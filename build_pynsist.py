"""The pynsist build -- an EXPERIMENT, not the way this program ships.

`build.py` is untouched and remains the real build. This file exists to test
one hypothesis, recorded in `docs/STATE.md`, about antivirus false positives.

WHY
---
`build.report_bootloader()` measured that our executable contains PyInstaller's
stock `runw.exe` byte for byte (5 of 5 4 KB slices, sha256 1015b339...). Every
frozen Python application on earth contains the same bytes, malware included,
and generic engine signatures sit on them. Two attempts to move that number
have already failed and are written down: onedir instead of onefile took the
count from 1 engine to 2, and rebuilding the bootloader changed 64 bytes of
which every one was metadata.

PySpy -- a comparable Python/Windows EVE tool -- reports in its CHANGELOG 0.5.6:
"Switch pynsist for installation to avoid bogus virus warnings." pynsist embeds
no bootloader at all: it ships a real embeddable CPython plus an NSIS
installer, so the bytes those signatures key on are simply absent.

⚠️ THE COMPARISON IS NOT STRICT, and that has to be said before anyone reads a
number off it. Our detections were on `CharacterCheck.exe`. What pynsist
produces is an NSIS installer stub -- a different binary with its own detection
profile, and NSIS is itself a packaging format malware uses. A drop from 2 to 1
could be that, and not the absence of a bootloader.

⚠️ AND THE COST IS REAL. This produces an *installer*, not a portable folder.
`config.cache_dir` puts the cache beside the executable precisely so a copy on
a USB stick carries its answers with it (see CLAUDE.md). If this experiment
wins on detections, the trade is "fewer false positives" against "no longer
portable", and that is a decision to put to a human with both numbers in hand.

    pip install pynsist            # and NSIS, e.g. winget install NSIS.NSIS
    python build_pynsist.py        # -> build/nsis/CharacterCheck_Installer.exe
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

import build          # the real build, reused for its icon and its metadata
from core import config

ROOT = build.ROOT
OUT_DIR = os.path.join(ROOT, "build", "nsis")
CFG = os.path.join(ROOT, "build", "installer.cfg")

# Bundled, and deliberately not the Python running this script. PySide6 wheels
# are cp310-abi3, so anything from 3.10 up loads them; 3.12 is what PySpy ships
# and what has the most miles on it under pynsist, whose last release was 2022.
PYTHON = "3.12.10"

# Pinned exactly, the way PySpy's own installer.cfg does: pynsist resolves no
# dependencies, so every transitive one has to be named here or the app dies
# at the first import on somebody else's machine.
#
# WARNING: PySide6-Essentials, NOT PySide6. The meta-package pulls
# PySide6-Addons in as well -- a 168 MB wheel of WebEngine, Quick, Charts,
# Multimedia and 3D that this app never imports. Essentials carries QtCore,
# QtGui, QtWidgets and QtNetwork, which is the whole of what `ui/` uses.
WHEELS = [
    "shiboken6==6.11.1",
    "PySide6-Essentials==6.11.1",
    "requests==2.34.2",
    "urllib3==2.7.0",
    "idna==3.15",
    "certifi==2026.4.22",
    "charset-normalizer==3.4.7",
]

# Our own code. `packages` copies from this working tree, which is what we want
# for the app itself -- there is no Character Check wheel to download.
PACKAGES = ["main", "core", "ui"]

# WARNING: the artifacts have to land INSIDE pkgs/, not in the install root.
# `cyno_sets._artifact_path` and `ui.assets._asset` both fall back to two
# directories above their own module when `sys._MEIPASS` is absent, and under
# pynsist that is `pkgs/`. Dropping them in $INSTDIR would leave the app unable
# to find its own cyno sets, which is a hard failure by design.
# WARNING: absolute, and every other path in this config too. pynsist resolves
# relative paths against the DIRECTORY OF THE CONFIG FILE, not the working
# directory -- and this config is generated into `build/`, so a relative
# `assets/icon.png` sends it looking for `build/assets/icon.png`. The failure
# is a bare `FileNotFoundError: [WinError 2]` that never says which path it
# wanted.
FILES = [
    (os.path.join(ROOT, "sde", "cyno_sets.json"), r"$INSTDIR\pkgs\sde"),
    (os.path.join(ROOT, "assets", "icon.png"), r"$INSTDIR\pkgs\assets"),
    (os.path.join(ROOT, "assets", "background.png"), r"$INSTDIR\pkgs\assets"),
]

# Even inside Essentials there is a great deal this app never loads. pynsist's
# exclude patterns are rooted at `pkgs/`, so this is the closest thing it has
# to PyInstaller's --exclude-module. It trims the tree rather than the import
# graph: no hook decides what a module needs, we simply say what to leave out.
EXCLUDE = [
    "pkgs/PySide6/Qt6Quick*.dll", "pkgs/PySide6/Qt6Qml*.dll",
    "pkgs/PySide6/Qt6WebEngine*.dll", "pkgs/PySide6/Qt6WebChannel*.dll",
    "pkgs/PySide6/Qt6Charts*.dll", "pkgs/PySide6/Qt6DataVisualization*.dll",
    "pkgs/PySide6/Qt6Multimedia*.dll", "pkgs/PySide6/Qt63D*.dll",
    "pkgs/PySide6/Qt6Pdf*.dll", "pkgs/PySide6/Qt6Designer*.dll",
    "pkgs/PySide6/Qt6Sql*.dll", "pkgs/PySide6/Qt6Test*.dll",
    "pkgs/PySide6/Qt6Bluetooth*.dll", "pkgs/PySide6/Qt6SerialPort*.dll",
    "pkgs/PySide6/Qt6Positioning*.dll", "pkgs/PySide6/Qt6OpenGL*.dll",
    "pkgs/PySide6/QtQuick*.pyd", "pkgs/PySide6/QtQml*.pyd",
    "pkgs/PySide6/QtWebEngine*.pyd", "pkgs/PySide6/QtWebChannel*.pyd",
    "pkgs/PySide6/QtCharts*.pyd", "pkgs/PySide6/QtDataVisualization*.pyd",
    "pkgs/PySide6/QtMultimedia*.pyd", "pkgs/PySide6/Qt3D*.pyd",
    "pkgs/PySide6/QtPdf*.pyd", "pkgs/PySide6/QtDesigner*.pyd",
    "pkgs/PySide6/QtSql*.pyd", "pkgs/PySide6/QtTest*.pyd",
    "pkgs/PySide6/QtBluetooth*.pyd", "pkgs/PySide6/QtSerialPort*.pyd",
    "pkgs/PySide6/QtPositioning*.pyd", "pkgs/PySide6/QtOpenGL*.pyd",
    "pkgs/PySide6/qml/*", "pkgs/PySide6/translations/*",
    "pkgs/PySide6/examples/*", "pkgs/PySide6/glue/*",
    "pkgs/PySide6/typesystems/*", "pkgs/PySide6/include/*",
    "pkgs/PySide6/plugins/sqldrivers/*", "pkgs/PySide6/plugins/multimedia/*",
    "pkgs/PySide6/plugins/designer/*",
]


def write_cfg(path: str, icon: str) -> str:
    lines = [
        "[Application]",
        "name=Character Check",
        "version=%s" % config.VERSION,
        # PROJECT_URL, never a person: the installer is handed to strangers,
        # and invariant 7 keeps the author out of everything but ui/about.py.
        "publisher=%s" % config.PROJECT_URL,
        "entry_point=main:main",
        "icon=%s" % icon,
        # A tray app. A console hanging around for its whole life is the bug
        # start.cmd exists to avoid.
        "console=false",
        "",
        "[Python]",
        "version=%s" % PYTHON,
        "bitness=64",
        "",
        "[Include]",
        "pypi_wheels=" + "".join("\n    " + w for w in WHEELS),
        "packages=" + "".join("\n    " + p for p in PACKAGES),
        # WARNING: the first entry goes on the key's own line, and that is not
        # cosmetic. `nsist.configreader.read_extra_files` reads this value with
        # a bare `.splitlines()` -- unlike `packages` and `pypi_wheels`, which
        # it strips first -- and appends every line that has no `>` as a path
        # of its own. A leading blank line therefore becomes the file `''`,
        # and pynsist dies inside `shutil.copy2` with a bare
        # `FileNotFoundError: [WinError 3]` naming no path at all.
        "files=" + "\n    ".join("%s > %s" % pair for pair in FILES),
        "exclude=" + "".join("\n    " + p for p in EXCLUDE),
        "",
        "[Build]",
        "directory=%s" % OUT_DIR,
        "installer_name=CharacterCheck_Installer.exe",
        "",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="pynsist experiment")
    ap.add_argument("--cfg-only", action="store_true",
                    help="write installer.cfg and stop")
    args = ap.parse_args()

    icon = build.make_icon(os.path.join(ROOT, "build", "CharacterCheck.ico"))
    cfg = write_cfg(CFG, icon)
    print("config:", cfg)
    if args.cfg_only:
        return 0

    cmd = [sys.executable, "-m", "nsist", cfg]
    print("$", " ".join(cmd))
    code = subprocess.call(cmd, cwd=ROOT)
    if code:
        return code
    out = os.path.join(OUT_DIR, "CharacterCheck_Installer.exe")
    if os.path.exists(out):
        print("built: %s (%.1f MB)" % (out, os.path.getsize(out) / 1e6))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
