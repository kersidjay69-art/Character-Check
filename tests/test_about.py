"""The About dialog. It had no test at all, and that is why it was broken.

`ui/about.py` called `i18n.t()` without importing `i18n`, so opening it raised
NameError -- in a shipped release. Nothing here constructed the dialog, and
`test_distribution.py` deliberately reads the file with `ast` instead of
importing it, so the whole suite could stay green over a window that could not
open. The first test below is the one that would have caught it.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui import about  # noqa: E402


class TestAboutDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["CC_DATA_DIR"] = tempfile.mkdtemp()
        from core import config
        config.load(force=True)

        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        cls.dlg = about.AboutDialog()

    @classmethod
    def tearDownClass(cls):
        cls.dlg.close()
        cls.app.processEvents()
        os.environ.pop("CC_DATA_DIR", None)
        from core import config
        config.load(force=True)

    def _labels(self):
        from PySide6.QtWidgets import QLabel
        return [w.text() for w in self.dlg.findChildren(QLabel)]

    def _buttons(self):
        from PySide6.QtWidgets import QPushButton
        return self.dlg.findChildren(QPushButton)

    def test_it_opens_at_all(self):
        """The whole point. It did not, for one release."""
        self.assertTrue(self.dlg.windowTitle())

    def test_no_bare_i18n_key_is_rendered(self):
        """A missing key shows as `about.version` -- visible, and useless."""
        for text in self._labels() + [b.text() for b in self._buttons()]:
            for prefix in ("about.", "contact."):
                self.assertNotIn(prefix, text, text)

    def test_the_three_handles_reach_the_buttons(self):
        captions = " ".join(b.text() for b in self._buttons())
        for handle in (about.DISCORD, about.TELEGRAM, about.CHARACTER):
            self.assertIn(handle, captions)

    def test_every_button_says_what_it_does(self):
        for btn in self._buttons():
            self.assertTrue(btn.toolTip(), btn.text())

    def test_the_user_agent_is_shown_rather_than_promised(self):
        """The user can read what their own copy sends instead of trusting a
        sentence about it."""
        self.assertTrue(any(t.startswith("User-Agent:")
                            for t in self._labels()))

    def test_copying_the_handle_announces_it_to_the_watcher(self):
        from core import clipboard
        self.dlg._copy(about.DISCORD)
        self.assertTrue(clipboard._was_expected(about.DISCORD))
        # And it restores the title afterwards rather than leaving "copied".
        self.assertIn(about.DISCORD, self.dlg.windowTitle())


if __name__ == "__main__":
    unittest.main()
