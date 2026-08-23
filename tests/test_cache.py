"""Cache behaviour, in-memory, no network."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import cache, config  # noqa: E402
from core.analyze import (  # noqa: E402
    ALL_EVIDENCE, Filters, KIND_CARGO, KIND_FITTED, KIND_HULL_FLOWN,
    KIND_HULL_LOST, LEVEL_CYNO, LEVEL_HULL, LEVEL_INDY, LEVEL_NONE,
    LEVEL_SEEN, Finding,
)


def db_mb(conn) -> float:
    return cache.db_size(conn) / 1048576.0


def f(kind, km_id=1, ship=11957, mod=None, when=1_700_000_000.0,
      hull_class="combat"):
    return Finding(km_id, kind, when, ship, mod, 30000142, hull_class)


FALCON = 11957      # combat cyno hull
BADGER = 648        # industrial cyno hull
CHARON = 20185      # a ship, but no cyno hull at all
COVERT_CYNO = 28646
PLAIN_CYNO = 21096
INDY_CYNO = 52694
HOUND = 12034       # Stealth Bomber -- covert cyno only
VELATOR = 606       # rookie corvette -- cannot mount any cyno today
LEGION = 29986      # Strategic Cruiser -- a QUIET hull
BUZZARD = 11192     # Covert Ops -- a QUIET hull
REDEEMER = 22428    # Black Ops
MARSHAL = 44996     # Black Ops
VIATOR = 12743      # Blockade Runner


def store(character_id, name, level, findings, pages_scanned=1,
          full_history=False, conn=None, modules=None, ships=None):
    """Write a pilot row unconditionally, the way an older build did.

    `cache.save_pilot` refuses a pilot with no cyno module -- that is the
    sizing rule the whole cache rests on, and it has its own tests below. The
    migration, summary and grouping tests are about rows earlier builds left
    behind, which predate the rule, so they need a door that ignores it.
    """
    from core import analyze, cyno_sets
    sets = cyno_sets.load()
    if modules is None:
        modules = analyze.modules_of(findings, sets)
    if ships is None:
        ships = analyze.ships_of(findings, sets)
    kinds = {x.kind for x in findings}
    conn.execute(
        "INSERT INTO pilots (character_id, name, name_lc, level, has_fitted,"
        " has_cargo, has_hull_lost, has_hull_flown, pages_scanned,"
        " full_history, checked_at, modules_csv, ships_csv, scan_bits)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,3)"
        " ON CONFLICT(character_id) DO UPDATE SET"
        "  level=excluded.level, has_fitted=excluded.has_fitted,"
        "  has_cargo=excluded.has_cargo,"
        "  has_hull_lost=excluded.has_hull_lost,"
        "  has_hull_flown=excluded.has_hull_flown,"
        "  pages_scanned=MAX(pilots.pages_scanned, excluded.pages_scanned),"
        "  full_history=MAX(pilots.full_history, excluded.full_history),"
        "  checked_at=excluded.checked_at,"
        "  modules_csv=excluded.modules_csv, ships_csv=excluded.ships_csv",
        (character_id, name, name.casefold(), level,
         int(KIND_FITTED in kinds), int(KIND_CARGO in kinds),
         int(KIND_HULL_LOST in kinds), int(KIND_HULL_FLOWN in kinds),
         pages_scanned, int(full_history), time.time(),
         cache._csv(modules), cache._csv(ships)))
    conn.executemany(
        "INSERT OR IGNORE INTO findings (character_id, killmail_id, kind,"
        " km_time, ship_type_id, module_type_id, system_id)"
        " VALUES (?,?,?,?,?,?,?)",
        [(character_id, x.killmail_id, x.kind, x.km_time, x.ship_type_id,
          x.module_type_id, x.system_id) for x in findings])
    conn.commit()


class TestSchema(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.conn = cache.connect(self.path)

    def tearDown(self):
        self.conn.close()

    def test_migrations_are_idempotent(self):
        """Re-running the schema must converge, not fail."""
        self.conn.executescript(cache._SCHEMA)
        self.conn.executescript(cache._SCHEMA)
        self.conn.commit()

    def test_wal_is_on(self):
        mode = self.conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual("wal", mode.lower())

    def test_name_lc_is_not_unique(self):
        """A biomassed name can be released and reused. A UNIQUE index would
        turn that into a failing INSERT that wedges a scan."""
        idx = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='idx_pilots_name_lc'"
        ).fetchone()[0]
        self.assertNotIn("UNIQUE", idx.upper())


class TestRoundTrip(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.conn = cache.connect(self.path)

    def tearDown(self):
        self.conn.close()

    def test_save_and_read_back(self):
        store(1, "Bob", LEVEL_CYNO, [f(KIND_FITTED, mod=28646)],
                         1, False, conn=self.conn)
        got = cache.get_pilot(1, conn=self.conn)
        self.assertEqual(LEVEL_CYNO, got["level"])
        self.assertEqual(1, got["has_fitted"])
        self.assertEqual(0, got["has_hull_flown"])
        self.assertEqual([28646],
                         [x["module_type_id"] for x in
                          cache.get_findings(1, conn=self.conn)])

    def test_findings_are_idempotent(self):
        for _ in range(3):
            store(1, "Bob", LEVEL_CYNO, [f(KIND_FITTED, mod=28646)],
                             1, False, conn=self.conn)
        self.assertEqual(1, len(cache.get_findings(1, conn=self.conn)))

    def test_pages_scanned_never_regresses(self):
        store(1, "Bob", LEVEL_NONE, [], 5, True, conn=self.conn)
        store(1, "Bob", LEVEL_NONE, [], 1, False, conn=self.conn)
        got = cache.get_pilot(1, conn=self.conn)
        self.assertEqual(5, got["pages_scanned"])
        self.assertEqual(1, got["full_history"])

    def test_stats(self):
        store(1, "Bob", LEVEL_CYNO, [f(KIND_FITTED)], 1, False,
                         conn=self.conn)
        store(2, "Ann", LEVEL_NONE, [], 1, False, conn=self.conn)
        s = cache.stats(conn=self.conn)
        self.assertEqual(2, s["pilots"])
        self.assertEqual(1, s["flagged"])


class TestFreshness(unittest.TestCase):
    def test_positive_never_expires(self):
        """The evidence is monotone: a pilot who died with a cyno fitted can
        never un-die in one, so a finding is cached forever."""
        for lv in (LEVEL_CYNO, LEVEL_HULL, LEVEL_INDY):
            self.assertTrue(cache.is_fresh({"level": lv, "checked_at": 0.0}, 7), lv)

    def test_negative_expires(self):
        """Guards a real bug: after the levels were renamed, is_fresh still
        compared against the old literal, so every clean verdict became
        permanent and the TTL silently stopped working."""
        self.assertFalse(cache.is_fresh({"level": LEVEL_NONE, "checked_at": 0.0}, 7))
        self.assertTrue(cache.is_fresh(
            {"level": LEVEL_NONE, "checked_at": time.time()}, 7))

    def test_missing_entry_is_not_fresh(self):
        self.assertFalse(cache.is_fresh(None, 7))


class TestIconSummary(unittest.TestCase):
    """The module/ship rows the UI draws come from here, not from `findings`.

    `findings` cannot answer the question: its primary key collapses on
    (killmail, kind), so one loss with two cynos aboard stores a single row,
    and reads are capped at 50 besides.
    """

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.conn = cache.connect(self.path)

    def tearDown(self):
        self.conn.close()

    def save(self, findings, level=LEVEL_CYNO):
        store(1, "Bob", level, findings, 1, False, conn=self.conn)
        return cache.get_pilot(1, conn=self.conn)

    def test_summary_round_trips(self):
        got = self.save([f(KIND_FITTED, mod=COVERT_CYNO)])
        self.assertEqual([COVERT_CYNO], got["modules"])
        self.assertEqual([FALCON], got["ships"])

    def test_two_modules_on_one_killmail_both_survive(self):
        """The exact case the findings table loses to its primary key."""
        got = self.save([f(KIND_FITTED, km_id=7, mod=COVERT_CYNO),
                         f(KIND_FITTED, km_id=7, mod=INDY_CYNO)])
        self.assertEqual([COVERT_CYNO, INDY_CYNO], got["modules"])
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM findings WHERE character_id=1").fetchone()[0]
        self.assertEqual(1, rows)

    def test_cargo_on_a_freighter_leaves_no_module(self):
        got = self.save([f(KIND_CARGO, ship=CHARON, mod=COVERT_CYNO,
                           hull_class="unknown")], level=LEVEL_NONE)
        self.assertEqual([], got["modules"])
        self.assertEqual([], got["ships"])

    def test_bare_industrial_hull_leaves_no_ship(self):
        got = self.save([f(KIND_HULL_LOST, ship=BADGER, hull_class="indy")],
                        level=LEVEL_NONE)
        self.assertEqual([], got["ships"])

    def test_a_pilot_with_no_findings_has_empty_summaries(self):
        got = self.save([], level=LEVEL_NONE)
        self.assertEqual([], got["modules"])
        self.assertEqual([], got["ships"])

    def test_parse_csv_tolerates_junk(self):
        self.assertEqual([], cache.parse_csv(""))
        self.assertEqual([], cache.parse_csv(None))
        self.assertEqual([1, 2], cache.parse_csv("1, ,2,x"))


class TestLevelMigration(unittest.TestCase):
    """`levels_cargo_and_indy_hulls` re-derives verdicts under the new rules."""

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")

    def _legacy_db(self, rows):
        """A database as an older build left it: flagged, no summaries, and
        with our migration flag not yet set."""
        conn = cache.connect(self.path)
        for cid, name, level, findings in rows:
            store(cid, name, level, findings, 1, False, conn=conn)
        conn.execute("UPDATE pilots SET modules_csv='', ships_csv=''")
        conn.execute("DELETE FROM meta WHERE key=?",
                     ("migration:levels_cargo_and_indy_hulls",))
        conn.commit()
        conn.close()

    def test_bare_industrial_hull_is_demoted_to_clean(self):
        self._legacy_db([
            (1, "Miner", LEVEL_INDY,
             [f(KIND_HULL_LOST, ship=BADGER, hull_class="indy")]),
        ])
        conn = cache.connect(self.path)
        self.assertEqual(LEVEL_NONE, cache.get_pilot(1, conn=conn)["level"])
        conn.close()

    def test_combat_hull_survives_the_migration(self):
        self._legacy_db([
            (2, "Scout", LEVEL_HULL,
             [f(KIND_HULL_LOST, ship=FALCON, hull_class="combat")]),
        ])
        conn = cache.connect(self.path)
        got = cache.get_pilot(2, conn=conn)
        self.assertEqual(LEVEL_HULL, got["level"])
        self.assertEqual([FALCON], got["ships"])
        conn.close()

    def test_migration_backfills_summaries(self):
        self._legacy_db([
            (3, "Bob", LEVEL_CYNO, [f(KIND_FITTED, mod=COVERT_CYNO)]),
        ])
        conn = cache.connect(self.path)
        got = cache.get_pilot(3, conn=conn)
        self.assertEqual([COVERT_CYNO], got["modules"])
        self.assertEqual([FALCON], got["ships"])
        conn.close()

    def test_a_pilot_with_no_findings_is_still_touched(self):
        """The rule from CLAUDE.md: a migration that skips the finding-less
        pilots leaves them wearing a level name from the old scheme forever."""
        conn = cache.connect(self.path)
        store(4, "Ghost", LEVEL_NONE, [], 1, False, conn=conn)
        conn.execute("UPDATE pilots SET level='orange', modules_csv='9'")
        conn.execute("DELETE FROM meta WHERE key=?",
                     ("migration:levels_cargo_and_indy_hulls",))
        conn.commit()
        conn.close()

        conn = cache.connect(self.path)
        got = cache.get_pilot(4, conn=conn)
        self.assertEqual(LEVEL_NONE, got["level"])
        self.assertEqual([], got["modules"])
        conn.close()

    def test_migration_is_idempotent(self):
        self._legacy_db([
            (5, "Miner", LEVEL_INDY,
             [f(KIND_HULL_LOST, ship=BADGER, hull_class="indy")]),
        ])
        for _ in range(3):
            conn = cache.connect(self.path)
            self.assertEqual(LEVEL_NONE,
                             cache.get_pilot(5, conn=conn)["level"])
            conn.close()


class TestAdditiveColumns(unittest.TestCase):
    def test_columns_are_added_to_an_older_database(self):
        """A database created before the summary columns existed must gain
        them on open rather than blowing up on the first SELECT."""
        import sqlite3
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        raw = sqlite3.connect(path)
        raw.executescript(
            "CREATE TABLE pilots ("
            " character_id INTEGER PRIMARY KEY, name TEXT NOT NULL,"
            " name_lc TEXT NOT NULL, level TEXT NOT NULL,"
            " has_fitted INTEGER NOT NULL DEFAULT 0,"
            " has_cargo INTEGER NOT NULL DEFAULT 0,"
            " has_hull_lost INTEGER NOT NULL DEFAULT 0,"
            " has_hull_flown INTEGER NOT NULL DEFAULT 0,"
            " pages_scanned INTEGER NOT NULL DEFAULT 0,"
            " full_history INTEGER NOT NULL DEFAULT 0,"
            " checked_at REAL NOT NULL);"
            "INSERT INTO pilots VALUES (9,'Old','old','cyno',1,0,0,0,1,0,0.0);")
        raw.commit()
        raw.close()

        conn = cache.connect(path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(pilots)")}
        self.assertIn("modules_csv", cols)
        self.assertIn("ships_csv", cols)
        self.assertIsNotNone(cache.get_pilot(9, conn=conn))
        conn.close()


class TestPreRebalanceCleanup(unittest.TestCase):
    """`drop_prerebalance_module_findings` retires fits the SDE now forbids."""

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")

    def _seed(self, rows):
        """Write findings, then clear our migration flag so it runs on reopen."""
        conn = cache.connect(self.path)
        for cid, name, level, findings in rows:
            store(cid, name, level, findings, 1, False, conn=conn)
        conn.execute("DELETE FROM meta WHERE key=?",
                     ("migration:drop_prerebalance_module_findings",))
        conn.commit()
        conn.close()

    def _findings(self, cid):
        conn = cache.connect(self.path)
        out = cache.get_findings(cid, conn=conn)
        conn.close()
        return out

    def test_a_rookie_ship_fit_is_deleted(self):
        """The headline case: a 2015 cyno on a Velator is real and useless."""
        self._seed([(1, "Old", LEVEL_CYNO,
                     [f(KIND_FITTED, ship=VELATOR, mod=COVERT_CYNO,
                        hull_class="unknown")])])
        conn = cache.connect(self.path)
        self.assertEqual([], cache.get_findings(1, conn=conn))
        got = cache.get_pilot(1, conn=conn)
        self.assertEqual(LEVEL_NONE, got["level"])
        self.assertEqual([], got["modules"])
        self.assertEqual([], got["ships"])
        conn.close()

    def test_the_wrong_variant_on_a_real_hull_is_deleted(self):
        """A plain Cyno I on a Stealth Bomber -- legal then, impossible now."""
        self._seed([(2, "Bomber", LEVEL_CYNO,
                     [f(KIND_FITTED, ship=HOUND, mod=PLAIN_CYNO),
                      f(KIND_HULL_LOST, km_id=2, ship=HOUND)])])
        kinds = [x["kind"] for x in self._findings(2)]
        self.assertEqual([KIND_HULL_LOST], kinds)
        conn = cache.connect(self.path)
        # The hull survives, so the pilot stays yellow instead of vanishing.
        self.assertEqual(LEVEL_HULL, cache.get_pilot(2, conn=conn)["level"])
        conn.close()

    def test_a_legitimate_fit_is_untouched(self):
        """The gate must not eat evidence that is still valid."""
        self._seed([(3, "Scout", LEVEL_CYNO,
                     [f(KIND_FITTED, ship=HOUND, mod=COVERT_CYNO)])])
        conn = cache.connect(self.path)
        self.assertEqual(1, len(cache.get_findings(3, conn=conn)))
        got = cache.get_pilot(3, conn=conn)
        self.assertEqual(LEVEL_CYNO, got["level"])
        self.assertEqual([COVERT_CYNO], got["modules"])
        conn.close()

    def test_hull_only_findings_are_never_touched(self):
        """No module, nothing to be incompatible with."""
        self._seed([(4, "Flyer", LEVEL_HULL,
                     [f(KIND_HULL_FLOWN, ship=FALCON)])])
        self.assertEqual(1, len(self._findings(4)))

    def test_migration_is_idempotent(self):
        self._seed([(5, "Old", LEVEL_CYNO,
                     [f(KIND_FITTED, ship=VELATOR, mod=COVERT_CYNO,
                        hull_class="unknown")])])
        for _ in range(3):
            conn = cache.connect(self.path)
            self.assertEqual(LEVEL_NONE, cache.get_pilot(5, conn=conn)["level"])
            self.assertEqual([], cache.get_findings(5, conn=conn))
            conn.close()

    def test_module_order_is_rewritten_covert_first(self):
        """The stored CSV order has to be rebuilt too, not just the level."""
        self._seed([(6, "Both", LEVEL_CYNO,
                     [f(KIND_FITTED, km_id=1, ship=FALCON, mod=PLAIN_CYNO),
                      f(KIND_FITTED, km_id=2, ship=FALCON, mod=COVERT_CYNO)])])
        conn = cache.connect(self.path)
        self.assertEqual([COVERT_CYNO, PLAIN_CYNO],
                         cache.get_pilot(6, conn=conn)["modules"])
        conn.close()


class TestEvidenceGrouping(unittest.TestCase):
    """The LIJaman defect, reproduced at its real shape.

    62 findings across six hulls. Ordered by date and capped at fifty, the read
    returned nothing but the newest hull -- so the Marshal and the Redeemer his
    icon row correctly showed had no row to explain them. Grouping is what
    makes the two agree.
    """

    # Exactly the distribution measured on the live cache.
    SHAPE = ((LEGION, KIND_HULL_FLOWN, 52, 6_000_000.0),
             (REDEEMER, KIND_HULL_FLOWN, 3, 5_000_000.0),
             (HOUND, KIND_HULL_LOST, 3, 4_000_000.0),
             (VIATOR, KIND_HULL_LOST, 2, 3_000_000.0),
             (MARSHAL, KIND_HULL_LOST, 1, 1_000_000.0))

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.conn = cache.connect(self.path)
        findings, km_id = [], 1
        for ship, kind, count, base in self.SHAPE:
            for i in range(count):
                findings.append(f(kind, km_id=km_id, ship=ship,
                                  when=base + i))
                km_id += 1
        self.total = len(findings)
        store(1, "LIJaman", LEVEL_HULL, findings, 1, False,
                         conn=self.conn)

    def tearDown(self):
        self.conn.close()

    def test_the_shape_really_is_the_one_that_broke(self):
        """Guards the fixture: comfortably past the old cap of 50.

        61 rather than the live pilot's 62 -- his last one was a Noctis, which
        is not a cyno hull at all and cannot reach this table under today's
        rules. Everything that matters here is the 52 that ate the cap.
        """
        self.assertEqual(61, self.total)
        self.assertGreater(self.total, 50)
        stored = self.conn.execute(
            "SELECT COUNT(*) FROM findings WHERE character_id=1").fetchone()[0]
        self.assertEqual(61, stored)

    def test_every_hull_gets_a_row(self):
        rows = cache.get_findings(1, conn=self.conn)
        self.assertEqual(len(self.SHAPE), len(rows))
        self.assertEqual({s for s, _, _, _ in self.SHAPE},
                         {r["ship_type_id"] for r in rows})

    def test_the_busiest_hull_no_longer_crowds_the_rest_out(self):
        """The failure in one line: before grouping this list was 50 Legions."""
        ships = [r["ship_type_id"] for r in cache.get_findings(1,
                                                               conn=self.conn)]
        self.assertIn(MARSHAL, ships)
        self.assertIn(REDEEMER, ships)

    def test_the_count_covers_every_row_not_the_sample(self):
        rows = {r["ship_type_id"]: r["n"]
                for r in cache.get_findings(1, conn=self.conn)}
        for ship, _, count, _ in self.SHAPE:
            self.assertEqual(count, rows[ship], ship)

    def test_each_row_points_at_the_newest_killmail_of_its_group(self):
        """A bare column beside MAX(km_time). SQLite promises it comes from the
        row MAX picked -- the double-click depends on that promise."""
        for row in cache.get_findings(1, conn=self.conn):
            newest = self.conn.execute(
                "SELECT killmail_id, km_time FROM findings"
                " WHERE character_id=1 AND kind=? AND ship_type_id=?"
                " ORDER BY km_time DESC LIMIT 1",
                (row["kind"], row["ship_type_id"])).fetchone()
            self.assertEqual(newest[0], row["killmail_id"])
            self.assertEqual(newest[1], row["km_time"])

    def test_rows_are_newest_first(self):
        times = [r["km_time"] for r in cache.get_findings(1, conn=self.conn)]
        self.assertEqual(sorted(times, reverse=True), times)

    def test_the_icon_row_and_the_evidence_list_name_the_same_hulls(self):
        """The property the whole change exists to guarantee."""
        listed = {r["ship_type_id"]
                  for r in cache.get_findings(1, conn=self.conn)}
        drawn = set(cache.get_pilot(1, conn=self.conn)["ships"])
        self.assertTrue(drawn <= listed, drawn - listed)


class TestQuietHullMigration(unittest.TestCase):
    """`levels_quiet_hulls` demotes bare Covert Ops and T3 to `seen`."""

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")

    def _seed(self, rows):
        conn = cache.connect(self.path)
        for cid, name, level, findings in rows:
            store(cid, name, level, findings, 1, False, conn=conn)
        conn.execute("DELETE FROM meta WHERE key=?",
                     ("migration:levels_quiet_hulls",))
        conn.commit()
        conn.close()

    def _level(self, cid):
        conn = cache.connect(self.path)
        out = cache.get_pilot(cid, conn=conn)["level"]
        conn.close()
        return out

    def test_a_bare_t3_stops_being_a_warning(self):
        self._seed([(1, "LIJaman", LEVEL_HULL,
                     [f(KIND_HULL_FLOWN, ship=LEGION)])])
        self.assertEqual(LEVEL_SEEN, self._level(1))

    def test_a_bare_covert_ops_stops_being_a_warning(self):
        self._seed([(2, "Explorer", LEVEL_HULL,
                     [f(KIND_HULL_LOST, ship=BUZZARD)])])
        self.assertEqual(LEVEL_SEEN, self._level(2))

    def test_a_loud_hull_keeps_its_warning(self):
        self._seed([(3, "Scout", LEVEL_HULL, [f(KIND_HULL_FLOWN, ship=FALCON)])])
        self.assertEqual(LEVEL_HULL, self._level(3))

    def test_a_cyno_on_a_quiet_hull_outranks_its_quietness(self):
        self._seed([(4, "Hunter", LEVEL_CYNO,
                     [f(KIND_FITTED, ship=BUZZARD, mod=COVERT_CYNO)])])
        self.assertEqual(LEVEL_CYNO, self._level(4))

    def test_the_new_level_survives_reopening(self):
        """`seen` has to be in the list of levels the schema recognises, or the
        very next open rewrites it back to `none`."""
        self._seed([(5, "LIJaman", LEVEL_HULL,
                     [f(KIND_HULL_FLOWN, ship=LEGION)])])
        for _ in range(3):
            self.assertEqual(LEVEL_SEEN, self._level(5))


class TestIndyHullFindingCleanup(unittest.TestCase):
    """`drop_indy_hull_findings` removes bare haulers from the evidence list."""

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")

    def _seed(self, rows):
        conn = cache.connect(self.path)
        for cid, name, level, findings in rows:
            store(cid, name, level, findings, 1, False, conn=conn)
        conn.execute("DELETE FROM meta WHERE key=?",
                     ("migration:drop_indy_hull_findings",))
        conn.commit()
        conn.close()

    def _findings(self, cid):
        conn = cache.connect(self.path)
        out = cache.get_findings(cid, conn=conn)
        conn.close()
        return out

    def test_a_bare_hauler_is_deleted(self):
        self._seed([(1, "Miner", LEVEL_NONE,
                     [f(KIND_HULL_LOST, ship=BADGER, hull_class="indy")])])
        self.assertEqual([], self._findings(1))

    def test_a_hauler_with_a_cyno_fitted_is_kept(self):
        """The `indy` verdict is made of exactly this row."""
        self._seed([(2, "Bridger", LEVEL_INDY,
                     [f(KIND_FITTED, ship=BADGER, mod=INDY_CYNO,
                        hull_class="indy")])])
        rows = self._findings(2)
        self.assertEqual(1, len(rows))
        conn = cache.connect(self.path)
        self.assertEqual(LEVEL_INDY, cache.get_pilot(2, conn=conn)["level"])
        conn.close()

    def test_a_combat_hull_is_never_touched(self):
        self._seed([(3, "Scout", LEVEL_HULL, [f(KIND_HULL_FLOWN, ship=FALCON)])])
        self.assertEqual(1, len(self._findings(3)))

    def test_migration_is_idempotent(self):
        self._seed([(4, "Miner", LEVEL_NONE,
                     [f(KIND_HULL_LOST, ship=BADGER, hull_class="indy")])])
        for _ in range(3):
            self.assertEqual([], self._findings(4))


class TestOnlyCynoPilotsAreStored(unittest.TestCase):
    """The sizing rule the whole file rests on.

    EVE creates about thirty thousand characters a day, so a row per name ever
    seen is a database this app has no business keeping. The 10.5% who were
    actually caught with a module do fit -- beside the executable, and small
    enough to travel with it. The cost is real and was accepted: a clean pilot
    is re-checked on every paste.
    """

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.conn = cache.connect(self.path)

    def tearDown(self):
        self.conn.close()

    def save(self, cid, level, findings, **kw):
        return cache.save_pilot(cid, "P%d" % cid, level, findings, 1, False,
                                conn=self.conn, **kw)

    def test_a_pilot_with_a_module_is_stored(self):
        self.assertTrue(self.save(1, LEVEL_CYNO, [f(KIND_FITTED,
                                                    mod=COVERT_CYNO)]))
        self.assertIsNotNone(cache.get_pilot(1, conn=self.conn))

    def test_a_clean_pilot_is_not_stored_at_all(self):
        self.assertFalse(self.save(2, LEVEL_NONE, []))
        self.assertIsNone(cache.get_pilot(2, conn=self.conn))

    def test_a_bare_cyno_hull_is_not_stored_either(self):
        """`hull` is a verdict, not a cyno. Keeping it would put a fifth of a
        trade hub in the file for an answer worth one request."""
        self.assertFalse(self.save(3, LEVEL_HULL,
                                   [f(KIND_HULL_LOST, ship=FALCON)]))
        self.assertIsNone(cache.get_pilot(3, conn=self.conn))

    def test_freight_is_not_a_module(self):
        """A cyno in a freighter's hold is cargo, so `modules_of` drops it and
        there is nothing left to store."""
        self.assertFalse(self.save(4, LEVEL_NONE,
                                   [f(KIND_CARGO, ship=CHARON,
                                      mod=COVERT_CYNO,
                                      hull_class="unknown")]))
        self.assertIsNone(cache.get_pilot(4, conn=self.conn))

    def test_the_findings_of_an_unstored_pilot_are_not_written(self):
        """Nothing must be left behind pointing at a pilot row that is not
        there -- eviction deletes by character_id and would never reach it."""
        self.save(5, LEVEL_HULL, [f(KIND_HULL_LOST, ship=FALCON)])
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM findings WHERE character_id=5").fetchone()[0]
        self.assertEqual(0, rows)


class TestScanBits(unittest.TestCase):
    """A cached row answers ONE question. Serving it to another one reports an
    absence nobody looked for."""

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.conn = cache.connect(self.path)
        self.narrow = Filters(potential=False, industrial=True)

    def tearDown(self):
        self.conn.close()

    def save(self, filters):
        cache.save_pilot(1, "Bob", LEVEL_CYNO,
                         [f(KIND_FITTED, mod=COVERT_CYNO)], 1, False,
                         conn=self.conn, filters=filters)
        return cache.get_pilot(1, conn=self.conn)

    def test_the_question_is_recorded(self):
        self.assertEqual(self.narrow.as_bits(), self.save(self.narrow)["scan_bits"])
        self.assertEqual(ALL_EVIDENCE.as_bits(),
                         self.save(ALL_EVIDENCE)["scan_bits"])

    def test_the_same_question_is_served_from_the_cache(self):
        self.assertTrue(cache.is_fresh(self.save(self.narrow), 7, self.narrow))

    def test_a_wider_question_refuses_a_narrow_row(self):
        """The pilot has no hull evidence at all -- it was never looked for."""
        self.assertFalse(cache.is_fresh(self.save(self.narrow), 7,
                                        ALL_EVIDENCE))

    def test_a_narrower_question_refuses_a_wide_row_as_well(self):
        """Equality, not containment. A wide row's `ships_csv` carries hulls
        the narrow question never asked about, while the evidence list under
        it is filtered down -- the icon row and the expansion would disagree,
        which is the failure this project has already paid for once."""
        self.assertFalse(cache.is_fresh(self.save(ALL_EVIDENCE), 7,
                                        self.narrow))

    def test_a_rescan_replaces_the_question_rather_than_adding_to_it(self):
        """The row has to describe the summary it actually holds; the summary
        was just overwritten by this scan."""
        self.save(ALL_EVIDENCE)
        self.assertEqual(self.narrow.as_bits(),
                         self.save(self.narrow)["scan_bits"])

    def test_a_row_from_before_the_filters_answers_everything(self):
        self.assertTrue(cache.is_fresh(
            {"level": LEVEL_CYNO, "checked_at": 0.0}, 7, ALL_EVIDENCE))

    def test_no_filter_asked_means_no_opinion(self):
        self.assertTrue(cache.is_fresh(self.save(self.narrow), 7))


class TestFindingsAreFilteredOnRead(unittest.TestCase):
    """`findings` is append-only across every scan a pilot ever had, so it is
    the UNION of the questions asked over time. A hull row left behind by an
    older, wider scan must not turn up under a row whose icons were built
    without it."""

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.conn = cache.connect(self.path)
        store(1, "Bob", LEVEL_CYNO,
              [f(KIND_FITTED, km_id=1, mod=COVERT_CYNO),
               f(KIND_FITTED, km_id=2, ship=BADGER, mod=INDY_CYNO,
                 hull_class="indy"),
               f(KIND_HULL_LOST, km_id=3, ship=FALCON),
               f(KIND_HULL_FLOWN, km_id=4, ship=FALCON)],
              conn=self.conn)

    def tearDown(self):
        self.conn.close()

    def kinds(self, filters):
        return sorted(r["kind"] for r in
                      cache.get_findings(1, conn=self.conn, filters=filters))

    def test_everything_comes_back_when_everything_was_asked_for(self):
        self.assertEqual([KIND_FITTED, KIND_FITTED, KIND_HULL_FLOWN,
                          KIND_HULL_LOST], self.kinds(ALL_EVIDENCE))

    def test_bare_hull_rows_are_hidden_when_potential_is_off(self):
        self.assertEqual([KIND_FITTED, KIND_FITTED],
                         self.kinds(Filters(potential=False)))

    def test_the_industrial_module_is_hidden_when_it_is_off(self):
        rows = cache.get_findings(
            1, conn=self.conn,
            filters=Filters(potential=False, industrial=False))
        self.assertEqual([COVERT_CYNO],
                         [r["module_type_id"] for r in rows])

    def test_no_filter_still_returns_the_lot(self):
        """Callers that do not care -- migrations, the stats line -- keep the
        old behaviour."""
        self.assertEqual(4, len(cache.get_findings(1, conn=self.conn)))


class TestEviction(unittest.TestCase):
    """The 100 MB ceiling. A safety valve, not a mechanism: reaching it takes
    roughly 1.8 million distinct cyno pilots."""

    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "t.db")
        self.conn = cache.connect(self.path)
        for cid in range(1, 21):
            store(cid, "P%d" % cid, LEVEL_CYNO,
                  [f(KIND_FITTED, km_id=cid, mod=COVERT_CYNO)],
                  conn=self.conn)
            # Oldest first, so eviction has an unambiguous order to follow.
            self.conn.execute("UPDATE pilots SET checked_at=? WHERE"
                              " character_id=?", (float(cid), cid))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def _left(self):
        return {r[0] for r in
                self.conn.execute("SELECT character_id FROM pilots")}

    def test_nothing_goes_while_the_file_fits(self):
        self.assertEqual(0, cache.enforce_limit(self.conn, limit_mb=100))
        self.assertEqual(20, len(self._left()))

    def test_the_least_recently_checked_go_first(self):
        cache.enforce_limit(self.conn, limit_mb=db_mb(self.conn) * 0.5)
        left = self._left()
        self.assertLess(len(left), 20)
        # Whatever survived, it is a suffix of the checked_at order.
        self.assertEqual(sorted(left)[-1], 20)
        self.assertNotIn(1, left)

    def test_a_pilots_findings_go_with_him(self):
        cache.enforce_limit(self.conn, limit_mb=db_mb(self.conn) * 0.5)
        left = self._left()
        orphans = [r[0] for r in self.conn.execute(
            "SELECT DISTINCT character_id FROM findings")
            if r[0] not in left]
        self.assertEqual([], orphans)

    def test_a_zero_limit_is_off_rather_than_empty(self):
        """A misread config must not wipe the cache."""
        self.assertEqual(0, cache.enforce_limit(self.conn, limit_mb=0))
        self.assertEqual(20, len(self._left()))

    def test_a_fresh_database_can_actually_give_pages_back(self):
        """auto_vacuum has to be asked for before the first table exists; on a
        database that already has one the pragma is silently a no-op, and then
        eviction deletes rows forever without the file ever shrinking."""
        self.assertEqual(2, self.conn.execute(
            "PRAGMA auto_vacuum").fetchone()[0])


class TestCacheLocation(unittest.TestCase):
    """Beside the application, so a portable copy carries its own answers."""

    def setUp(self):
        self.saved = os.environ.pop("CC_DATA_DIR", None)
        self.home = tempfile.mkdtemp()
        self.real_app_dir = config.app_dir
        config.app_dir = lambda: self.home

    def tearDown(self):
        config.app_dir = self.real_app_dir
        if self.saved is not None:
            os.environ["CC_DATA_DIR"] = self.saved

    def test_it_sits_next_to_the_application(self):
        self.assertEqual(os.path.join(self.home, "cache"), config.cache_dir())

    def test_an_unwritable_folder_falls_back_instead_of_refusing_to_start(self):
        """An exe dropped into Program Files still has to run."""
        real = config._writable
        config._writable = lambda p: False
        try:
            self.assertEqual(config.data_dir(), config.cache_dir())
        finally:
            config._writable = real

    def test_the_environment_override_still_wins(self):
        """It is what the whole test suite runs on."""
        forced = tempfile.mkdtemp()
        os.environ["CC_DATA_DIR"] = forced
        try:
            self.assertEqual(forced, config.cache_dir())
        finally:
            os.environ.pop("CC_DATA_DIR", None)

    def test_the_config_does_not_move_with_it(self):
        """Only the cache is portable. Settings stay where Windows roams
        them."""
        self.assertNotEqual(config.cache_dir(),
                            os.path.dirname(config.config_path()))


if __name__ == "__main__":
    unittest.main()
