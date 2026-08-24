"""The two pictures this program ships: the logo and the background.

It has two independent jobs. `build.py` scales it into a multi-size `.ico`
that becomes the executable's Explorer icon; this module loads it at runtime
for the window, the taskbar and the topbar. Neither knows about the other, and
both must survive the file being absent -- a missing picture is no reason to
stop somebody building or running the program.

⚠️ The PNG already carries a real alpha channel with the circular cut baked
in: colour type 6, corners at alpha 0, centre at 255. **Do not cut a circle
again here.** The source image arrived with its transparency painted in as a
checkerboard, that was fixed once, offline, and the fixed file is what is
committed. Cutting a second time would round the artwork twice.

`assets/background.png` is the second, and it has one job: what an empty
results window shows instead of a flat rectangle. It is produced by
`assets/make_background.py` from the source artwork -- a committed generator
beside a committed artifact, the same pattern as `sde/build_cyno_sets.py`.
The dimming is baked into the file so the app does no work per repaint.

Everything else in the interface is drawn (`ui/glyphs.py`, the tray beacon,
the tier wedge). Artwork cannot be derived from code, which is why these two
files exist.
"""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap

LOGO = "icon.png"
BACKGROUND = "background.png"


def _asset(name: str) -> str:
    """Where a bundled asset lives, from source or from a frozen exe.

    The same contract as `core.cyno_sets._artifact_path`: ask `sys._MEIPASS`
    directly rather than deriving it from `__file__`. Walking two directories
    up lands in the same place today, but that is a detail of how PyInstaller
    names frozen modules, not a promise.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", name)


def logo_pixmap(size: int) -> QPixmap | None:
    """The logo at `size` points, or None when the file is missing.

    Scaled from the 512px master with a device pixel ratio set, the way
    `ui/glyphs` renders its glyphs, so it does not go soft on a HiDPI screen.

    ⚠️ Below roughly 32 px this logo is unreadable -- the dense radar dial
    becomes an orange blob and only the circle survives. In the topbar it is
    decoration, not information. The fix is a different picture for the small
    sizes, not code.
    """
    pix = QPixmap(_asset(LOGO))
    if pix.isNull():
        return None
    scaled = pix.scaled(size * 2, size * 2, Qt.KeepAspectRatio,
                        Qt.SmoothTransformation)
    scaled.setDevicePixelRatio(2.0)
    return scaled


def logo_icon() -> QIcon:
    """The window and taskbar icon. An empty icon when the file is missing.

    `QApplication.setWindowIcon(QIcon())` is a no-op, so a missing asset
    silently leaves Qt's default in place instead of raising.
    """
    pix = QPixmap(_asset(LOGO))
    return QIcon() if pix.isNull() else QIcon(pix)


def background_pixmap() -> QPixmap | None:
    """The empty window's backdrop, or None when the file is missing.

    Returned unscaled: the caller scales it to cover whatever the viewport
    happens to be, and caching a scaled copy is the caller's business because
    only the caller knows when the size changed.

    Missing is not an error, exactly as with `logo_pixmap`. The window then
    shows the flat panel it showed before this picture existed.
    """
    pix = QPixmap(_asset(BACKGROUND))
    return None if pix.isNull() else pix
