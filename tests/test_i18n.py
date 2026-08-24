"""The interface strings. One table now, English, and the tests changed shape.

Until 2026-08-23 there were two tables and the important test was that they
agreed -- a key present in one and missing from the other was the whole failure
mode of a hand-written translation. With one table that class of bug cannot
happen, so what is left to check is the lookup's promise: it never raises, and
every level, kind and refusal the code can produce has a label to show.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import i18n  # noqa: E402


class TestTable(unittest.TestCase):
    def test_nothing_is_blank(self):
        for key, text in i18n.EN.items():
            self.assertTrue(text.strip(), "EN[%r] is blank" % key)

    def test_no_key_is_left_pointing_at_a_language_switch(self):
        """The Russian table is gone; nothing may quietly expect it back."""
        self.assertFalse(hasattr(i18n, "RU"))
        self.assertFalse(hasattr(i18n, "TABLES"))
        self.assertFalse(hasattr(i18n, "set_language"))

    def test_every_placeholder_is_one_the_lookup_can_fill(self):
        """`t()` formats with a plain tuple, so `%(name)s` would always fail.

        This is what is left of the old cross-table placeholder check: the
        risk was never the letters, it was a format string nobody can satisfy.
        """
        named = re.compile(r"%\([^)]*\)")
        for key, text in i18n.EN.items():
            self.assertIsNone(named.search(text),
                              "%r uses a named placeholder" % key)


class TestLookup(unittest.TestCase):
    def test_unknown_key_returns_itself_rather_than_raising(self):
        """A missing key should be visible in the UI, not fatal to it."""
        self.assertEqual("no.such.key", i18n.t("no.such.key"))
        self.assertEqual("no.such.key", i18n.t("no.such.key", 1, 2))

    def test_bad_arguments_do_not_raise(self):
        self.assertTrue(i18n.t("status.progress", "not", "numbers"))
        self.assertTrue(i18n.t("status.progress"))

    def test_every_level_and_kind_has_a_label(self):
        from core import analyze
        for lv in (analyze.LEVEL_CYNO, analyze.LEVEL_HULL,
                   analyze.LEVEL_INDY, analyze.LEVEL_NONE):
            self.assertIn("level." + lv, i18n.EN)
        for kind in (analyze.KIND_FITTED, analyze.KIND_CARGO,
                     analyze.KIND_HULL_LOST, analyze.KIND_HULL_FLOWN):
            self.assertIn("kind." + kind, i18n.EN)


class TestGuardReasonsAreKeyed(unittest.TestCase):
    """Refusals must carry a key as well as a sentence.

    `reason` is the finished line that goes into the log; `reason_key` plus
    `reason_args` let the window build its own, because it puts the refusal
    beside other text in the hint. That split survived the language removal --
    it was never really about language.
    """

    def test_every_rejection_has_a_key_and_english_text(self):
        from core import guard
        cases = ["", "a\tb", "see https://example.com/x", "x" * 70000,
                 "\n".join("name %d" % i for i in range(2000)),
                 "\n".join("!!!" for _ in range(20))]
        for text in cases:
            r = guard.inspect(text)
            self.assertFalse(r.accepted, repr(text[:20]))
            self.assertTrue(r.reason_key, repr(text[:20]))
            self.assertIn(r.reason_key, i18n.EN, r.reason_key)
            self.assertTrue(r.reason)

    def test_the_sentence_and_the_key_say_the_same_thing(self):
        from core import guard
        r = guard.inspect("")
        self.assertEqual("empty", r.reason)
        self.assertEqual("empty", i18n.t(r.reason_key))


if __name__ == "__main__":
    unittest.main()
