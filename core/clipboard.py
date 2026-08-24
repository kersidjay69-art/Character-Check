"""Windows clipboard watcher, on ctypes only.

`GetClipboardSequenceNumber` is the point of this module: it is a cheap counter
that changes when the clipboard changes, so the watcher can poll several times
a second without ever opening the clipboard and without fighting other apps for
it. pyperclip does not expose it, which is why there is no dependency here.

No input is synthesised into the game and nothing is written to the clipboard
from HERE. The copy stays a human action -- CLAUDE.md invariant 2.

The window does write to it, though: Ctrl+C copies the selected names, and the
contacts row copies a Discord handle. Both go through Qt, and the watcher
cannot tell such a write from a paste -- the sequence number simply moves. So
they announce themselves with `expect()` first, and the watcher swallows the
echo. Without that, Ctrl+C on a list of pilots starts a fresh scan of those
same pilots, and copying a handle makes the guard refuse it half a second
later, in the very label that said "copied".
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


_expected: list[str] = []
_expected_lock = threading.Lock()


def expect(text: str) -> None:
    """Announce something this app is about to put on the clipboard.

    The next read matching it is consumed instead of being handed on as a
    paste. A list rather than a single slot because two copies can happen
    faster than the poll interval; matches are consumed, never accumulated,
    and anything else the user copies in between clears the queue -- a stale
    expectation must not eat a real paste an hour later.
    """
    with _expected_lock:
        _expected.append(text)


def _was_expected(text: str) -> bool:
    """True if `text` is our own write. Consumes the expectation."""
    with _expected_lock:
        if text in _expected:
            _expected.remove(text)
            return True
        _expected.clear()
        return False


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
                    # The sequence number is still consumed above: the echo is
                    # skipped, not deferred, or the next real copy of the same
                    # text would be skipped too.
                    if text and not _was_expected(text):
                        self._on_text(text)
            except Exception:
                log.exception("clipboard poll failed")
                time.sleep(1.0)
            self._stop.wait(self._interval)
