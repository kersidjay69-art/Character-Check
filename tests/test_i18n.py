"""The translation tables. The important test is that they agree."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import config, i18n  # noqa: E402


class TestTablesAgree(unittest.TestCase):
    """One forgotten key is the whole failure mode of a hand-written table."""

    def test_both_languages_have_the_same_keys(self):
        missing_ru = set(i18n.EN) - set(i18n.RU)
        missing_en = set(i18n.RU) - set(i18n.EN)
        self.assertEqual(set(), missing_ru, "no Russian for: %s" % missing_ru)
        self.assertEqual(set(), missing_en, "no English for: %s" % missing_en)

    def test_format_placeholders_match_per_key(self):
        """A key that takes two numbers in one language must take two in the
        other, or the switch turns into a crash on the next scan."""
        spec = re.compile(r"%[-#0-9. +]*[a-zA-Z]")
        for key, en_text in i18n.EN.items():
            self.assertEqual(
                sorted(spec.findall(en_text)),
                sorted(spec.findall(i18n.RU[key])),
                "placeholders differ for %r" % key)

    def test_nothing_is_blank(self):
        for table, name in ((i18n.EN, "EN"), (i18n.RU, "RU")):
            for key, text in table.items():
                self.assertTrue(text.strip(), "%s[%r] is blank" % (name, key))


class TestLookup(unittest.TestCase):
    def setUp(self):
        self._prev = i18n.language()

    def tearDown(self):
        i18n.set_language(self._prev)

    def test_default_is_english(self):
        self.assertEqual("en", i18n.DEFAULT)
        self.assertEqual("en", config.DEFAULTS["lang"])

    def test_switching_changes_the_answer(self):
        i18n.set_language("en")
        self.assertEqual("CYNO", i18n.t("level.cyno"))
        i18n.set_language("ru")
        self.assertEqual("ЦИНО", i18n.t("level.cyno"))

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual("en", i18n.set_language("klingon"))
        self.assertEqual("en", i18n.set_language(None))

    def test_unknown_key_returns_itself_rather_than_raising(self):
        """A missing key should be visible in the UI, not fatal to it."""
        self.assertEqual("no.such.key", i18n.t("no.such.key"))
        self.assertEqual("no.such.key", i18n.t("no.such.key", 1, 2))

    def test_bad_arguments_do_not_raise(self):
        i18n.set_language("en")
        self.assertTrue(i18n.t("status.pilots", "not", "numbers"))
        self.assertTrue(i18n.t("status.pilots"))

    def test_en_helper_ignores_the_active_language(self):
        """Log lines stay English even when the window is Russian."""
        i18n.set_language("ru")
        self.assertEqual("empty", i18n.en("reason.empty"))
        self.assertEqual("ЦИНО", i18n.t("level.cyno"))

    def test_every_level_and_kind_has_a_label(self):
        from core import analyze
        for lv in (analyze.LEVEL_CYNO, analyze.LEVEL_HULL,
                   analyze.LEVEL_INDY, analyze.LEVEL_NONE):
            self.assertIn("level." + lv, i18n.EN)
        for kind in (analyze.KIND_FITTED, analyze.KIND_CARGO,
                     analyze.KIND_HULL_LOST, analyze.KIND_HULL_FLOWN):
            self.assertIn("kind." + kind, i18n.EN)


class TestGuardReasonsAreKeyed(unittest.TestCase):
    """Refusals must carry a key, or the window cannot translate them."""

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

    def test_reason_text_stays_english_under_a_russian_ui(self):
        from core import guard
        prev = i18n.language()
        try:
            i18n.set_language("ru")
            r = guard.inspect("")
            self.assertEqual("empty", r.reason)
            self.assertEqual("пусто", i18n.t(r.reason_key))
        finally:
            i18n.set_language(prev)


if __name__ == "__main__":
    unittest.main()
