"""Two small mechanisms with no home of their own.

The logo has to be found both from source and inside a frozen bundle, and the
clipboard watcher has to know its own writes from a paste. Neither is worth a
file, and both are the kind of thing that fails silently.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from core import clipboard  # noqa: E402


class TestClipboardEcho(unittest.TestCase):
    """The app writes to the clipboard; the watcher must not read it back.

    `GetClipboardSequenceNumber` moves for our own write exactly as it does
    for a paste. Before this, Ctrl+C on a list of pilots started a fresh scan
    of those same pilots, and copying a contact handle made the guard refuse
    it half a second later.
    """

    def tearDown(self):
        clipboard._expected.clear()

    def test_an_announced_write_is_swallowed_once(self):
        clipboard.expect("Leya Sokard")
        self.assertTrue(clipboard._was_expected("Leya Sokard"))
        # Copying the same text again, by hand, is a real paste.
        self.assertFalse(clipboard._was_expected("Leya Sokard"))

    def test_anything_else_passes_straight_through(self):
        self.assertFalse(clipboard._was_expected("some names"))

    def test_a_real_paste_clears_a_stale_expectation(self):
        """An expectation that was never consumed must not sit there waiting
        to eat a genuine copy of the same text an hour later."""
        clipboard.expect("kersid_jay")
        self.assertFalse(clipboard._was_expected("something the user copied"))
        self.assertFalse(clipboard._was_expected("kersid_jay"))

    def test_the_module_still_never_writes(self):
        """Invariant 2 cuts both ways: this module reads, Qt writes."""
        with open(os.path.join(ROOT, "core", "clipboard.py"),
                  encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("SetClipboardData", src)
        self.assertNotIn("EmptyClipboard", src)


class TestLogoAsset(unittest.TestCase):
    """The one binary file in the repository, now loaded at runtime too."""

    def test_the_resolver_finds_it_from_source(self):
        from ui import assets
        self.assertTrue(os.path.exists(assets._asset(assets.LOGO)))

    def test_it_still_carries_its_own_transparency(self):
        """RGBA with the circular cut baked in. If this ever fails, the file
        was re-exported without an alpha channel -- and the answer is to fix
        the file, NOT to cut a circle at load time."""
        with open(os.path.join(ROOT, "assets", "icon.png"), "rb") as fh:
            head = fh.read(26)
        self.assertEqual(b"\x89PNG", head[:4])
        self.assertEqual(6, head[25], "colour type 6 == RGBA")

    def test_a_missing_file_is_an_answer_rather_than_a_crash(self):
        """A missing picture must not stop the app any more than it stops a
        build, where `build._logo_png` returns None for the same reason."""
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        from ui import assets
        prev = assets.LOGO
        try:
            assets.LOGO = "no-such-file.png"
            self.assertIsNone(assets.logo_pixmap(22))
            self.assertTrue(assets.logo_icon().isNull())
        finally:
            assets.LOGO = prev


if __name__ == "__main__":
    unittest.main()
