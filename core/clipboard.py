"""Windows clipboard watcher, on ctypes only.

`GetClipboardSequenceNumber` is the point of this module: it is a cheap counter
that changes when the clipboard changes, so the watcher can poll several times
a second without ever opening the clipboard and without fighting other apps for
it. pyperclip does not expose it, which is why there is no dependency here.

Nothing is ever written to the clipboard, and no input is synthesised into the
game. The copy stays a human action -- CLAUDE.md invariant 2.
"""
from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes

log = logging.getLogger("cc.clipboard")

CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
_user32.OpenClipboard.argtypes = [wintypes.HWND]
_user32.OpenClipboard.restype = wintypes.BOOL
_user32.CloseClipboard.restype = wintypes.BOOL
_user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
_user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
_user32.GetClipboardData.argtypes = [wintypes.UINT]
_user32.GetClipboardData.restype = wintypes.HANDLE
_kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalLock.restype = wintypes.LPVOID
_kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]


def sequence_number() -> int:
    return int(_user32.GetClipboardSequenceNumber())


def read_text(retries: int = 5, pause: float = 0.05) -> str | None:
    """Read CF_UNICODETEXT, or None.

    The retry loop is not paranoia: the clipboard is a shared, singly-owned
    resource and OpenClipboard genuinely fails while another process holds it,
    which happens constantly right after a copy.
    """
    for _ in range(retries):
        if not _user32.OpenClipboard(None):
            time.sleep(pause)
            continue
        try:
            if not _user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return None
            handle = _user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return None
            ptr = _kernel32.GlobalLock(handle)
            if not ptr:
                return None
            try:
                return ctypes.c_wchar_p(ptr).value
            finally:
                _kernel32.GlobalUnlock(handle)
        finally:
            _user32.CloseClipboard()
    return None


class ClipboardWatcher(threading.Thread):
    """Calls `on_text(text)` whenever the clipboard content changes."""

    daemon = True

    def __init__(self, on_text, poll_ms: int = 200):
        super().__init__(name="clipboard-watcher")
        self._on_text = on_text
        self._interval = max(0.05, poll_ms / 1000.0)
        self._stop = threading.Event()
        # Seed with the current value so whatever is already in the clipboard
        # at startup does not fire a scan the user did not ask for.
        self._last_seq = sequence_number()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                seq = sequence_number()
                if seq != self._last_seq:
                    self._last_seq = seq
                    text = read_text()
                    if text:
                        self._on_text(text)
            except Exception:
                log.exception("clipboard poll failed")
                time.sleep(1.0)
            self._stop.wait(self._interval)
