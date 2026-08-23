"""Tier logic, and one named test per trap found while verifying real data."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cyno_sets  # noqa: E402
from core.analyze import (  # noqa: E402
    KIND_CARGO, KIND_FITTED, KIND_HULL_FLOWN, KIND_HULL_LOST,
    LEVEL_CYNO, LEVEL_HULL, LEVEL_INDY, LEVEL_NONE, LEVEL_SEEN,
    ALL_CYNO, ALL_EVIDENCE, Filters, Finding, analyze_killmail,
    group_findings, is_quiet, level_of, modules_of, parse_km_time, ships_of,
)

CHAR = 90000001
OTHER = 90000002

COVERT_CYNO = 28646
PLAIN_CYNO = 21096      # Cynosural Field Generator I
INDY_CYNO = 52694
HOUND = 12034           # Stealth Bomber -- covert cyno only
HELIOS = 11172          # Covert Ops
BROADSWORD = 12013      # Heavy Interdiction Cruiser
PANTHER = 22440         # Black Ops
FALCON = 11957          # Force Recon Ship, group 833
VENTURE = 32880         # group 25 Frigate -- only via canFitShipType
RIFTER = 587            # group 25 Frigate -- must never be flagged
BADGER = 648            # Hauler, an INDY-class cyno hull
CHARON = 20185          # Freighter -- a real ship, but no cyno hull at all
PROWLER = 12735         # Blockade Runner -- takes covert AND industrial
BUZZARD = 11192         # Covert Ops -- a QUIET hull
LEGION = 29986          # Strategic Cruiser -- a QUIET hull
MARSHAL = 44996         # Black Ops -- loud, and the hull LIJaman lost once
IBIS = 601              # rookie ship, carried cynos before the rebalance
CAPSULE = 670
ROCKET = 27361          # a charge, to sit on a module's slot flag


def km(**kw):
    base = {"killmail_id": 1, "killmail_time": "2026-08-17T12:00:00Z",
            "solar_system_id": 30002510, "victim": {}, "attackers": []}
    base.update(kw)
    return base


def victim(char=CHAR, ship=FALCON, items=None):
    return {"character_id": char, "ship_type_id": ship, "items": items or []}


def item(type_id, flag, nested=None):
    d = {"item_type_id": type_id, "flag": flag, "quantity_destroyed": 1,
         "singleton": 0}
    if nested:
        d["items"] = nested
    return d


class TestAnalyze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sets = cyno_sets.load()

    def kinds(self, k, char=CHAR):
        return [f.kind for f in analyze_killmail(k, char, self.sets)]

    # --- the happy path -------------------------------------------------

    def test_fitted_combat_cyno_is_the_top_verdict(self):
        k = km(victim=victim(items=[item(COVERT_CYNO, 27)]))
        f = analyze_killmail(k, CHAR, self.sets)
        self.assertIn(KIND_FITTED, [x.kind for x in f])
        self.assertEqual(LEVEL_CYNO, level_of(f))
        self.assertEqual([COVERT_CYNO], modules_of(f))

    def test_all_high_slot_flags_count(self):
        for flag in range(27, 35):
            k = km(victim=victim(items=[item(COVERT_CYNO, flag)]))
            self.assertIn(KIND_FITTED, self.kinds(k), "flag %d" % flag)

    def test_combat_cyno_in_cargo_still_ranks_as_cyno(self):
        """Priority follows WHICH module was aboard, not whether it was
        fitted -- a covert cyno in the hold is the same threat one undock
        later."""
        k = km(victim=victim(items=[item(COVERT_CYNO, 5)]))
        f = analyze_killmail(k, CHAR, self.sets)
        kinds = [x.kind for x in f]
        self.assertIn(KIND_CARGO, kinds)
        self.assertNotIn(KIND_FITTED, kinds)
        self.assertEqual(LEVEL_CYNO, level_of(f))

    def test_hull_lost_without_module(self):
        k = km(victim=victim(ship=FALCON, items=[]))
        self.assertEqual([KIND_HULL_LOST], self.kinds(k))

    def test_hull_flown_as_attacker(self):
        k = km(victim=victim(char=OTHER, ship=CAPSULE),
               attackers=[{"character_id": CHAR, "ship_type_id": FALCON}])
        self.assertEqual([KIND_HULL_FLOWN], self.kinds(k))

    # --- trap 1: nested items inherit high-slot flags --------------------

    def test_trap_nested_depth1_hislot_is_not_fitted(self):
        """A fitted recon inside a Ship Maintenance Bay yields flag 28 at
        depth 1. Counting it as `fitted` would flag every hauler carrying one.

        The victim is a hull that CAN mount a covert cyno, otherwise the
        compatibility gate would reject the item first and this test would
        pass without ever exercising the depth rule.
        """
        k = km(victim=victim(
            ship=FALCON,
            items=[item(FALCON, 155, nested=[item(COVERT_CYNO, 28)])]))
        kinds = self.kinds(k)
        self.assertNotIn(KIND_FITTED, kinds)
        self.assertIn(KIND_CARGO, kinds)

    def test_freighter_hauling_a_fitted_recon_yields_nothing_at_all(self):
        """The original shape of trap 1, now caught one step earlier.

        A freighter cannot mount any cyno, so the nested module is dropped by
        the compatibility gate before the depth rule is even consulted. Two
        independent reasons to ignore it, which is what we want here.
        """
        k = km(victim=victim(
            ship=CHARON,
            items=[item(FALCON, 155, nested=[item(COVERT_CYNO, 28)])]))
        self.assertEqual([], self.kinds(k))

    # --- trap 2: a flag is not unique per slot ---------------------------

    def test_trap_charge_sharing_module_flag_is_ignored(self):
        """Loaded ammo carries its module's slot flag. Only the cyno type_id
        may produce a finding, never the flag on its own."""
        k = km(victim=victim(items=[item(ROCKET, 27), item(COVERT_CYNO, 27)]))
        f = analyze_killmail(k, CHAR, self.sets)
        fitted = [x for x in f if x.kind == KIND_FITTED]
        self.assertEqual(1, len(fitted))
        self.assertEqual(COVERT_CYNO, fitted[0].module_type_id)

    def test_trap_non_cyno_item_in_hislot_alone_is_not_evidence(self):
        k = km(victim=victim(ship=CAPSULE, items=[item(ROCKET, 27)]))
        self.assertEqual([], self.kinds(k))

    # --- trap 3: groups vs individual types ------------------------------

    def test_trap_venture_is_a_hull_by_type_not_group(self):
        """Membership is by type. Venture is in the set, its groupmates are not.

        The module finding is what proves it: `can_fit` only says yes for a
        hull the artifact lists, so a fitted industrial cyno here IS the
        membership check.

        No `hull_lost` is expected any more -- a bare industrial hull stopped
        being recorded at all. That is a deliberate reversal, not a regression:
        see `_hull_is_evidence`. The trap this test guards is a different one
        and is still live.
        """
        k = km(victim=victim(ship=VENTURE, items=[item(INDY_CYNO, 27)]))
        kinds = self.kinds(k)
        self.assertIn(KIND_FITTED, kinds)
        self.assertNotIn(KIND_HULL_LOST, kinds)
        self.assertTrue(self.sets.is_hull(VENTURE))

    def test_trap_rifter_shares_ventures_group_but_is_clean(self):
        """Venture is groupID 25 'Frigate'. If the artifact had expanded that
        group, every T1 frigate in the game would be a cyno hull."""
        k = km(victim=victim(ship=RIFTER))
        self.assertEqual([], self.kinds(k))
        self.assertFalse(self.sets.is_hull(RIFTER))

    # --- level calibration, measured on a 1547-pilot hub scan -------------

    def test_industrial_cyno_ranks_below_a_bare_combat_hull(self):
        """The ordering the user asked for: a fitted industrial cyno is a
        weaker signal than a combat hull with no module at all, because it
        bridges only jump freighters and the Rorqual."""
        indy = analyze_killmail(
            km(victim=victim(ship=VENTURE, items=[item(INDY_CYNO, 27)])),
            CHAR, self.sets)
        hull = analyze_killmail(
            km(victim=victim(ship=FALCON, items=[])), CHAR, self.sets)
        self.assertEqual(LEVEL_INDY, level_of(indy))
        self.assertEqual(LEVEL_HULL, level_of(hull))

    def test_industrial_hull_alone_is_clean(self):
        """A lost Venture with nothing aboard is a miner, not a scout.

        842 of the flags in the 1547-pilot hub scan were exactly this, which is
        why a bare industrial hull stopped being evidence at all. The hull only
        speaks when a cyno was actually bolted onto it -- see the test below.
        """
        k = km(victim=victim(ship=VENTURE, items=[]))
        self.assertEqual(LEVEL_NONE, level_of(analyze_killmail(k, CHAR, self.sets)))

    def test_industrial_hull_with_a_fitted_cyno_still_counts(self):
        """The other half of the rule: the module is what talks."""
        k = km(victim=victim(ship=VENTURE, items=[item(INDY_CYNO, 27)]))
        self.assertEqual(LEVEL_INDY, level_of(analyze_killmail(k, CHAR, self.sets)))

    # --- cargo only counts on a hull built to light a cyno ----------------

    def test_cargo_cyno_on_a_combat_hull_counts_as_fitted(self):
        """A recon with a covert cyno in the hold unfitted it an undock ago."""
        k = km(victim=victim(ship=FALCON, items=[item(COVERT_CYNO, 5)]))
        f = analyze_killmail(k, CHAR, self.sets)
        self.assertIn(KIND_CARGO, [x.kind for x in f])
        self.assertEqual(LEVEL_CYNO, level_of(f))

    def test_cargo_cyno_on_a_freighter_is_freight(self):
        """A hauler moving a crate of cynos. It cannot mount one, so the
        evidence is not merely discounted -- it is never recorded."""
        k = km(victim=victim(ship=CHARON, items=[item(COVERT_CYNO, 5)]))
        f = analyze_killmail(k, CHAR, self.sets)
        self.assertEqual([], f)
        self.assertEqual(LEVEL_NONE, level_of(f))
        self.assertEqual([], modules_of(f))

    def test_cargo_cyno_on_an_industrial_hull_is_freight(self):
        k = km(victim=victim(ship=BADGER, items=[item(INDY_CYNO, 5)]))
        self.assertEqual(LEVEL_NONE,
                         level_of(analyze_killmail(k, CHAR, self.sets)))

    # --- the hull must be able to mount THAT cyno, today ------------------

    def test_fitted_cyno_on_a_hull_that_cannot_mount_it_is_ignored(self):
        """A REVERSED decision -- do not restore the old behaviour on sight.

        Cynos really were fitted to rookie frigates before canFitShipGroup
        existed, and this project deliberately counted those for a while. On
        real data that turned out to be 727 of 1493 stored module findings,
        and it put Velator and Myrmidon icons next to pilots who cannot light
        a cyno at all today. The killmail is genuine; what it predicts is
        nothing. Measured cost of the reversal: 13 pilots out of 1712 lost
        their only evidence and went clean.
        """
        for hull, label in ((IBIS, "rookie ship"), (CHARON, "freighter")):
            k = km(victim=victim(ship=hull, items=[item(COVERT_CYNO, 27)]))
            f = analyze_killmail(k, CHAR, self.sets)
            self.assertEqual([], f, label)
            self.assertEqual(LEVEL_NONE, level_of(f), label)

    def test_wrong_cyno_on_a_real_cyno_hull_is_ignored(self):
        """A Stealth Bomber takes only the covert variant.

        20 stored findings had a plain Cyno I fitted to a Manticore -- legal
        before the rebalance, impossible now. `hulls[id]["modules"]` has always
        listed exactly which module each hull accepts; nothing was reading it.
        """
        k = km(victim=victim(ship=HOUND, items=[item(PLAIN_CYNO, 27)]))
        f = analyze_killmail(k, CHAR, self.sets)
        # The module evidence is gone; the hull itself is still a cyno hull,
        # so the pilot stays yellow rather than disappearing.
        self.assertEqual([], modules_of(f))
        self.assertEqual([KIND_HULL_LOST], [x.kind for x in f])
        self.assertEqual(LEVEL_HULL, level_of(f))

    def test_right_cyno_on_the_same_hull_still_counts(self):
        """The other half -- the gate must not swallow legitimate evidence."""
        k = km(victim=victim(ship=HOUND, items=[item(COVERT_CYNO, 27)]))
        f = analyze_killmail(k, CHAR, self.sets)
        self.assertEqual(LEVEL_CYNO, level_of(f))
        self.assertEqual([COVERT_CYNO], modules_of(f))

    # --- which ships earn an icon ----------------------------------------

    def test_ships_of_skips_a_bare_industrial_hull(self):
        k = km(victim=victim(ship=VENTURE, items=[]))
        self.assertEqual([], ships_of(analyze_killmail(k, CHAR, self.sets)))

    def test_ships_of_keeps_an_industrial_hull_that_was_fitted(self):
        k = km(victim=victim(ship=BADGER, items=[item(INDY_CYNO, 27)]))
        self.assertEqual([BADGER], ships_of(analyze_killmail(k, CHAR, self.sets)))

    def test_ships_of_skips_an_industrial_hull_carrying_cargo(self):
        k = km(victim=victim(ship=BADGER, items=[item(INDY_CYNO, 5)]))
        self.assertEqual([], ships_of(analyze_killmail(k, CHAR, self.sets)))

    def test_ships_of_orders_combat_hulls_by_role(self):
        """Recons, Heavy Interdictors, the rest, industrials, quiet hulls.

        The industrial sits ABOVE the bare Helios on purpose: a Badger in this
        row means a cyno was fitted into it, which is evidence, while a Covert
        Ops flown empty means nothing at all.
        """
        def flown(km_id, ship):
            return Finding(km_id, KIND_HULL_FLOWN, 0.0, ship, None, None,
                           "combat")

        mix = [flown(1, HOUND),          # Stealth Bomber
               flown(2, PANTHER),        # Black Ops
               flown(3, FALCON),         # Force Recon
               flown(4, HELIOS),         # Covert Ops -- quiet
               flown(5, BROADSWORD),     # Heavy Interdiction Cruiser
               Finding(6, KIND_FITTED, 0.0, BADGER, INDY_CYNO, None, "indy")]
        self.assertEqual(
            [FALCON, BROADSWORD, HOUND, PANTHER, BADGER, HELIOS],
            ships_of(mix, self.sets))

    def test_ships_of_puts_combat_hulls_first(self):
        k = km(victim=victim(ship=BADGER, items=[item(INDY_CYNO, 27)]),
               attackers=[{"character_id": CHAR, "ship_type_id": FALCON}])
        self.assertEqual([FALCON, BADGER],
                         ships_of(analyze_killmail(k, CHAR, self.sets)))

    def test_regular_cyno_ranks_with_covert(self):
        for mod in (21096, 28646):
            k = km(victim=victim(ship=FALCON, items=[item(mod, 27)]))
            self.assertEqual(LEVEL_CYNO,
                             level_of(analyze_killmail(k, CHAR, self.sets)),
                             "module %d" % mod)

    def test_strongest_level_wins_across_findings(self):
        k = km(victim=victim(ship=VENTURE, items=[]),
               attackers=[{"character_id": CHAR, "ship_type_id": FALCON}])
        self.assertEqual(LEVEL_HULL, level_of(analyze_killmail(k, CHAR, self.sets)))

    def test_modules_of_orders_covert_then_plain_then_industrial(self):
        """Worst first, and "worst" is the covert one: it is the module that
        drops a fleet on you from a cloak. Ordering is by explicit rank, not
        by type_id -- 21096 sorts before 28646 numerically, which is backwards.

        Built from Findings directly: no single hull in the game accepts all
        three modules, so a killmail cannot express this case.
        """
        f = [Finding(1, KIND_FITTED, 0.0, FALCON, INDY_CYNO, None, "combat"),
             Finding(1, KIND_FITTED, 0.0, FALCON, PLAIN_CYNO, None, "combat"),
             Finding(1, KIND_FITTED, 0.0, FALCON, COVERT_CYNO, None, "combat")]
        self.assertEqual([COVERT_CYNO, PLAIN_CYNO, INDY_CYNO], modules_of(f))

    def test_modules_of_on_a_real_killmail(self):
        """A Blockade Runner is the widest real case: covert plus industrial."""
        k = km(victim=victim(ship=PROWLER,
                             items=[item(INDY_CYNO, 5), item(COVERT_CYNO, 27)]))
        self.assertEqual([COVERT_CYNO, INDY_CYNO],
                         modules_of(analyze_killmail(k, CHAR, self.sets)))

    def test_no_evidence_is_level_none(self):
        k = km(victim=victim(ship=RIFTER))
        self.assertEqual(LEVEL_NONE, level_of(analyze_killmail(k, CHAR, self.sets)))

    # --- boundaries -------------------------------------------------------

    def test_module_in_a_deployable_is_not_evidence(self):
        """Killmails exist for deployables too. A Mobile Tractor Unit (33475)
        that scooped a cyno off a wreck and then died was being counted as
        "cyno in cargo" for its owner -- caught on a real 2015 killmail."""
        MTU = 33475
        self.assertFalse(self.sets.is_ship(MTU))
        k = km(victim=victim(ship=MTU, items=[item(COVERT_CYNO, 5)]))
        self.assertEqual([], self.kinds(k))

    def test_module_on_a_real_ship_still_counts(self):
        self.assertTrue(self.sets.is_ship(FALCON))
        k = km(victim=victim(ship=FALCON, items=[item(COVERT_CYNO, 5)]))
        self.assertIn(KIND_CARGO, self.kinds(k))

    def test_capsule_is_a_ship(self):
        """The pod is category 6 and must not be swept up by the filter."""
        self.assertTrue(self.sets.is_ship(CAPSULE))

    def test_other_pilots_evidence_is_not_ours(self):
        k = km(victim=victim(char=OTHER, items=[item(COVERT_CYNO, 27)]))
        self.assertEqual([], self.kinds(k))

    def test_structure_victim_without_character_id(self):
        k = km(victim={"ship_type_id": FALCON, "items": []})
        self.assertEqual([], self.kinds(k))

    def test_missing_killmail_id_yields_nothing(self):
        k = km(victim=victim())
        del k["killmail_id"]
        self.assertEqual([], self.kinds(k))

    def test_fitted_module_not_reported_twice_as_cargo(self):
        k = km(victim=victim(items=[item(COVERT_CYNO, 27), item(COVERT_CYNO, 5)]))
        f = analyze_killmail(k, CHAR, self.sets)
        self.assertEqual(1, len([x for x in f if x.kind == KIND_FITTED]))
        self.assertEqual(0, len([x for x in f if x.kind == KIND_CARGO]))

    def test_victim_and_attacker_in_one_mail(self):
        """Self-inflicted or duplicated ids should still yield both facts."""
        k = km(victim=victim(items=[item(COVERT_CYNO, 27)]),
               attackers=[{"character_id": CHAR, "ship_type_id": FALCON}])
        kinds = self.kinds(k)
        self.assertIn(KIND_FITTED, kinds)
        self.assertIn(KIND_HULL_FLOWN, kinds)

    def test_parse_km_time_is_utc(self):
        self.assertEqual(1755432000.0, parse_km_time("2025-08-17T12:00:00Z"))
        self.assertEqual(0.0, parse_km_time(None))


class TestCynoSets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sets = cyno_sets.load()

    def test_the_three_modules(self):
        self.assertEqual({21096, 28646, 52694}, set(self.sets.modules))

    def test_late_numbered_canfit_attributes_were_picked_up(self):
        """28646 reaches Strategic Cruisers via attribute 1872 and Blockade
        Runners via 1879 -- both outside the usual 1298..1300 range."""
        by_group = {}
        for h in self.sets.hulls.values():
            by_group.setdefault(h["group_name"], set()).update(h["modules"])
        self.assertIn(28646, by_group.get("Strategic Cruiser", set()))
        self.assertIn(28646, by_group.get("Blockade Runner", set()))
        self.assertIn(28646, by_group.get("Stealth Bomber", set()))

    def test_structure_and_npc_cyno_are_absent(self):
        self.assertNotIn(35912, self.sets.modules)   # Standup, structure module
        self.assertNotIn(2852, self.sets.modules)    # Sansha Cynosural Field

    def test_type_only_hulls_did_not_drag_in_their_groups(self):
        groups = {}
        for tid, h in self.sets.hulls.items():
            groups.setdefault(h["group_name"], []).append(tid)
        self.assertEqual(2, len(groups.get("Frigate", [])))    # both Ventures
        self.assertEqual(2, len(groups.get("Logistics", [])))  # Etana, Rabisu

    def test_industrial_only_hulls_are_classed_indy(self):
        self.assertEqual("indy", self.sets.hull_class(32880))   # Venture
        self.assertEqual("combat", self.sets.hull_class(11957))  # Falcon
        self.assertEqual("combat", self.sets.hull_class(32790))  # Etana

    def test_any_ship_can_be_named_not_only_cyno_hulls(self):
        """Evidence A is not limited to today's cyno-capable hulls. Before CCP
        added the canFitShipGroup restriction, cynos were fitted to rookie
        frigates -- real killmails from 2014-2018 show Velator and Ibis. Those
        findings must still render a ship name, not "type 606"."""
        self.assertEqual("Velator", self.sets.hull_name(606))
        self.assertEqual("Ibis", self.sets.hull_name(601))
        self.assertFalse(self.sets.is_hull(606))
        self.assertTrue(self.sets.hull_name(999999999).startswith("type "))

    def test_load_rejects_an_empty_artifact(self):
        import json
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "empty.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"modules": {}, "hulls": {}}, fh)
        with self.assertRaises(ValueError):
            cyno_sets.load(path)


class TestQuietHulls(unittest.TestCase):
    """Covert Ops and Strategic Cruisers: cyno-capable, but no threat alone.

    Buzzard/Helios/Anathema/Cheetah are the explorer's frigates and
    Legion/Loki/Tengu/Proteus are the game's general-purpose cruiser. Pilots
    who have never lit a cyno fly them constantly, so a bare one scores `seen`
    -- shown, greyed, bottom of the list -- instead of the yellow warning it
    used to earn. Same reasoning that retired the bare Venture.
    """

    @classmethod
    def setUpClass(cls):
        cls.sets = cyno_sets.load()

    def _flown(self, ship):
        k = km(attackers=[{"character_id": CHAR, "ship_type_id": ship}])
        return analyze_killmail(k, CHAR, self.sets)

    def test_a_bare_covert_ops_is_seen_not_a_warning(self):
        f = self._flown(BUZZARD)
        self.assertEqual([KIND_HULL_FLOWN], [x.kind for x in f])
        self.assertEqual(LEVEL_SEEN, level_of(f))

    def test_a_bare_t3_cruiser_is_seen_not_a_warning(self):
        self.assertEqual(LEVEL_SEEN, level_of(self._flown(LEGION)))

    def test_a_loud_hull_is_still_a_warning(self):
        """The change is two groups wide, not a blanket demotion."""
        for ship in (FALCON, MARSHAL, HOUND, BROADSWORD):
            self.assertEqual(LEVEL_HULL, level_of(self._flown(ship)), ship)

    def test_a_cyno_fitted_to_a_quiet_hull_is_still_a_cyno(self):
        """The module rules run first and never consult the quiet set. A
        Buzzard with a covert cyno in it is exactly what this tool looks for."""
        k = km(victim=victim(ship=BUZZARD, items=[item(COVERT_CYNO, 27)]))
        f = analyze_killmail(k, CHAR, self.sets)
        self.assertEqual(LEVEL_CYNO, level_of(f))

    def test_a_cyno_stowed_in_a_quiet_hull_is_still_a_cyno(self):
        """`hull_class` is what decides cargo, and a Buzzard is still combat."""
        k = km(victim=victim(ship=BUZZARD, items=[item(COVERT_CYNO, 5)]))
        self.assertEqual(LEVEL_CYNO, level_of(analyze_killmail(k, CHAR,
                                                               self.sets)))

    def test_quietness_belongs_to_the_finding_not_the_ship(self):
        """One Buzzard, two findings, opposite answers -- and `ships_of` has to
        keep the louder one or the icon lands in the wrong place."""
        bare = Finding(1, KIND_HULL_FLOWN, 0.0, BUZZARD, None, None, "combat")
        armed = Finding(2, KIND_FITTED, 1.0, BUZZARD, COVERT_CYNO, None,
                        "combat")
        self.assertTrue(is_quiet(bare, self.sets))
        self.assertFalse(is_quiet(armed, self.sets))
        # Ahead of a bare Falcon it is not, but it must not be dead last
        # either: sorted with a loud hull, the armed Buzzard stays in the
        # combat block rather than sinking below it.
        falcon = Finding(3, KIND_HULL_FLOWN, 0.0, FALCON, None, None, "combat")
        self.assertEqual([FALCON, BUZZARD],
                         ships_of([bare, armed, falcon], self.sets))

    def test_a_bare_industrial_hull_produces_no_finding_at_all(self):
        """Not merely level `none` -- absent. It used to pad the killmail list."""
        lost = km(victim=victim(ship=BADGER, items=[]))
        self.assertEqual([], analyze_killmail(lost, CHAR, self.sets))
        flown = km(attackers=[{"character_id": CHAR, "ship_type_id": VENTURE}])
        self.assertEqual([], analyze_killmail(flown, CHAR, self.sets))


class TestGroupFindings(unittest.TestCase):
    """The LIJaman case: 62 findings, six hulls, and a list showing one.

    Fifty rows of the same Legion crowded out the Marshal and the Redeemer his
    icon row correctly showed. Grouping is what makes the icons and the list
    agree by construction.
    """

    def _flown(self, km_id, ship, when):
        return Finding(km_id, KIND_HULL_FLOWN, when, ship, None, None,
                       "combat")

    def test_a_repeated_hull_collapses_to_one_row_with_a_count(self):
        rows = group_findings([self._flown(i, LEGION, 1000.0 + i)
                               for i in range(52)])
        self.assertEqual(1, len(rows))
        self.assertEqual(52, rows[0]["n"])

    def test_the_row_points_at_the_newest_killmail_of_its_group(self):
        rows = group_findings([self._flown(7, LEGION, 100.0),
                               self._flown(9, LEGION, 900.0),
                               self._flown(8, LEGION, 500.0)])
        self.assertEqual(9, rows[0]["killmail_id"])
        self.assertEqual(900.0, rows[0]["km_time"])

    def test_every_distinct_hull_survives_the_collapse(self):
        """The whole point: no hull can be crowded out by a busier one."""
        raw = [self._flown(i, LEGION, 5000.0 + i) for i in range(52)]
        raw.append(self._flown(900, MARSHAL, 1.0))
        rows = group_findings(raw)
        self.assertEqual({LEGION, MARSHAL},
                         {r["ship_type_id"] for r in rows})

    def test_kind_and_module_split_a_hull_into_separate_rows(self):
        raw = [Finding(1, KIND_FITTED, 3.0, BUZZARD, COVERT_CYNO, None,
                       "combat"),
               Finding(2, KIND_HULL_LOST, 2.0, BUZZARD, None, None, "combat"),
               self._flown(3, BUZZARD, 1.0)]
        self.assertEqual(3, len(group_findings(raw)))

    def test_rows_are_newest_first(self):
        rows = group_findings([self._flown(1, LEGION, 10.0),
                               self._flown(2, MARSHAL, 99.0)])
        self.assertEqual([MARSHAL, LEGION], [r["ship_type_id"] for r in rows])

    def test_regrouping_is_idempotent(self):
        """The UI may be handed rows that are already grouped; counting them
        as one each would quietly deflate every number on screen."""
        once = group_findings([self._flown(i, LEGION, float(i))
                               for i in range(5)])
        twice = group_findings(once)
        self.assertEqual(once, twice)


class TestFilters(unittest.TestCase):
    """What the scan is asking for, and what it therefore does not see.

    These are not display filters. Evidence that is switched off is never
    extracted, which is the whole reason `scan` can skip a request rather than
    fetch it and throw the answer away -- see core/scan.py.
    """

    @classmethod
    def setUpClass(cls):
        cls.sets = cyno_sets.load()
        cls.narrow = Filters(potential=False, industrial=True)

    def find(self, k, filters, char=CHAR):
        return analyze_killmail(k, char, self.sets, filters)

    # --- potential cyno -------------------------------------------------

    def test_an_attacker_killmail_yields_nothing_at_all(self):
        """The load-bearing one. If this ever returns a finding, skipping the
        /kills/ feed stops being free and starts being a silent omission."""
        k = km(victim=victim(char=OTHER, ship=CHARON),
               attackers=[{"character_id": CHAR, "ship_type_id": FALCON}])
        self.assertEqual([], self.find(k, self.narrow))
        self.assertEqual([KIND_HULL_FLOWN],
                         [f.kind for f in self.find(k, ALL_EVIDENCE)])

    def test_a_bare_cyno_hull_loss_is_not_evidence_either(self):
        k = km(victim=victim(ship=FALCON))
        self.assertEqual([], self.find(k, self.narrow))
        self.assertEqual([KIND_HULL_LOST],
                         [f.kind for f in self.find(k, ALL_EVIDENCE)])

    def test_a_quiet_hull_cannot_produce_the_seen_level(self):
        k = km(victim=victim(ship=LEGION))
        self.assertEqual(LEVEL_NONE, level_of(self.find(k, self.narrow)))
        self.assertEqual(LEVEL_SEEN, level_of(self.find(k, ALL_EVIDENCE)))

    def test_the_module_on_that_same_hull_is_untouched(self):
        """Narrowing must never cost a red verdict -- that is the product."""
        k = km(victim=victim(ship=FALCON, items=[item(COVERT_CYNO, 27)]))
        found = self.find(k, self.narrow)
        self.assertEqual([KIND_FITTED], [f.kind for f in found])
        self.assertEqual(LEVEL_CYNO, level_of(found))

    def test_cargo_evidence_is_untouched_too(self):
        k = km(victim=victim(ship=FALCON, items=[item(COVERT_CYNO, 5)]))
        self.assertEqual([KIND_CARGO],
                         [f.kind for f in self.find(k, self.narrow)])

    # --- industrial cyno ------------------------------------------------

    def test_the_industrial_module_disappears_when_it_is_switched_off(self):
        no_indy = Filters(potential=True, industrial=False)
        k = km(victim=victim(ship=BADGER, items=[item(INDY_CYNO, 27)]))
        self.assertEqual([], [f for f in self.find(k, no_indy)
                              if f.module_type_id is not None])

    def test_a_pilot_with_only_an_industrial_cyno_becomes_clean(self):
        """He does not sink down the list, he leaves it: `none` is not shown."""
        no_indy = Filters(potential=False, industrial=False)
        k = km(victim=victim(ship=BADGER, items=[item(INDY_CYNO, 27)]))
        self.assertEqual(LEVEL_NONE, level_of(self.find(k, no_indy)))
        self.assertEqual(LEVEL_INDY, level_of(self.find(k, self.narrow)))

    def test_switching_industrial_off_leaves_combat_cyno_alone(self):
        no_indy = Filters(potential=False, industrial=False)
        k = km(victim=victim(ship=FALCON, items=[item(COVERT_CYNO, 27)]))
        self.assertEqual(LEVEL_CYNO, level_of(self.find(k, no_indy)))

    # --- the defaults and the bits ---------------------------------------

    def test_the_pure_analyser_defaults_to_everything(self):
        """A caller who did not ask to narrow the question gets the whole
        answer; only `scan` applies the user's choice."""
        k = km(victim=victim(ship=FALCON))
        self.assertEqual([KIND_HULL_LOST],
                         [f.kind for f in analyze_killmail(k, CHAR, self.sets)])

    def test_from_config_matches_the_shipped_defaults(self):
        from core import config
        self.assertEqual(Filters.from_config(config.DEFAULTS),
                         Filters(potential=False, industrial=True))

    def test_bits_round_trip(self):
        for p in (False, True):
            for i in (False, True):
                f = Filters(potential=p, industrial=i)
                self.assertEqual(f, Filters.from_bits(f.as_bits()))

    def test_the_default_bits_are_not_zero_by_accident(self):
        """`scan_bits` defaults to 3 in the schema, meaning "everything". A
        Filters value that also happened to be 3 would make that default
        indistinguishable from a row somebody really scanned narrow."""
        self.assertEqual(3, ALL_EVIDENCE.as_bits())
        self.assertNotEqual(3, Filters().as_bits())

    def test_all_cyno_is_every_module_the_sets_know(self):
        """The module column is sized from this. If a fourth cyno ever ships,
        the column has to grow with it and not with somebody's memory."""
        self.assertEqual(set(self.sets.modules), set(ALL_CYNO))


if __name__ == "__main__":
    unittest.main()
