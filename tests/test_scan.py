"""Order, the listing floor, and which feeds a scan actually asks for.

`ScanResult.at_least` is the only thing that decides who the window shows and
in what order, and both rules in it are counter-intuitive enough to have been
got wrong once already.

`feeds_for` is the other half: it is where the scan stops asking zKillboard
questions whose answers it has already decided not to look at. No network --
zkb is replaced with a counter.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import analyze, config, scan as scan_mod, zkb  # noqa: E402
from core.analyze import (  # noqa: E402
    ALL_EVIDENCE, Filters, LEVEL_CYNO, LEVEL_HULL, LEVEL_INDY, LEVEL_NONE,
    LEVEL_SEEN,
)
from core.scan import PilotResult, ScanResult  # noqa: E402

COVERT_CYNO = 28646
INDY_CYNO = 52694
FALCON = 11957
LEGION = 29986


def pilot(name, level, modules=(), ships=(), cid=1):
    return PilotResult(cid, name, level=level, modules=list(modules),
                       ships=list(ships))


def result(*pilots):
    return ScanResult(True, "list", "", list(pilots))


class TestListingFloor(unittest.TestCase):
    def test_seen_pilots_are_listed(self):
        """A bare Covert Ops or T3 is no threat, but hiding the pilot would
        also hide the fact that we looked at him."""
        r = result(pilot("LIJaman", LEVEL_SEEN, ships=[LEGION]))
        self.assertEqual(["LIJaman"], [p.name for p in r.flagged])

    def test_clean_pilots_are_not_listed(self):
        r = result(pilot("Miner", LEVEL_NONE))
        self.assertEqual([], r.flagged)

    def test_the_floor_is_still_selectable_for_the_console(self):
        """`min_level` filtering reads the ranks, and the console keeps its own
        floor -- "seen" would add most of a trade hub to a terminal."""
        r = result(pilot("LIJaman", LEVEL_SEEN, ships=[LEGION]),
                   pilot("Scout", LEVEL_HULL, ships=[FALCON], cid=2))
        self.assertEqual(["Scout"], [p.name for p in r.at_least(LEVEL_INDY)])


class TestDisplayOrder(unittest.TestCase):
    def test_seen_sinks_below_every_warning(self):
        r = result(pilot("Quiet", LEVEL_SEEN, ships=[LEGION]),
                   pilot("Yellow", LEVEL_HULL, ships=[FALCON], cid=2),
                   pilot("Red", LEVEL_CYNO, modules=[COVERT_CYNO], cid=3))
        self.assertEqual(["Red", "Yellow", "Quiet"],
                         [p.name for p in r.flagged])

    def test_a_pilot_holding_a_cyno_outranks_one_who_is_not(self):
        """The levels alone put `indy` (rank 2) under `hull` (rank 3), so the
        blue pilot who was caught WITH a module sorted below a yellow one who
        had nothing aboard. Whoever is carrying goes on top."""
        r = result(pilot("Yellow", LEVEL_HULL, ships=[FALCON]),
                   pilot("Blue", LEVEL_INDY, modules=[INDY_CYNO], cid=2))
        self.assertEqual(["Blue", "Yellow"], [p.name for p in r.flagged])

    def test_ties_break_on_the_name_case_insensitively(self):
        r = result(pilot("bob", LEVEL_HULL, ships=[FALCON]),
                   pilot("Alice", LEVEL_HULL, ships=[FALCON], cid=2))
        self.assertEqual(["Alice", "bob"], [p.name for p in r.flagged])


class TestSortKeyIsShared(unittest.TestCase):
    """Streaming inserts each pilot as he lands; the final render sorts the
    whole list. One function, or the window reshuffles itself when a scan
    ends and it looks like a bug."""

    def test_the_streamed_order_is_the_final_order(self):
        pilots = [pilot("Quiet", LEVEL_SEEN, ships=[LEGION]),
                  pilot("Yellow", LEVEL_HULL, ships=[FALCON], cid=2),
                  pilot("Blue", LEVEL_INDY, modules=[INDY_CYNO], cid=3),
                  pilot("Red", LEVEL_CYNO, modules=[COVERT_CYNO], cid=4),
                  pilot("alice", LEVEL_HULL, ships=[FALCON], cid=5)]
        streamed = sorted(pilots, key=scan_mod.pilot_sort_key)
        final = result(*pilots).flagged
        self.assertEqual([p.name for p in final], [p.name for p in streamed])


class TestFeeds(unittest.TestCase):
    """Which zKillboard feeds a question needs -- the whole speed story."""

    def test_potential_off_asks_for_losses_only(self):
        self.assertEqual((zkb.KIND_LOSSES,),
                         scan_mod.feeds_for(Filters(potential=False)))

    def test_potential_on_asks_for_both(self):
        self.assertEqual((zkb.KIND_LOSSES, zkb.KIND_KILLS),
                         scan_mod.feeds_for(ALL_EVIDENCE))


class TestScanPilotRequests(unittest.TestCase):
    """What actually leaves the machine, counted.

    zkb.iter_killmails is replaced, so nothing here touches the network. The
    cache is pointed at a throwaway file for the same reason -- scan_pilot
    writes to it, and it must not be the user's.
    """

    @classmethod
    def setUpClass(cls):
        from core import cyno_sets
        cls.sets = cyno_sets.load()

    def setUp(self):
        from core import cache
        self.conn = cache.connect(
            os.path.join(tempfile.mkdtemp(), "t.db"))
        cache._conn = self.conn
        self.calls = []
        self.real = zkb.iter_killmails

        def fake(character_id, kind, max_pages=1, start_page=1, stop=None):
            self.calls.append((kind, max_pages, stop is not None))
            return iter(())

        zkb.iter_killmails = fake

    def tearDown(self):
        from core import cache
        zkb.iter_killmails = self.real
        cache._conn = None
        self.conn.close()

    def scan_one(self, filters, **kw):
        scan_mod.scan_pilot(1, "Bob", self.sets, 1, 7.0, use_cache=False,
                            filters=filters, **kw)
        return [c[0] for c in self.calls]

    def test_the_kills_feed_is_never_requested_with_potential_off(self):
        """The measured 2x. Module evidence lives only in victim.items, so
        with hull evidence switched off this request cannot contribute a row
        -- and a request that cannot change the screen must not be made."""
        self.assertEqual([zkb.KIND_LOSSES], self.scan_one(Filters()))

    def test_both_feeds_are_requested_with_potential_on(self):
        self.assertEqual([zkb.KIND_LOSSES, zkb.KIND_KILLS],
                         self.scan_one(ALL_EVIDENCE))

    def test_the_stop_predicate_is_only_passed_when_asked_for(self):
        self.scan_one(ALL_EVIDENCE, stop_at_first=False)
        self.assertEqual([False, False], [c[2] for c in self.calls])
        self.calls = []
        self.scan_one(ALL_EVIDENCE, stop_at_first=True)
        self.assertEqual([True, True], [c[2] for c in self.calls])


class TestStopAtFirstThreshold(unittest.TestCase):
    """One pilot is fast either way, so a complete answer wins. A thousand
    pilots pay the same choice a thousand times."""

    def test_the_threshold_is_a_named_constant(self):
        self.assertEqual(10, scan_mod.STOP_AT_FIRST_MIN)

    def test_a_single_name_is_below_it(self):
        self.assertFalse(1 > scan_mod.STOP_AT_FIRST_MIN)

    def test_a_local_paste_is_above_it(self):
        self.assertTrue(200 > scan_mod.STOP_AT_FIRST_MIN)


class TestProven(unittest.TestCase):
    """What "until the first combat cyno" stops at."""

    def test_a_combat_cyno_proves_it(self):
        f = analyze.Finding(1, analyze.KIND_FITTED, 0.0, FALCON, COVERT_CYNO,
                            None, "combat", 833)
        self.assertTrue(scan_mod._proven([f]))

    def test_an_industrial_cyno_does_not(self):
        """Stopping on one would leave a red pilot reported as blue."""
        f = analyze.Finding(1, analyze.KIND_FITTED, 0.0, FALCON, INDY_CYNO,
                            None, "combat", 833)
        self.assertFalse(scan_mod._proven([f]))

    def test_a_bare_hull_does_not(self):
        f = analyze.Finding(1, analyze.KIND_HULL_LOST, 0.0, FALCON, None,
                            None, "combat", 833)
        self.assertFalse(scan_mod._proven([f]))


class TestIgnoreList(unittest.TestCase):
    """The session ignore list, at the level where it has to pay.

    Hiding rows would have been the easy version. The point of applying it
    inside `scan_text` is that an ignored pilot costs NO cache lookup and NO
    request -- so what these tests watch is the two things that would have
    happened, not the rows that did not appear.

    Nothing here touches the network: ESI, zKillboard and the cache are all
    replaced.
    """

    def setUp(self):
        from core import cache, esi
        self.calls = []
        self.cache_reads = []
        self._esi, self._zkb = esi.resolve_names, zkb.iter_killmails
        self._get = cache.get_pilot
        self.cache = cache
        self.esi = esi

        def resolve(names):
            # Three pilots, ids 101/102/103, whatever was pasted.
            return {n.casefold(): (100 + i + 1, n)
                    for i, n in enumerate(names)}

        def killmails(character_id, kind, max_pages=1, start_page=1,
                      stop=None):
            self.calls.append(character_id)
            return iter(())

        def get_pilot(character_id):
            self.cache_reads.append(character_id)
            return None

        esi.resolve_names = resolve
        zkb.iter_killmails = killmails
        cache.get_pilot = get_pilot

    def tearDown(self):
        self.esi.resolve_names = self._esi
        zkb.iter_killmails = self._zkb
        self.cache.get_pilot = self._get

    PASTE = "Alpha One\nBravo Two\nCharlie Three\n"

    def scan(self, ignore=()):
        return scan_mod.scan_text(self.PASTE, cfg=dict(config.DEFAULTS),
                                  ignore_ids=ignore)

    def test_without_a_list_every_pilot_is_fetched(self):
        result = self.scan()
        self.assertTrue(result.accepted)
        self.assertEqual([101, 102, 103], sorted(self.calls))
        self.assertEqual(0, result.ignored)

    def test_an_ignored_pilot_costs_no_request(self):
        self.scan(ignore={102})
        self.assertEqual([101, 103], sorted(self.calls))

    def test_an_ignored_pilot_is_not_even_looked_up_in_the_cache(self):
        """The filter sits BEFORE the cache read on purpose. A cached fleet
        would otherwise still be fetched from disk and then thrown away."""
        self.scan(ignore={102})
        self.assertNotIn(102, self.cache_reads)

    def test_an_ignored_pilot_is_not_in_the_result(self):
        result = self.scan(ignore={102})
        self.assertEqual([101, 103],
                         sorted(p.character_id for p in result.pilots))

    def test_the_count_of_what_was_dropped_comes_back(self):
        """Without it a scan that quietly halves a paste looks broken."""
        self.assertEqual(2, self.scan(ignore={101, 103}).ignored)

    def test_the_progress_total_counts_what_will_be_scanned(self):
        """"checked 3 of 12" has to mean twelve pilots somebody is actually
        going to look at, not twelve minus however many were skipped."""
        seen = []
        scan_mod.scan_text(self.PASTE, cfg=dict(config.DEFAULTS),
                           ignore_ids={102},
                           on_stage=lambda st, n: seen.append((st, n)))
        self.assertIn((scan_mod.STAGE_SCANNING, 2), seen)

    def test_ignoring_everyone_is_an_empty_answer_and_not_a_refusal(self):
        """A refusal puts a "skipped:" line on screen and means the paste was
        junk. Ignoring the whole fleet is neither."""
        result = self.scan(ignore={101, 102, 103})
        self.assertTrue(result.accepted)
        self.assertEqual([], result.pilots)
        self.assertEqual(3, result.ignored)
        self.assertEqual([], self.calls)

    def test_an_unknown_id_in_the_list_changes_nothing(self):
        self.scan(ignore={999})
        self.assertEqual([101, 102, 103], sorted(self.calls))


if __name__ == "__main__":
    unittest.main()
