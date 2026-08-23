"""The safety catch. The most important test file in the project: a guard that
is too tight makes the tool useless, one that is too loose fires ESI requests
on every copy-paste the user makes all day.

The mask is validated against tests/fixtures/real_names.txt -- 329 genuine
character names harvested from this machine's EVE chat logs.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.guard import (  # noqa: E402
    GuardResult, MAX_NAME_LEN, inspect, looks_like_name, normalize,
)

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load_real_names():
    with open(os.path.join(FIX, "real_names.txt"), encoding="utf-8") as fh:
        return [ln.strip() for ln in fh if ln.strip()]


OWN = ("Leya Sokard", "Freya Jay", "Misolara")

LOCAL_PASTE = """Leya Sokard
Falcon Punchline
Zhang Wei
冰喵
Io ''Midnight'' Shadow
599847624
Al-Avari"""

DSCAN = """122351\tRapier\tRapier\t12 km
122352\tFalcon\tFalcon\t- """

EFT_FIT = """[Falcon, Covert Bait]
Damage Control II
Covert Cynosural Field Generator I"""

CODE = """def analyze(km, char_id):
    return [f for f in km['victim']['items'] if f['flag'] == 27]"""

RUSSIAN = """Привет, я вчера потерял фалькон в лоу
надо будет пересобрать фит"""

URL_TEXT = "https://zkillboard.com/character/93872166/"


class TestNameMask(unittest.TestCase):
    def test_every_real_harvested_name_passes(self):
        """329 names taken from real chat logs. Regressions here mean the
        tool starts ignoring real pilots in local."""
        names = load_real_names()
        self.assertGreater(len(names), 300)
        bad = [n for n in names if not looks_like_name(n)]
        self.assertEqual([], bad, "mask rejected real character names")

    def test_cjk_names_pass(self):
        """28% of harvested names are CJK -- a Latin-only mask would drop a
        quarter of every local list."""
        for n in ("冰喵", "幻华 琉璃", "躺着看", "吉他大富翁"):
            self.assertTrue(looks_like_name(n), n)

    def test_digit_only_name_passes(self):
        self.assertTrue(looks_like_name("599847624"))

    def test_repeated_apostrophes_pass(self):
        self.assertTrue(looks_like_name("Io ''Midnight'' Shadow"))

    def test_hyphen_and_apostrophe_pass(self):
        for n in ("Al-Avari", "Ki'Yong", "Silky-Kitty E", "Planet-earth"):
            self.assertTrue(looks_like_name(n), n)

    def test_cyrillic_is_not_a_name(self):
        self.assertFalse(looks_like_name("Привет всем"))

    def test_length_bounds(self):
        self.assertFalse(looks_like_name("a"))
        self.assertTrue(looks_like_name("ab"))
        self.assertTrue(looks_like_name("x" * MAX_NAME_LEN))
        self.assertFalse(looks_like_name("x" * (MAX_NAME_LEN + 1)))

    def test_at_most_three_words(self):
        self.assertTrue(looks_like_name("One Two Three"))
        self.assertFalse(looks_like_name("One Two Three Four"))

    def test_punctuation_edges_rejected(self):
        for n in ("-Nope", "Nope-", "'Nope", "Nope'", " Nope", "Nope "):
            self.assertFalse(looks_like_name(n), n)

    def test_forbidden_characters(self):
        for n in ("a.b", "a_b", 'a"b', "a/b", "a,b", "a(b)", "a@b", "a|b"):
            self.assertFalse(looks_like_name(n), n)


class TestNormalize(unittest.TestCase):
    def test_crlf_blanks_bom_and_dupes(self):
        got = normalize("﻿Alpha\r\n\r\n  Beta  \nalpha\nGamma\n")
        self.assertEqual(["Alpha", "Beta", "Gamma"], got)

    def test_dedupe_is_case_insensitive(self):
        self.assertEqual(["Bob"], normalize("Bob\nBOB\nbob"))


class TestInspectAccepts(unittest.TestCase):
    def test_local_paste_accepted_as_list(self):
        r = inspect(LOCAL_PASTE, own_names=OWN)
        self.assertTrue(r.accepted)
        self.assertEqual("list", r.mode)
        self.assertIn("Zhang Wei", r.names)

    def test_own_character_is_excluded_from_the_scan(self):
        r = inspect(LOCAL_PASTE, own_names=OWN)
        self.assertEqual(("Leya Sokard",), r.own_seen)
        self.assertNotIn("Leya Sokard", r.names)

    def test_own_character_rescues_a_partly_malformed_paste(self):
        """A truncated copy or a stray UI line should not lose the whole
        paste when your own pilot is provably in it."""
        text = "Leya Sokard\nZhang Wei\nsome junk line with, commas\nmore. junk\nyet_more junk"
        r = inspect(text, own_names=OWN)
        self.assertTrue(r.accepted)
        self.assertIn("Zhang Wei", r.names)

    def test_single_name_accepted_in_single_mode(self):
        r = inspect("Zhang Wei")
        self.assertTrue(r.accepted)
        self.assertEqual("single", r.mode)
        self.assertEqual(("Zhang Wei",), r.names)

    def test_list_without_own_character_still_accepted(self):
        r = inspect("Zhang Wei\nFalcon Punchline\n冰喵")
        self.assertTrue(r.accepted)
        self.assertEqual("list", r.mode)

    def test_real_local_paste_is_fully_accepted(self):
        """A genuine 49-pilot local member list copied out of the game.
        Every line must survive: lowercase starts (jonathan quintero),
        digits (Reflex8755), hyphens (wuyou-06), three-word names
        (Jorvunen Suun Parmala) and all-caps (STAN PSHEN)."""
        with open(os.path.join(FIX, "local_paste_real.txt"), encoding="utf-8") as fh:
            text = fh.read()
        expected = len([ln for ln in text.splitlines() if ln.strip()])
        r = inspect(text)
        self.assertTrue(r.accepted, r.reason)
        self.assertEqual("list", r.mode)
        self.assertEqual(expected, len(r.names))

    def test_hub_sized_local_is_accepted(self):
        """A real paste from a trade hub ran to ~1100 names. The first cap of
        250 rejected it outright -- exactly the case where the tool matters
        most. Breadth is cheap; depth is what stays small for big pastes."""
        names = ["Pilot%04d" % i for i in range(1100)]
        r = inspect("\n".join(names))
        self.assertTrue(r.accepted, r.reason)
        self.assertEqual(1100, len(r.names))

    def test_trailing_signature_line_is_dropped_not_fatal(self):
        """That same paste ended with a Cyrillic note the user had typed. One
        bad line in a thousand must neither lose the paste nor be scanned."""
        text = "\n".join(["Pilot%04d" % i for i in range(200)] + ["стресс тест"])
        r = inspect(text)
        self.assertTrue(r.accepted)
        self.assertNotIn("стресс тест", r.names)

    def test_one_bad_line_in_twenty_is_tolerated(self):
        lines = ["Pilot%02d" % i for i in range(19)] + ["bad, line"]
        r = inspect("\n".join(lines))
        self.assertTrue(r.accepted)


class TestInspectRejects(unittest.TestCase):
    def assertRejected(self, text, own=()):
        r = inspect(text, own_names=own)
        self.assertFalse(r.accepted, "should have been rejected: %r" % text[:60])
        self.assertEqual("rejected", r.mode)
        self.assertTrue(r.reason)
        return r

    def test_dscan_rejected_by_tabs(self):
        r = self.assertRejected(DSCAN)
        self.assertIn("tab", r.reason)

    def test_eft_fit_rejected(self):
        self.assertRejected(EFT_FIT)

    def test_url_rejected(self):
        r = self.assertRejected(URL_TEXT)
        self.assertIn("URL", r.reason)

    def test_code_rejected(self):
        self.assertRejected(CODE)

    def test_russian_prose_rejected(self):
        self.assertRejected(RUSSIAN)

    def test_empty_rejected(self):
        self.assertRejected("")
        self.assertRejected("   \n\n  ")

    def test_too_many_lines_rejected(self):
        from core.guard import MAX_LINES
        self.assertRejected("\n".join("Pilot%05d" % i
                                      for i in range(MAX_LINES + 10)))

    def test_huge_text_rejected(self):
        """Distinct lines on purpose: normalize() de-duplicates, so repeating
        one name collapses to a single line and tests nothing."""
        from core.guard import MAX_CHARS
        text = "\n".join("Pilot%06d" % i for i in range(MAX_CHARS // 4))
        self.assertGreater(len(text), MAX_CHARS)
        self.assertRejected(text)

    def test_only_own_characters_rejected(self):
        """Copying your own fleet's names should not raise an alarm on
        yourself."""
        self.assertRejected("Leya Sokard\nFreya Jay", own=OWN)

    def test_sentence_rejected(self):
        self.assertRejected("hey does anyone have a spare falcon in jita")

    def test_isk_amount_rejected(self):
        self.assertRejected("1,500,000,000")

    def test_guard_result_is_falsy_when_rejected(self):
        self.assertFalse(bool(inspect(CODE)))
        self.assertTrue(bool(inspect("Zhang Wei")))


class TestNoNetworkContract(unittest.TestCase):
    def test_guard_module_imports_nothing_networked(self):
        """Stage 1-3 must be free. If guard ever grows an HTTP import, every
        stray copy in the user's day becomes a request."""
        import core.guard as g
        with open(g.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for bad in ("import requests", "import httpx", "import urllib",
                    "import socket", "from urllib"):
            self.assertNotIn(bad, src)


if __name__ == "__main__":
    unittest.main()
