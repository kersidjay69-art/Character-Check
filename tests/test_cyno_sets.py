"""The SDE artifact and what the runtime asks of it. No network."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cyno_sets  # noqa: E402

FALCON = 11957      # Force Recon    -- takes plain AND covert
HOUND = 12034       # Stealth Bomber -- covert only
BADGER = 648        # Hauler         -- industrial only
PROWLER = 12735     # Blockade Runner -- covert AND industrial
LOKI = 29990        # Strategic Cruiser, Tech III
RIFTER = 587        # Tech I, not a cyno hull
VELATOR = 606       # rookie corvette, no meta group at all
CHARON = 20185      # freighter

PLAIN_CYNO, COVERT_CYNO, INDY_CYNO = 21096, 28646, 52694


class TestCanFit(unittest.TestCase):
    """The rule that retired every pre-rebalance fit."""

    @classmethod
    def setUpClass(cls):
        cls.sets = cyno_sets.load()

    def test_a_hull_takes_the_modules_it_is_listed_with(self):
        self.assertTrue(self.sets.can_fit(FALCON, PLAIN_CYNO))
        self.assertTrue(self.sets.can_fit(FALCON, COVERT_CYNO))
        self.assertTrue(self.sets.can_fit(HOUND, COVERT_CYNO))
        self.assertTrue(self.sets.can_fit(BADGER, INDY_CYNO))
        self.assertTrue(self.sets.can_fit(PROWLER, COVERT_CYNO))
        self.assertTrue(self.sets.can_fit(PROWLER, INDY_CYNO))

    def test_a_cyno_hull_still_refuses_the_wrong_variant(self):
        """The subtle half: the ship is cyno-capable, the module is not its own.

        20 stored findings had a plain Cyno I on a Manticore -- legal before
        the rebalance, impossible now.
        """
        self.assertFalse(self.sets.can_fit(HOUND, PLAIN_CYNO))
        self.assertFalse(self.sets.can_fit(HOUND, INDY_CYNO))
        self.assertFalse(self.sets.can_fit(BADGER, PLAIN_CYNO))
        self.assertFalse(self.sets.can_fit(FALCON, INDY_CYNO))

    def test_a_non_cyno_hull_takes_nothing(self):
        for hull in (RIFTER, VELATOR, CHARON):
            for mod in (PLAIN_CYNO, COVERT_CYNO, INDY_CYNO):
                self.assertFalse(self.sets.can_fit(hull, mod),
                                 "%d/%d" % (hull, mod))

    def test_unknown_ids_do_not_raise(self):
        self.assertFalse(self.sets.can_fit(999999, PLAIN_CYNO))
        self.assertFalse(self.sets.can_fit(FALCON, 999999))

    def test_every_hull_can_fit_at_least_one_module(self):
        """Otherwise it had no business being in the hull set."""
        for tid, hull in self.sets.hulls.items():
            self.assertTrue(hull["modules"], hull["name"])
            self.assertTrue(
                any(self.sets.can_fit(tid, m) for m in hull["modules"]),
                hull["name"])


class TestMetaGroups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sets = cyno_sets.load()

    def test_tech_tiers_are_reported(self):
        self.assertEqual(2, self.sets.meta_group(FALCON))
        self.assertEqual(2, self.sets.meta_group(HOUND))
        self.assertEqual(14, self.sets.meta_group(LOKI))

    def test_tech_one_and_rookies_carry_no_badge(self):
        """Tech I and NULL are omitted from the artifact on purpose -- there is
        no badge to draw, so storing them would only pad the file."""
        self.assertIsNone(self.sets.meta_group(RIFTER))
        self.assertIsNone(self.sets.meta_group(VELATOR))
        self.assertIsNone(self.sets.meta_group(999999))

    def test_artifact_carries_meta_groups(self):
        with open(cyno_sets._DEFAULT, encoding="utf-8") as fh:
            raw = json.load(fh)
        self.assertIn("meta_groups", raw)
        self.assertTrue(raw["meta_groups"])
        self.assertNotIn(1, set(raw["meta_groups"].values()))

    def test_every_meta_group_id_belongs_to_a_ship(self):
        for tid in self.sets.meta_groups:
            self.assertTrue(self.sets.is_ship(tid), tid)


if __name__ == "__main__":
    unittest.main()
