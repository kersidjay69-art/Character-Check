"""Build the Windows executable.

    python build.py                       # -> dist/CharacterCheck/
    python build.py --dest "C:/some/dir"  # and copy it there
    python build.py --onefile             # one file instead of a folder

The app ships without binary assets, so the executable's icon is rendered here
from the same beacon `ui.tray` draws for the tray -- one source of truth, and
nothing to keep in sync by hand. The version resource is generated the same
way, from `core.config`.

A FOLDER, NOT ONE FILE
----------------------
`--onefile` is an option now, not the default, and the reason is antivirus
heuristics. A onefile build is a stub that unpacks itself into %TEMP% and runs
what it just wrote there -- behaviour indistinguishable from a dropper, and
generic engines score it that way. VirusTotal flagged the onefile build on
2026-08-20 (Bkav Pro, W32.Malware.98C1BF1C -- one engine, a false positive, but
one that costs a user's trust to explain).

A onedir build has no extraction stage at all. It also starts instantly: the
1.6 s cold start measured on the onefile build WAS the unpacking.

Three things the bundle cannot do without:

  * `sde/cyno_sets.json`. Everything the app knows about cyno modules and the
    hulls that carry them is in that one file; without it the app raises on
    startup rather than declaring the whole galaxy clean.
  * a windowed (console-less) target. This is a tray app -- a console window
    hanging around for its whole life is the bug `main.pyw` exists to avoid.
  * a version resource. An executable with a blank Details tab is a nameless
    unsigned binary, which is a heuristic signal in its own right.
"""
from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
NAME = "CharacterCheck"

# The one binary asset in the repository, and it is here on purpose: the
# executable's icon is artwork, and artwork cannot be derived from code the way
# the tray beacon is. Everything else -- the tray icon, the topbar glyphs, the
# tech-tier wedge -- is still drawn. See CLAUDE.md.
#
# 512x512 PNG with a real alpha channel. If it is missing the build falls back
# to the drawn beacon rather than failing: a missing picture must not stop
# somebody from building the program.
LOGO = os.path.join(ROOT, "assets", "icon.png")

# Qt modules PySide6 ships that this app never imports. PyInstaller's hook is
# generous by default, and these are the expensive ones -- WebEngine alone is
# well over a hundred megabytes.
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQml",
    "PySide6.QtQuick3D", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtDesigner",
    "PySide6.QtBluetooth", "PySide6.QtPositioning", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "tkinter", "matplotlib", "numpy", "PIL", "pandas",
]


def _beacon_png(size: int) -> bytes:
    """The tray beacon at one size, as PNG bytes.

    Geometry copied from `ui.tray._icon` and expressed as fractions, so it
    stays sharp at 16 pixels and at 256 instead of being a scaled-down 64.
    """
    from PySide6.QtCore import QBuffer, QByteArray, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    from ui import styles

    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    u = size / 64.0
    colour = QColor(styles.ACCENT)
    p.setPen(QPen(colour, max(1.0, 6 * u)))
    p.drawEllipse(int(12 * u), int(12 * u), int(40 * u), int(40 * u))
    p.setPen(QPen(colour, max(1.0, 5 * u)))
    for x1, y1, x2, y2 in ((32, 2, 32, 14), (32, 50, 32, 62),
                           (2, 32, 14, 32), (50, 32, 62, 32)):
        p.drawLine(int(x1 * u), int(y1 * u), int(x2 * u), int(y2 * u))
    p.end()

    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QBuffer.WriteOnly)
    pix.save(buf, "PNG")
    buf.close()
    return bytes(data)


def _logo_png(size: int) -> bytes | None:
    """The artwork at one size, or None if the asset is not there.

    Rescaled from the 512px master for every entry rather than letting Windows
    shrink one bitmap: the logo is a dense radar dial, and at 16px an
    unfiltered downscale turns it into orange mud.
    """
    from PySide6.QtCore import QBuffer, QByteArray, Qt
    from PySide6.QtGui import QImage

    if not os.path.exists(LOGO):
        return None
    img = QImage(LOGO)
    if img.isNull():
        return None
    img = img.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(data)


def make_icon(path: str, sizes=(16, 24, 32, 48, 64, 128, 256)) -> str:
    """Write a multi-size .ico.

    Assembled by hand rather than through Qt's ICO writer, which stores a
    single image: Windows picks a different size for the taskbar, the title
    bar and Explorer's large view, and one downscaled bitmap looks soft in at
    least two of them. Entries are PNG-compressed, which Windows has accepted
    since Vista.
    """
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    images = []
    for size in sizes:
        png = _logo_png(size)
        images.append((size, png if png is not None else _beacon_png(size)))
    print("icon source:", "assets/icon.png" if _logo_png(16) else
          "drawn beacon (assets/icon.png missing)")
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = [], []
    for size, png in images:
        # 0 means 256 in the directory entry -- the field is a single byte.
        dim = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                                   len(png), offset))
        blobs.append(png)
        offset += len(png)
    with open(path, "wb") as fh:
        fh.write(header)
        for e in entries:
            fh.write(e)
        for b in blobs:
            fh.write(b)
    return path


def _version_tuple(text: str) -> tuple:
    """"0.1" -> (0, 1, 0, 0). The resource wants four numbers, always.

    Tolerant on purpose: `config.VERSION` is a human string that will grow a
    third part one day, and may grow a "-rc1" after that. A build must not be
    the thing that discovers it.
    """
    parts = []
    for chunk in str(text or "").split("."):
        # LEADING digits, not every digit in the chunk: "0-rc1" has to read as
        # 0, and stripping non-digits wherever they sit would splice it into
        # "01" and quietly ship 1.1 as the version of 1.0-rc1.
        digits = ""
        for c in chunk.strip():
            if not c.isdigit():
                break
            digits += c
        parts.append(int(digits) if digits else 0)
    parts = (parts + [0, 0, 0, 0])[:4]
    return tuple(parts)


VERSION_TEMPLATE = """\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=%(vers)r,
    prodvers=%(vers)r,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', %(company)r),
      StringStruct('FileDescription', %(description)r),
      StringStruct('FileVersion', %(version)r),
      StringStruct('InternalName', %(name)r),
      StringStruct('LegalCopyright', %(copyright)r),
      StringStruct('OriginalFilename', %(filename)r),
      StringStruct('ProductName', %(product)r),
      StringStruct('ProductVersion', %(version)r),
      StringStruct('Comments', %(comments)r)
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def make_version_file(path: str) -> str:
    """Write the Windows version resource, generated rather than kept.

    Same rule as the icon: nothing binary and nothing hand-maintained in the
    repository. Every field comes from `core.config`, so the exe's Details tab
    and the User-Agent can never disagree about what this program is.

    ⚠️ No author anywhere in here. Invariant 7 keeps the author's contacts in
    `ui/about.py` alone, and this file is handed to strangers -- so
    `CompanyName` is the repository, which is the project's one public
    identity, and `LegalCopyright` names the licence instead of a person.

    040904B0 is US English + Unicode; the matching Translation kid must agree
    with it or Explorer shows nothing at all.
    """
    sys.path.insert(0, ROOT)
    from core import config

    body = VERSION_TEMPLATE % {
        "vers": _version_tuple(config.VERSION),
        "version": config.VERSION,
        "name": NAME,
        "filename": NAME + ".exe",
        "product": "Character Check",
        "company": config.PROJECT_URL,
        "description": "Character Check -- EVE Online cyno history checker",
        "copyright": "Apache License 2.0 -- see LICENSE",
        "comments": "Reads a pasted local member list and reports which "
                    "pilots have lit a cyno.",
    }
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


# sha256 of the bootloaders PyInstaller SHIPS, per version. Matching one means
# we are building on the stock binary -- the same bytes as every other
# PyInstaller app in the world, malware included, which is exactly what generic
# antivirus signatures are keyed on. See `check_bootloader`.
#
# ⚠️ Keyed by version, never a single bare hash. After an upgrade the key is
# simply absent and the check has to SAY it does not recognise the version --
# a check that silently passes on anything it has not seen is decoration.
STOCK_BOOTLOADERS = {
    "6.20.0": {
        "run.exe":
            "6a9bca966dbf6c3f39ffa15c3adb9aed1ddcec2498284cf62969b247d72478e9",
        "runw.exe":
            "1015b3391b8e45c2760d4f15f4089aa9cb043f8e56e4051e8234e0e3d2556c10",
    },
}

# --windowed embeds runw; the console variant is only here to be recognised.
WINDOWED_BOOTLOADER = "runw.exe"


def _pyinstaller():
    """The installed PyInstaller, or None.

    None is a normal answer, not an error: PyInstaller is a build tool and is
    deliberately absent from `requirements.txt`, so the test suite and any
    other importer of this module has to survive without it.
    """
    try:
        import PyInstaller
    except ImportError:
        return None
    return PyInstaller


def bootloader_path(name: str = WINDOWED_BOOTLOADER) -> str:
    """Where PyInstaller keeps the bootloader it is about to embed.

    Empty string when PyInstaller is not installed -- nothing to point at.
    """
    pyi = _pyinstaller()
    if pyi is None:
        return ""
    return os.path.join(os.path.dirname(pyi.__file__), "bootloader",
                        "Windows-64bit-intel", name)


def check_bootloader(name: str = WINDOWED_BOOTLOADER) -> tuple:
    """(status, sha256) for the bootloader this build will embed.

    status is "custom", "stock" or "unknown-version".

    Why this exists: the PyPI wheel ships prebuilt bootloaders, so the C code
    that starts every frozen app is byte-identical everywhere. Measured on our
    own build -- a 4 KB slice from the middle of the stock runw.exe was present
    verbatim in CharacterCheck.exe. Rebuilding it from source (see CLAUDE.md)
    produces a unique binary; this guard is what notices when a plain
    `pip install --upgrade pyinstaller` quietly puts the stock one back.
    """
    import hashlib

    pyi = _pyinstaller()
    path = bootloader_path(name)
    if pyi is None or not path or not os.path.exists(path):
        return ("unknown-version", "")
    with open(path, "rb") as fh:
        digest = hashlib.sha256(fh.read()).hexdigest()
    known = STOCK_BOOTLOADERS.get(pyi.__version__)
    if known is None:
        return ("unknown-version", digest)
    return ("stock" if known.get(name) == digest else "custom", digest)


def report_bootloader() -> str:
    """Print the bootloader's provenance. Never fails a build over it -- the
    stock one produces a working program, just a more suspicious one."""
    pyi = _pyinstaller()
    if pyi is None:
        print("bootloader: PyInstaller is not installed -- nothing to check")
        return "unknown-version"
    version = pyi.__version__
    status, digest = check_bootloader()
    short = digest[:16] or "?"
    if status == "custom":
        print("bootloader: %s (custom -- built from source)" % short)
    elif status == "stock":
        print("bootloader: %s (STOCK for PyInstaller %s -- shared byte for "
              "byte with every PyInstaller app there is. Rebuild it: see "
              "the build section of CLAUDE.md)" % (short, version))
    else:
        print("bootloader: %s (PyInstaller %s is not in STOCK_BOOTLOADERS -- "
              "cannot tell stock from custom; add its hashes to build.py)"
              % (short, version))
    return status


def build(dest: str | None, onefile: bool = False) -> int:
    work = os.path.join(ROOT, "build")
    dist = os.path.join(ROOT, "dist")
    os.makedirs(work, exist_ok=True)
    icon = make_icon(os.path.join(work, "%s.ico" % NAME))
    print("icon:", icon)
    version = make_version_file(os.path.join(work, "version.txt"))
    print("version resource:", version)
    report_bootloader()

    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
           "--windowed", "--name", NAME, "--icon", icon,
           "--version-file", version,
           # Explicit, though UPX is not installed here. If it ever lands on
           # the PATH PyInstaller picks it up by itself, silently, and a
           # UPX-packed binary is flagged by a dozen engines rather than one.
           "--noupx",
           "--distpath", dist, "--workpath", work,
           "--specpath", work,
           # Separator is ';' on Windows, ':' elsewhere.
           "--add-data", "%s%s%s" % (os.path.join(ROOT, "sde",
                                                  "cyno_sets.json"),
                                     os.pathsep, "sde")]
    cmd.append("--onefile" if onefile else "--onedir")
    for mod in EXCLUDES:
        cmd += ["--exclude-module", mod]
    cmd.append(os.path.join(ROOT, "main.py"))

    print("$", " ".join(cmd))
    started = time.time()
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        return rc
    exe = os.path.join(dist, NAME + ".exe")
    if not onefile:
        exe = os.path.join(dist, NAME, NAME + ".exe")
    print("built in %.0f s: %s (%.1f MB)"
          % (time.time() - started, exe, os.path.getsize(exe) / 1048576.0))

    if dest:
        os.makedirs(dest, exist_ok=True)
        if onefile:
            shutil.copy2(exe, os.path.join(dest, NAME + ".exe"))
        else:
            target = os.path.join(dest, NAME)
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(os.path.join(dist, NAME), target)
        print("copied to", dest)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Build CharacterCheck")
    ap.add_argument("--dest", default="", help="also copy the result here")
    ap.add_argument("--onefile", action="store_true",
                    help="one file instead of a folder: convenient to hand "
                         "around, but it unpacks itself into %%TEMP%% on every "
                         "launch -- which costs 1.6 s of startup and reads to "
                         "a generic antivirus engine as a dropper")
    args = ap.parse_args()
    return build(args.dest or None, onefile=args.onefile)


if __name__ == "__main__":
    sys.exit(main())
