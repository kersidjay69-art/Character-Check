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
    def _slots(width, count, gap=None):
        """Ask the delegate's own layout code, rather than re-deriving it.

        Re-deriving is how the two numbers drifted apart in the first place.
        `_slots` reads nothing but `option.rect`, so a bare QRect in a stand-in
        object is enough and no QApplication is needed.
        """
        from types import SimpleNamespace

        from PySide6.QtCore import QRect
        delegate = IconRowDelegate.__new__(IconRowDelegate)
        # __new__ skips __init__, so `gap` comes from the class attribute
        # unless this test sets one -- which is why the class carries one.
        if gap is not None:
            delegate.gap = gap
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


class TestIconGap(unittest.TestCase):
    """Two columns, two gaps, one delegate class.

    Ships are unframed, so nothing has to hold them apart and the row fits
    more of them. Modules cannot follow: each is framed in a 2px colour, and
    two frames touching read as one wide box.
    """

    # Wrapped again: reading a staticmethod off a class yields a plain
    # function, which would then take `self` as its first argument.
    _slots = staticmethod(TestModuleColumnWidth._slots)

    def test_the_module_gap_keeps_the_coloured_frames_apart(self):
        """The reason the modules column cannot use the tight gap, as a
        number rather than as a sentence in a comment."""
        self.assertGreaterEqual(IconRowDelegate.GAP,
                                2 * IconRowDelegate.BORDER)

    def test_the_tight_gap_fits_more_ships_in_the_same_width(self):
        """The whole point of the change, in one assertion."""
        wide = self._slots(400, 20, gap=IconRowDelegate.GAP)
        tight = self._slots(400, 20, gap=IconRowDelegate.GAP_TIGHT)
        self.assertGreater(tight, wide)

    def test_width_and_slots_still_agree_at_the_tight_gap(self):
        """`width_for` grew a parameter; the inclusive-right()+1 has to
        survive it, or the last ship is dropped for a "+1"."""
        gap = IconRowDelegate.GAP_TIGHT
        for count in (1, 2, 3, 4):
            self.assertEqual(
                count,
                self._slots(IconRowDelegate.width_for(count, gap), count,
                            gap=gap), count)

    def test_one_pixel_less_is_not_enough_at_the_tight_gap(self):
        gap = IconRowDelegate.GAP_TIGHT
        for count in (2, 3):
            self.assertEqual(
                count - 1,
                self._slots(IconRowDelegate.width_for(count, gap) - 1, count,
                            gap=gap), count)

    def test_the_default_gap_is_still_the_module_one(self):
        """`width_for(n)` with no gap sizes the module column, and the call
        site in _build passes no gap."""
        self.assertEqual(IconRowDelegate.width_for(3, IconRowDelegate.GAP),
                         IconRowDelegate.width_for(3))


class TestNameColumn(unittest.TestCase):
    """What held the name column at 250 px was never the names.

    99% of a 1402-pilot hub paste fits in 125 px and the longest was 152. It
    was the evidence label underneath -- "2026-05-03  died in a cyno hull" is
    164 px. The short form fits in 124.
    """

    def test_every_evidence_kind_has_a_short_label(self):
        for kind in ("fitted", "cargo", "hull_lost", "hull_flown"):
            short = i18n.t("short." + kind)
            self.assertNotEqual("short." + kind, short, kind)
            self.assertLess(len(short), len(i18n.t("kind." + kind)), kind)


class TestFilterMenu(unittest.TestCase):
    """Three filters, three settings, one funnel."""

    def test_every_menu_line_drives_a_real_setting(self):
        """A key with no default silently reads False, which would turn the
        industrial filter off for everybody."""
        for key in results_window._FILTER_KEYS:
            self.assertIn(key, config.DEFAULTS, key)

    def test_every_menu_line_has_a_label(self):
        for suffix in results_window._FILTER_KEYS.values():
            self.assertNotEqual("filter." + suffix,
                                i18n.t("filter." + suffix), suffix)

    def test_potential_is_off_by_default(self):
        """The default is the whole speed story: with it off a scan asks
        zKillboard once per pilot instead of twice."""
        self.assertFalse(config.DEFAULTS["find_potential"])


if __name__ == "__main__":
    unittest.main()
