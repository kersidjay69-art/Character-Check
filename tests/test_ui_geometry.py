"""Numbers the window's look depends on, checked without opening a window.

Only class attributes are read here -- no QApplication, no widgets -- so this
runs anywhere the rest of the suite does.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import analyze, config, i18n  # noqa: E402
from ui import results_window, styles  # noqa: E402
from ui.results_window import IconRowDelegate  # noqa: E402


class TestRowHeight(unittest.TestCase):
    """The icon cell and the tree row have to be the same size.

    They used to be set independently -- a 20px icon in a 26px cell inside a
    30px row -- and the four leftover pixels read on screen as gaps between
    the rows. If these two ever drift apart again the gaps come straight back,
    and nothing else in the suite would notice.
    """

    def test_the_icon_cell_fills_the_row_exactly(self):
        self.assertEqual(styles.ROW_H, IconRowDelegate.cell.fget(
            IconRowDelegate))

    def test_the_stylesheet_asks_for_the_same_height(self):
        self.assertIn("min-height: %dpx" % styles.ROW_H, styles.MAIN_QSS)

    def test_no_vertical_padding_on_a_row(self):
        """Padding here is added to the height, so it reappears as a gap."""
        self.assertIn("padding: 0px 2px;", styles.MAIN_QSS)

    def test_the_badge_still_fits_inside_the_artwork(self):
        self.assertLess(IconRowDelegate.BADGE, IconRowDelegate.ICON // 2)


class TestVerdictColours(unittest.TestCase):
    def test_every_level_has_a_colour(self):
        """A level with no colour paints the pilot's name in the default text
        colour, which silently reads as "no verdict"."""
        for level in (analyze.LEVEL_CYNO, analyze.LEVEL_HULL,
                      analyze.LEVEL_INDY, analyze.LEVEL_SEEN,
                      analyze.LEVEL_NONE):
            self.assertIn(level, styles.LEVEL_COLORS)

    def test_seen_and_clean_are_told_apart(self):
        """Both are greys and they stand side by side as numbers in the topbar."""
        self.assertNotEqual(styles.LEVEL_COLORS[analyze.LEVEL_SEEN],
                            styles.LEVEL_COLORS[analyze.LEVEL_NONE])


class TestAlwaysOnTop(unittest.TestCase):
    """The toggle must not lose the window.

    `QWidget.setWindowFlag` hides a visible widget as a side effect, so the
    old code -- flip the flag, then `if self.isVisible(): self.show()` -- asked
    a question whose answer it had just destroyed. The window disappeared on
    the first click and never came back, which reads exactly like a crash.
    Recreating the native window also re-places it by its client rectangle, so
    it climbed the screen by one title bar per click.
    """

    @classmethod
    def setUpClass(cls):
        # The pin writes `window_on_top` to config.json, so the test has to own
        # its data directory -- otherwise running the suite silently unpins the
        # user's real window.
        import tempfile
        os.environ["CC_DATA_DIR"] = tempfile.mkdtemp()
        from core import config
        config.load(force=True)

        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from core import cyno_sets
        from ui.results_window import ResultsWindow
        cls.win = ResultsWindow(cyno_sets.load())
        cls.win.setGeometry(200, 200, 800, 600)
        cls.win.show()
        cls.app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.win.on_top_btn.setChecked(False)
        cls.win.hide()
        cls.app.processEvents()
        os.environ.pop("CC_DATA_DIR", None)
        from core import config
        config.load(force=True)

    def test_the_window_survives_being_pinned(self):
        self.win.on_top_btn.setChecked(True)
        self.app.processEvents()
        self.assertTrue(self.win.isVisible())

    def test_the_window_survives_being_unpinned(self):
        self.win.on_top_btn.setChecked(True)
        self.app.processEvents()
        self.win.on_top_btn.setChecked(False)
        self.app.processEvents()
        self.assertTrue(self.win.isVisible())

    def test_pinning_does_not_move_the_window(self):
        before = self.win.geometry()
        self.win.on_top_btn.setChecked(True)
        self.app.processEvents()
        self.win.on_top_btn.setChecked(False)
        self.app.processEvents()
        self.assertEqual(before, self.win.geometry())


class TestModuleColumnWidth(unittest.TestCase):
    """The module column has to hold every cyno in the game with no "+N".

    It was 96 px typed next to the delegate. Then the icon grew with the row
    height, three modules started needing 100, and a pilot carrying all three
    drew two of them and a "+1". Nothing in the suite noticed, because nothing
    knew the two numbers were related.
    """

    @staticmethod
    def _slots(width, count):
        """Ask the delegate's own layout code, rather than re-deriving it.

        Re-deriving is how the two numbers drifted apart in the first place.
        `_slots` reads nothing but `option.rect`, so a bare QRect in a stand-in
        object is enough and no QApplication is needed.
        """
        from types import SimpleNamespace

        from PySide6.QtCore import QRect
        delegate = IconRowDelegate.__new__(IconRowDelegate)
        option = SimpleNamespace(rect=QRect(0, 0, width, styles.ROW_H))
        slots, _ = IconRowDelegate._slots(delegate, option,
                                          [(1, None)] * count)
        return len(slots)

    def test_the_computed_width_really_fits_that_many_icons(self):
        for count in (1, 2, 3, 4):
            self.assertEqual(
                count, self._slots(IconRowDelegate.width_for(count), count),
                count)

    def test_one_pixel_less_is_not_enough(self):
        """Guards the +1 for QRect.right() being inclusive. Without it the
        column is a pixel short, the third module is dropped, and a "+1"
        appears where an icon should be -- silently, as it did once."""
        for count in (2, 3):
            self.assertEqual(
                count - 1,
                self._slots(IconRowDelegate.width_for(count) - 1, count),
                count)

    def test_the_width_grows_with_the_icon(self):
        """The bug in one line: a constant would not have."""
        self.assertGreater(IconRowDelegate.width_for(3),
                           IconRowDelegate.width_for(2))

    def test_the_column_is_sized_from_the_sets_not_from_a_three(self):
        """If CCP ever ships a fourth cyno the column grows with the SDE."""
        self.assertEqual(3, len(analyze.ALL_CYNO))


class TestNameColumn(unittest.TestCase):
    """What held the name column at 250 px was never the names.

    99% of a 1402-pilot hub paste fits in 125 px and the longest was 152. It
    was the evidence label underneath -- "2026-05-03  died in a cyno hull" is
    164 px, 184 in Russian. The short forms fit in 124/133.
    """

    def test_every_evidence_kind_has_a_short_label(self):
        for kind in ("fitted", "cargo", "hull_lost", "hull_flown"):
            for lang in ("en", "ru"):
                i18n.set_language(lang)
                short = i18n.t("short." + kind)
                self.assertNotEqual("short." + kind, short, (kind, lang))
                self.assertLess(len(short), len(i18n.t("kind." + kind)),
                                (kind, lang))
        i18n.set_language("en")


class TestFilterMenu(unittest.TestCase):
    """Three filters, three settings, one funnel."""

    def test_every_menu_line_drives_a_real_setting(self):
        """A key with no default silently reads False, which would turn the
        industrial filter off for everybody."""
        for key in results_window._FILTER_KEYS:
            self.assertIn(key, config.DEFAULTS, key)

    def test_every_menu_line_has_a_label_in_both_languages(self):
        for suffix in results_window._FILTER_KEYS.values():
            for lang in ("en", "ru"):
                i18n.set_language(lang)
                self.assertNotEqual("filter." + suffix,
                                    i18n.t("filter." + suffix), suffix)
        i18n.set_language("en")

    def test_potential_is_off_by_default(self):
        """The default is the whole speed story: with it off a scan asks
        zKillboard once per pilot instead of twice."""
        self.assertFalse(config.DEFAULTS["find_potential"])


if __name__ == "__main__":
    unittest.main()
