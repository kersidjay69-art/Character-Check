"""The results window as a live widget: state, buttons and the contacts row.

`test_ui_geometry.py` checks numbers without opening anything. This file opens
the window, because the things it guards are wiring rather than arithmetic --
a button connected to nothing, a field that only exists after the first scan,
two columns sharing one delegate again.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import i18n  # noqa: E402
from ui import about, results_window  # noqa: E402
from ui.results_window import IconRowDelegate  # noqa: E402


class WindowCase(unittest.TestCase):
    """One offscreen window, in a data directory of its own.

    The pin and the filters write config.json, so a shared directory would
    silently rewrite the user's real settings while the suite runs.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["CC_DATA_DIR"] = tempfile.mkdtemp()
        from core import config
        config.load(force=True)

        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])
        from core import cyno_sets
        from ui.results_window import ResultsWindow
        cls.win = ResultsWindow(cyno_sets.load())

    @classmethod
    def tearDownClass(cls):
        cls.win.hide()
        cls.app.processEvents()
        os.environ.pop("CC_DATA_DIR", None)
        from core import config
        config.load(force=True)


class TestClear(WindowCase):
    def test_clear_empties_the_tree_and_the_counts(self):
        from PySide6.QtWidgets import QTreeWidgetItem
        self.win.begin_scan(5)
        self.win.tree.addTopLevelItem(QTreeWidgetItem(["someone", "", ""]))
        self.win._set_counts({"cyno": 3})
        self.win.clear()
        self.assertEqual(0, self.win.tree.topLevelItemCount())
        self.assertFalse(self.win._count_labels["cyno"].isVisible())

    def test_clear_re_enables_the_refresh_button(self):
        """begin_scan disables it; without this the button stays dead until
        a scan that will never arrive finishes."""
        self.win.begin_scan(5)
        self.assertFalse(self.win.rescan_btn.isEnabled())
        self.win.clear()
        self.assertTrue(self.win.rescan_btn.isEnabled())

    def test_clear_forgets_the_last_result(self):
        """Anything that re-renders would otherwise resurrect the list."""
        self.win.begin_scan(1)
        self.win._last_result = object()
        self.win.clear()
        self.assertIsNone(self.win._last_result)

    def test_the_stream_fields_exist_before_any_scan(self):
        """A pilot arriving without a preceding STAGE_SCANNING used to raise
        AttributeError on _stream_done."""
        from core import cyno_sets
        from ui.results_window import ResultsWindow
        fresh = ResultsWindow(cyno_sets.load())
        self.assertEqual(0, fresh._stream_done)
        self.assertEqual([], fresh._stream_keys)


class TestNotice(WindowCase):
    """The "requests go out unsigned" line, which used to be a balloon."""

    def tearDown(self):
        self.win.set_notice()

    def test_the_notice_shows_beside_the_hint(self):
        self.win._say("scanning")
        self.win.set_notice("unsigned", "the long version")
        self.assertIn("unsigned", self.win.hint.text())
        self.assertIn("scanning", self.win.hint.text())

    def test_the_long_form_is_the_tooltip(self):
        self.win.set_notice("unsigned", "the long version")
        self.assertEqual("the long version", self.win.hint.toolTip())

    def test_it_survives_the_next_message(self):
        """It stands until it is taken away, not until the next line."""
        self.win.set_notice("unsigned", "")
        self.win._say("checked 3 of 9")
        self.assertIn("unsigned", self.win.hint.text())

    def test_an_empty_call_takes_it_away(self):
        self.win.set_notice("unsigned", "tip")
        self.win.set_notice()
        self.win._say("idle")
        self.assertEqual("idle", self.win.hint.text())

    def test_the_hint_always_has_a_tooltip(self):
        """It carries an Ignored size policy and really is clipped on a narrow
        window, so the tooltip is the only way to read it."""
        self.win._say("a fairly long status line")
        self.assertTrue(self.win.hint.toolTip())


class TestContactsRow(WindowCase):
    def test_the_handles_come_from_the_one_module_that_owns_them(self):
        """Imported, not retyped: invariant 7 by import."""
        self.assertIs(results_window.DISCORD, about.DISCORD)
        self.assertIs(results_window.CHARACTER_URL, about.CHARACTER_URL)

    def test_every_contact_button_says_what_it_does(self):
        for btn in (self.win.discord_btn, self.win.telegram_btn,
                    self.win.eve_btn):
            self.assertTrue(btn.toolTip())
            self.assertNotIn("contact.", btn.toolTip())

    def test_the_handle_is_in_the_tooltip_not_the_caption(self):
        """A caption carrying the handle sets the window's minimum width."""
        self.assertNotIn(about.DISCORD, self.win.discord_btn.text())
        self.assertIn(about.DISCORD, self.win.discord_btn.toolTip())

    def test_copying_a_handle_announces_it_to_the_watcher(self):
        """Without this the handle comes back as a paste, the guard refuses
        it, and the refusal lands in the label that just said "copied"."""
        from core import clipboard
        self.win._copy_contact(about.DISCORD)
        self.assertTrue(clipboard._was_expected(about.DISCORD))


class TestTooltips(WindowCase):
    def test_every_button_in_the_topbar_has_one(self):
        for btn in (self.win.rescan_btn, self.win.clear_btn,
                    self.win.expand_btn, self.win.collapse_btn,
                    self.win.filters_btn, self.win.on_top_btn):
            self.assertTrue(btn.toolTip(), btn.objectName())

    def test_no_tooltip_is_a_bare_key(self):
        """A missing key renders as `tip.clear`, which is visible but useless."""
        for btn in (self.win.rescan_btn, self.win.clear_btn,
                    self.win.expand_btn, self.win.collapse_btn):
            for prefix in ("tip.", "btn."):
                self.assertNotIn(prefix, btn.toolTip())

    def test_the_header_numbers_are_labelled(self):
        self.win._set_counts({"cyno": 2})
        tip = self.win._count_labels["cyno"].toolTip()
        self.assertTrue(tip)
        self.assertIn(i18n.t("level.cyno"), tip)

    def test_the_two_places_that_set_a_count_tooltip_agree(self):
        """_label_widgets sets it once, _set_counts on every update. Two
        copies of the format string is how they drift."""
        self.win._set_counts({"hull": 1})
        self.assertEqual(results_window._count_tip("hull"),
                         self.win._count_labels["hull"].toolTip())


class TestIconColumns(WindowCase):
    def test_the_two_icon_columns_have_their_own_delegates(self):
        """One delegate on both columns is what made ships and modules share
        a gap in the first place."""
        modules = self.win.tree.itemDelegateForColumn(
            results_window._COL_MODULES)
        ships = self.win.tree.itemDelegateForColumn(
            results_window._COL_SHIPS)
        self.assertIsNot(modules, ships)
        self.assertEqual(IconRowDelegate.GAP, modules.gap)
        self.assertEqual(IconRowDelegate.GAP_TIGHT, ships.gap)

    def test_a_new_icon_is_forgotten_by_both(self):
        """The delegate that was not told keeps drawing the old scale."""
        for delegate in self.win._delegates:
            delegate._scaled[12345] = object()
        self.win._on_icon_ready(12345)
        for delegate in self.win._delegates:
            self.assertNotIn(12345, delegate._scaled)


class TestBackground(WindowCase):
    def test_no_strip_of_the_window_is_left_unpainted(self):
        """`QWidget` is transparent in the QSS so panels can sit on whatever
        is beneath them -- but a strip belonging to no widget at all (the
        margin round the tree, the row the hint sits in) then paints nothing
        whatsoever. The central widget is named and given a background for
        exactly this; without it those rows come out fully transparent."""
        self.win.show()
        self.win.resize(700, 250)
        for _ in range(4):
            self.app.processEvents()
        image = self.win.grab().toImage()
        clear = [y for y in range(self.win.height())
                 if (image.pixel(self.win.width() // 2, y) >> 24) != 255]
        self.assertEqual([], clear[:10])


class TestBackdrop(WindowCase):
    """The picture an idle window shows, and the places it must not appear."""

    def setUp(self):
        self.win.show()
        self.win.resize(700, 420)
        self.pump()

    def tearDown(self):
        self.win.clear()
        self.pump()

    def pump(self):
        for _ in range(5):
            self.app.processEvents()

    def viewport_shot(self):
        return self.win.tree.viewport().grab().toImage()

    def test_an_empty_list_shows_the_picture(self):
        image = self.viewport_shot()
        seen = {image.pixel(x, y) for x in range(0, image.width(), 7)
                for y in range(0, image.height(), 7)}
        self.assertGreater(len(seen), 50)

    def test_rows_get_a_flat_panel_and_not_artwork(self):
        """A pilot's name is the verdict -- it is never read against a
        picture. The backdrop is what an EMPTY window shows, so one row is
        enough to take it away entirely."""
        from PySide6.QtWidgets import QTreeWidgetItem
        self.win.tree.addTopLevelItem(QTreeWidgetItem(["someone", "", ""]))
        self.pump()
        image = self.viewport_shot()
        low = image.height() - 20            # well below the single row
        seen = {image.pixel(x, low) for x in range(0, image.width(), 7)}
        self.assertEqual(1, len(seen))

    def test_clearing_brings_it_back(self):
        """Nothing in the window watches the row count: the model's own
        repaint is what redraws the viewport. If that ever stops being true,
        Clear leaves a flat rectangle."""
        from PySide6.QtWidgets import QTreeWidgetItem
        self.win.tree.addTopLevelItem(QTreeWidgetItem(["someone", "", ""]))
        self.pump()
        self.win.clear()
        self.pump()
        image = self.viewport_shot()
        seen = {image.pixel(x, y) for x in range(0, image.width(), 7)
                for y in range(0, image.height(), 7)}
        self.assertGreater(len(seen), 50)

    def test_a_missing_picture_is_not_an_error(self):
        """Same contract as the logo: no asset, no feature, no crash."""
        keep = self.win._backdrop
        try:
            self.win._backdrop = None
            self.win.tree.viewport().update()
            self.pump()
            image = self.viewport_shot()
            seen = {image.pixel(x, y) for x in range(0, image.width(), 11)
                    for y in range(0, image.height(), 11)}
            self.assertEqual(1, len(seen))
        finally:
            self.win._backdrop = keep


class TestBackdropScaling(WindowCase):
    def test_it_fills_the_viewport_exactly(self):
        """Cover-and-crop, not fit: a letterboxed picture in a dark window
        reads as a rendering bug rather than as a background."""
        pix = self.win._cover(400, 120)
        self.assertEqual((400, 120), (pix.width(), pix.height()))

    def test_the_same_size_is_not_rescaled_twice(self):
        """A repaint happens on every hover. Rescaling 1440x760 each time is
        real work for a picture that has not changed."""
        first = self.win._cover(300, 200)
        self.assertIs(first, self.win._cover(300, 200))

    def test_a_new_size_rebuilds_it(self):
        self.win._cover(300, 200)
        self.assertEqual((301, 200), (self.win._cover(301, 200).width(),
                                      self.win._cover(301, 200).height()))


class TestMinimumWidth(WindowCase):
    """A ceiling, not an equality.

    An equality would fail on any machine whose fonts or DPI differ from this
    one, CI included. A generous ceiling still catches the failure worth
    catching: somebody puts a wide label in the topbar and the window can no
    longer be made narrow. Measured 2026-08-23: 318 px, set by the contacts
    row (the topbar needs 282).
    """

    def test_the_window_still_gets_out_of_the_way(self):
        self.win.show()
        self.app.processEvents()
        self.win.resize(100, 400)
        self.app.processEvents()
        self.assertLessEqual(self.win.width(), 380)

    def test_the_shrinkable_widgets_are_still_visible_when_there_is_room(self):
        """The bug behind "bring the Check clipboard button back".

        `_let_it_shrink` used an Ignored size policy, and an Ignored widget
        beside a stretch does not get "its hint when there is room" -- its
        hint is discarded and it gets nothing. The title and the hint were
        0 px wide at every window size, not merely on a narrow one.
        """
        self.win.show()
        self.win.resize(900, 400)
        for _ in range(3):
            self.app.processEvents()
        self.assertGreater(self.win.title.width(), 50)
        self.assertGreater(self.win.hint.width(), 50)

    def test_they_still_let_the_window_shrink(self):
        """The other half: a minimum of 0 is silently ignored by Qt, so the
        label's own hint would become the floor again."""
        self.win.show()
        self.win.resize(100, 400)
        for _ in range(3):
            self.app.processEvents()
        self.assertLess(self.win.title.width(), 50)

    def test_the_action_buttons_do_not_vanish_when_it_is_narrow(self):
        """The complaint that started this: "Check clipboard" carried an
        Ignored size policy so the window could shrink, and below ~350 px it
        was squeezed out of existence. A 28 px square cannot be."""
        self.win.show()
        self.app.processEvents()
        self.win.resize(100, 400)
        self.app.processEvents()
        self.assertEqual(28, self.win.rescan_btn.width())
        self.assertEqual(28, self.win.clear_btn.width())


if __name__ == "__main__":
    unittest.main()
