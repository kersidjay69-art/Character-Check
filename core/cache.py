"""SQLite cache of verdicts and findings.

The design rests on one property: **the evidence is monotone.** A pilot who has
once died with a cyno fitted can never un-die in one. So a positive verdict is
cached forever and that pilot is never fetched again.

**Only pilots actually caught with a cyno module are stored.** EVE creates
roughly thirty thousand characters a day, so being a directory of everyone ever
seen is not a thing this file can be; a clean verdict is cheap to re-derive and
worthless to keep. That is what makes the cache small enough to live beside the
executable (`config.cache_dir`) and travel with it.

Each row records WHICH question it answered (`scan_bits`, see
`analyze.Filters`). A pilot scanned without "potential cyno" carries no hull
evidence at all, so handing him to a scan that does want it would under-report
-- `is_fresh` refuses, and he is fetched again.

Schema is additive-only and guarded on PRAGMA table_info, so re-running against
an older database converges instead of failing.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import time

from . import config

# Reentrant on purpose: connect() holds it while it migrates, imports and
# evicts, and every one of those steps calls a helper that locks for
# itself. A plain Lock deadlocks on the first open of a fresh database.
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pilots (
  character_id       INTEGER PRIMARY KEY,
  name               TEXT NOT NULL,
  -- Deliberately NOT UNIQUE. Biomassed character names can be released and
  -- reused; a UNIQUE index would turn that rare event into a failing INSERT
  -- that wedges a whole scan.
  name_lc            TEXT NOT NULL,
  level              TEXT NOT NULL,
  has_fitted         INTEGER NOT NULL DEFAULT 0,
  has_cargo          INTEGER NOT NULL DEFAULT 0,
  has_hull_lost      INTEGER NOT NULL DEFAULT 0,
  has_hull_flown     INTEGER NOT NULL DEFAULT 0,
  pages_scanned      INTEGER NOT NULL DEFAULT 0,
  full_history       INTEGER NOT NULL DEFAULT 0,
  checked_at         REAL NOT NULL,
  -- Comma-joined type ids, the pilot's whole truth rather than a sample.
  -- `findings` cannot answer this: its PK collapses on (killmail, kind), so a
  -- loss with two different cynos aboard stores only one row, and reads are
  -- capped. The icon row must not depend on either.
  modules_csv        TEXT NOT NULL DEFAULT '',
  ships_csv          TEXT NOT NULL DEFAULT '',
  -- Which evidence this scan was looking for; see analyze.Filters.as_bits.
  -- 3 = everything, which is what every row written before the filters
  -- existed was scanned with.
  scan_bits          INTEGER NOT NULL DEFAULT 3
);
CREATE INDEX IF NOT EXISTS idx_pilots_name_lc ON pilots(name_lc);
-- Eviction reads this and nothing else.
CREATE INDEX IF NOT EXISTS idx_pilots_checked ON pilots(checked_at);

CREATE TABLE IF NOT EXISTS findings (
  character_id   INTEGER NOT NULL,
  killmail_id    INTEGER NOT NULL,
  kind           TEXT NOT NULL,
  km_time        REAL NOT NULL,
  ship_type_id   INTEGER,
  module_type_id INTEGER,
  system_id      INTEGER,
  PRIMARY KEY (character_id, killmail_id, kind)
) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS idx_findings_char ON findings(character_id, km_time DESC);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def db_path() -> str:
    """Beside the application, not in %APPDATA% -- see `config.cache_dir`."""
    return os.path.join(config.cache_dir(), "cache.db")


def connect(path: str | None = None) -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is not None and path is None:
            return _conn
        p = path or db_path()
        fresh = not os.path.exists(p)
        conn = sqlite3.connect(p, check_same_thread=False)
        if fresh:
            # Has to be asked for before the first table exists: on a database
            # that already has one this pragma is silently a no-op, and then
            # eviction could delete rows forever without the file shrinking.
            conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(_SCHEMA)
        _add_missing_columns(conn)
        conn.commit()
        _migrate(conn)
        if path is None:
            # Only for the real cache. An explicit path is a caller who said
            # exactly which file they meant -- importing somebody else's
            # pilots into it, or evicting from it, would be an ambush. It is
            # also what keeps the test suite off the user's own database.
            _import_legacy(conn)
            enforce_limit(conn)
            _conn = conn
        return conn


def db_size(conn=None) -> int:
    """Bytes the database occupies, without asking the filesystem.

    page_count x page_size rather than os.path.getsize: under WAL the bytes are
    spread across three files and the -wal one is transient.
    """
    c = _conn_or_default(conn)
    with _lock:
        pages = c.execute("PRAGMA page_count").fetchone()[0]
        size = c.execute("PRAGMA page_size").fetchone()[0]
    return int(pages) * int(size)


def enforce_limit(conn=None, limit_mb: float | None = None) -> int:
    """Drop the least recently checked pilots until the file fits again.

    A safety valve rather than a mechanism: at the measured 10.5% of pilots
    carrying a module, reaching 100 MB takes about 1.8 million distinct cyno
    pilots. It exists so a cache sitting next to a portable copy can never
    quietly grow without bound.

    Rows go by PROPORTION, not one at a time until the size drops: space is
    only returned by the vacuum at the end, so a loop that re-measured after
    every delete would never terminate.
    """
    c = _conn_or_default(conn)
    if limit_mb is None:
        limit_mb = float(config.load().get("cache_limit_mb", 100) or 100)
    limit = int(limit_mb * 1048576)
    if limit <= 0:
        return 0
    target = int(limit * 0.9)
    removed = 0
    for _ in range(3):
        size = db_size(c)
        if size <= limit:
            break
        with _lock:
            total = c.execute("SELECT COUNT(*) FROM pilots").fetchone()[0]
            if not total:
                break
            share = 1.0 - (float(target) / float(size))
            drop = max(1, min(total, int(total * share) + 1))
            victims = [r[0] for r in c.execute(
                "SELECT character_id FROM pilots"
                " ORDER BY checked_at ASC LIMIT ?", (drop,))]
            c.executemany("DELETE FROM findings WHERE character_id=?",
                          [(v,) for v in victims])
            c.executemany("DELETE FROM pilots WHERE character_id=?",
                          [(v,) for v in victims])
            c.commit()
            _reclaim(c)
        removed += len(victims)
    return removed


def _reclaim(conn) -> None:
    """Hand the freed pages back to the filesystem.

    incremental_vacuum only does anything when auto_vacuum was switched on
    before the first table was created -- true for files this build made, false
    for every older one, which needs the full rewrite instead.
    """
    mode = conn.execute("PRAGMA auto_vacuum").fetchone()[0]
    if int(mode) == 2:
        conn.execute("PRAGMA incremental_vacuum")
        conn.commit()
        return
    try:
        conn.execute("VACUUM")
    except sqlite3.Error:
        # VACUUM refuses inside a transaction; the space simply waits.
        pass


def _import_legacy(conn) -> int:
    """Carry cyno pilots over from the old %APPDATA% cache, once.

    Only pilots with a module, because that is all the new cache keeps. The old
    file is left exactly where it is: it is the user's data, and deleting it
    would be doing them a favour they never asked for.
    """
    done = conn.execute("SELECT value FROM meta WHERE key=?",
                        ("import:legacy_cache",)).fetchone()
    if done:
        return 0
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)",
                 ("import:legacy_cache", "1"))
    conn.commit()
    old = os.path.join(config.data_dir(), "cache.db")
    if not os.path.exists(old):
        return 0
    if os.path.normcase(os.path.abspath(old)) == os.path.normcase(
            os.path.abspath(db_path())):
        return 0
    try:
        src = sqlite3.connect("file:%s?mode=ro" % old.replace("\\", "/"),
                              uri=True)
    except sqlite3.Error:
        return 0
    try:
        have = {r[1] for r in src.execute("PRAGMA table_info(pilots)")}
        if "modules_csv" not in have:
            return 0
        rows = src.execute(
            "SELECT character_id, name, name_lc, level, has_fitted,"
            " has_cargo, has_hull_lost, has_hull_flown, pages_scanned,"
            " full_history, checked_at, modules_csv, ships_csv"
            " FROM pilots WHERE modules_csv != ''").fetchall()
        conn.executemany(
            "INSERT OR IGNORE INTO pilots (character_id, name, name_lc,"
            " level, has_fitted, has_cargo, has_hull_lost, has_hull_flown,"
            " pages_scanned, full_history, checked_at, modules_csv,"
            " ships_csv, scan_bits) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,3)",
            rows)
        for row in rows:
            conn.executemany(
                "INSERT OR IGNORE INTO findings (character_id, killmail_id,"
                " kind, km_time, ship_type_id, module_type_id, system_id)"
                " VALUES (?,?,?,?,?,?,?)",
                src.execute(
                    "SELECT character_id, killmail_id, kind, km_time,"
                    " ship_type_id, module_type_id, system_id"
                    " FROM findings WHERE character_id=?",
                    (row[0],)).fetchall())
        conn.commit()
        return len(rows)
    except sqlite3.Error:
        # A corrupt or locked old cache is not worth failing a startup over.
        return 0
    finally:
        src.close()


# Columns added after the first release. CREATE TABLE IF NOT EXISTS is a no-op
# on an existing database, so new columns need an explicit ALTER -- guarded on
# PRAGMA table_info, exactly as the module docstring promises.
_ADDED_COLUMNS = (
    ("pilots", "modules_csv", "TEXT NOT NULL DEFAULT ''"),
    ("pilots", "ships_csv", "TEXT NOT NULL DEFAULT ''"),
    # Default 3, not 0: rows that predate the filters answered every question,
    # and calling them narrow would throw the whole cache away on first open.
    ("pilots", "scan_bits", "INTEGER NOT NULL DEFAULT 3"),
)


def _add_missing_columns(conn) -> None:
    for table, column, decl in _ADDED_COLUMNS:
        have = {r[1] for r in conn.execute("PRAGMA table_info(%s)" % table)}
        if column not in have:
            conn.execute("ALTER TABLE %s ADD COLUMN %s %s"
                         % (table, column, decl))


# Data migrations are flagged in `meta`, never counted or re-derived, so they
# run once and re-running converges.
_MIGRATIONS = ("levels_with_yellow", "levels_by_module",
               "drop_non_ship_module_findings",
               "levels_cargo_and_indy_hulls",
               "drop_prerebalance_module_findings",
               "ship_order_recon_first",
               "drop_indy_hull_findings",
               "levels_quiet_hulls")


def _migrate(conn) -> None:
    done = {r[0] for r in conn.execute(
        "SELECT key FROM meta WHERE key LIKE 'migration:%'")}
    for name in _MIGRATIONS:
        if "migration:" + name in done:
            continue
        if name == "drop_non_ship_module_findings":
            _drop_non_ship_findings(conn)
        if name == "drop_prerebalance_module_findings":
            _drop_incompatible_findings(conn)
        if name == "drop_indy_hull_findings":
            _drop_indy_hull_findings(conn)
        if name in ("levels_with_yellow", "levels_by_module",
                    "drop_non_ship_module_findings",
                    "levels_cargo_and_indy_hulls",
                    "drop_prerebalance_module_findings",
                    "ship_order_recon_first",
                    "drop_indy_hull_findings",
                    "levels_quiet_hulls"):
            _recompute_levels(conn)
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)",
                     ("migration:" + name, "1"))
        conn.commit()


def _drop_non_ship_findings(conn) -> None:
    """Delete module evidence recorded against something that is not a ship.

    A Mobile Tractor Unit that scooped a cyno off a wreck and then died was
    being credited to its owner as "cyno in cargo". The killmail is real, the
    inference was not.
    """
    from . import cyno_sets
    try:
        sets = cyno_sets.load()
    except Exception:
        return
    victims = conn.execute(
        "SELECT DISTINCT ship_type_id FROM findings"
        " WHERE module_type_id IS NOT NULL AND ship_type_id IS NOT NULL"
    ).fetchall()
    bad = [t for (t,) in victims if not sets.is_ship(t)]
    for t in bad:
        conn.execute("DELETE FROM findings WHERE module_type_id IS NOT NULL"
                     " AND ship_type_id=?", (t,))


def _drop_incompatible_findings(conn) -> None:
    """Delete module evidence the hull cannot mount under the current SDE.

    Two shapes, one rule (`CynoSets.can_fit`):

      * the hull is not a cyno hull at all -- Velator, Ibis, a freighter.
        Cynos genuinely were fitted to rookie frigates before the
        canFitShipGroup restriction landed.
      * the hull is cyno-capable but takes a different variant -- a plain
        Cyno I bolted to a Manticore, legal then, impossible now.

    Measured on a 1712-pilot cache: 727 of 1493 module findings, moving 53
    pilots down a level. This REVERSES an earlier decision to keep historical
    fits; see the note in CLAUDE.md before restoring them.
    """
    from . import cyno_sets
    try:
        sets = cyno_sets.load()
    except Exception:
        return
    pairs = conn.execute(
        "SELECT DISTINCT ship_type_id, module_type_id FROM findings"
        " WHERE module_type_id IS NOT NULL").fetchall()
    for ship, mod in pairs:
        if ship is None or not sets.can_fit(ship, mod):
            conn.execute("DELETE FROM findings WHERE module_type_id=?"
                         " AND ship_type_id IS ?", (mod, ship))


def _drop_indy_hull_findings(conn) -> None:
    """Delete bare-hull evidence recorded against an industrial cyno hull.

    A lost Venture or Badger with nothing in it is a hauler. Those findings
    already scored `none` and already earned no icon, but they were still
    filling the expandable killmail list, which is the one place the noise was
    still visible.

    Module evidence on the same hull is left alone: an industrial cyno fitted
    into an Epithal is the whole point of the `indy` verdict.
    """
    from . import cyno_sets
    try:
        sets = cyno_sets.load()
    except Exception:
        return
    ships = conn.execute(
        "SELECT DISTINCT ship_type_id FROM findings"
        " WHERE module_type_id IS NULL AND ship_type_id IS NOT NULL"
    ).fetchall()
    bad = [t for (t,) in ships if sets.hull_class(t) == "indy"]
    for t in bad:
        conn.execute("DELETE FROM findings WHERE module_type_id IS NULL"
                     " AND ship_type_id=?", (t,))


def _recompute_levels(conn) -> None:
    """Re-derive every cached verdict, and its icon summary, from the findings.

    Needed when the level rules change -- as they did when `yellow` was split
    out of `orange`, and again when a stowed cyno stopped counting on a hull
    that cannot light one. The findings are the facts; the level and the icon
    rows are only opinions about them, so it is always safe to recompute and
    never right to guess.
    """
    from . import analyze, cyno_sets
    try:
        sets = cyno_sets.load()
    except Exception:
        return
    rows = conn.execute(
        "SELECT character_id, kind, ship_type_id, module_type_id"
        " FROM findings").fetchall()
    by_pilot: dict = {}
    for cid, kind, ship, mod in rows:
        # "unknown" is the honest answer for a hull outside the cyno set. It
        # used to say "combat" here, which is what let a freighter's cargo
        # read as a fitted cyno.
        cls = sets.hull_class(ship) if ship else "unknown"
        # Re-derived for the same reason as the class: the row does not store
        # it, and without it every bare Covert Ops and T3 would recompute as
        # `hull` again -- the migration would undo itself.
        grp = sets.hull_group(ship) if ship else None
        by_pilot.setdefault(cid, []).append(
            analyze.Finding(0, kind, 0.0, ship, mod, None, cls, grp))
    for cid, findings in by_pilot.items():
        conn.execute(
            "UPDATE pilots SET level=?, modules_csv=?, ships_csv=?"
            " WHERE character_id=?",
            (analyze.level_of(findings),
             _csv(analyze.modules_of(findings, sets)),
             _csv(analyze.ships_of(findings, sets)), cid))
    # Pilots with no findings at all are not in `by_pilot`, so they would keep
    # a level name from the old scheme forever and vanish from every count.
    have = ",".join(str(int(c)) for c in by_pilot)
    conn.execute(
        "UPDATE pilots SET level=?, modules_csv='', ships_csv=''"
        " WHERE character_id NOT IN (%s)" % (have or "0"),
        (analyze.LEVEL_NONE,))
    # Any level name this build does not know is not a level. Every constant
    # has to be listed: a missing one here means the migration overwrites its
    # own result with `none` on the very next open.
    conn.execute("UPDATE pilots SET level=? WHERE level NOT IN (?,?,?,?,?)",
                 (analyze.LEVEL_NONE, analyze.LEVEL_CYNO, analyze.LEVEL_HULL,
                  analyze.LEVEL_INDY, analyze.LEVEL_SEEN, analyze.LEVEL_NONE))


def _csv(type_ids) -> str:
    """Type ids -> "28646,52694". Order is meaningful: worst first."""
    return ",".join(str(int(t)) for t in type_ids)


def parse_csv(text: str) -> list:
    """"28646,52694" -> [28646, 52694]. Tolerates empty and malformed."""
    out = []
    for chunk in (text or "").split(","):
        chunk = chunk.strip()
        if chunk.isdigit():
            out.append(int(chunk))
    return out


def close() -> None:
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None


def _conn_or_default(conn):
    return conn if conn is not None else connect()


def get_pilot(character_id: int, conn=None) -> dict | None:
    c = _conn_or_default(conn)
    with _lock:
        row = c.execute(
            "SELECT character_id, name, level, has_fitted, has_cargo,"
            " has_hull_lost, has_hull_flown, pages_scanned, full_history,"
            " checked_at, modules_csv, ships_csv, scan_bits"
            " FROM pilots WHERE character_id=?",
            (character_id,)).fetchone()
    if not row:
        return None
    keys = ("character_id", "name", "level", "has_fitted", "has_cargo",
            "has_hull_lost", "has_hull_flown", "pages_scanned",
            "full_history", "checked_at", "modules_csv", "ships_csv",
            "scan_bits")
    entry = dict(zip(keys, row))
    entry["modules"] = parse_csv(entry["modules_csv"])
    entry["ships"] = parse_csv(entry["ships_csv"])
    return entry


def is_fresh(entry: dict | None, ttl_days: float, filters=None) -> bool:
    """Can this row answer the question being asked right now?

    Two independent reasons it might not:

    * it is stale. A positive never goes stale -- the evidence is monotone --
      so only a clean verdict expires. The level name is compared against the
      current constant, never a literal: an old literal here silently made
      every verdict permanent, TTL included.
    * it answered a DIFFERENT question. A pilot scanned with "potential cyno"
      off has no hull rows at all, so serving him to a scan that wants them
      would report an absence nobody ever looked for. Equality rather than
      containment, and `Filters.as_bits` says why a wider row is no better.
    """
    from . import analyze
    if not entry:
        return False
    if filters is not None and filters != analyze.Filters.from_bits(
            entry.get("scan_bits", 3)):
        return False
    if entry["level"] != analyze.LEVEL_NONE:
        return True
    return (time.time() - entry["checked_at"]) < ttl_days * 86400.0


def save_pilot(character_id: int, name: str, level: str, findings,
               pages_scanned: int, full_history: bool, conn=None,
               modules=None, ships=None, filters=None) -> bool:
    """Store a verdict, if it is one worth storing. Returns whether it was.

    **A pilot with no cyno module is not stored at all.** That is the whole
    sizing decision: thirty thousand characters are created a day, so a row per
    name seen is a database this app has no business keeping, while the 10.5%
    who were actually caught with a module fit beside the executable. The cost
    is honest and was accepted -- a clean pilot is re-checked on every paste.

    `modules`/`ships` are the caller's already-computed summaries; deriving them
    here is only a fallback, and it is a lossy one. Deriving needs the SDE:
    `ships_of` without `sets` cannot tell a recon from a hauler or a quiet hull
    from a loud one, so it used to store the row in a flat, wrong order that
    only a migration ever fixed. scan_pilot has the correct lists two lines
    earlier.

    `filters` is recorded, not applied -- see the module docstring for what
    reads it back.
    """
    from . import analyze
    c = _conn_or_default(conn)
    kinds = {f.kind for f in findings}
    if modules is None or ships is None:
        from . import cyno_sets
        try:
            sets = cyno_sets.load()
        except Exception:
            sets = None
        if modules is None:
            modules = analyze.modules_of(findings, sets)
        if ships is None:
            ships = analyze.ships_of(findings, sets)
    if not modules:
        return False
    # Stored from the full finding list -- never re-derived later from whatever
    # survived the findings table.
    modules_csv = _csv(modules)
    ships_csv = _csv(ships)
    bits = (filters or analyze.ALL_EVIDENCE).as_bits()
    now = time.time()
    with _lock:
        c.execute(
            "INSERT INTO pilots (character_id, name, name_lc, level,"
            " has_fitted, has_cargo, has_hull_lost, has_hull_flown,"
            " pages_scanned, full_history, checked_at,"
            " modules_csv, ships_csv, scan_bits)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT(character_id) DO UPDATE SET"
            "  name=excluded.name, name_lc=excluded.name_lc,"
            "  level=excluded.level, has_fitted=excluded.has_fitted,"
            "  has_cargo=excluded.has_cargo,"
            "  has_hull_lost=excluded.has_hull_lost,"
            "  has_hull_flown=excluded.has_hull_flown,"
            "  pages_scanned=MAX(pilots.pages_scanned, excluded.pages_scanned),"
            "  full_history=MAX(pilots.full_history, excluded.full_history),"
            "  checked_at=excluded.checked_at,"
            "  modules_csv=excluded.modules_csv,"
            "  ships_csv=excluded.ships_csv,"
            # Assigned, not OR-ed. The row has to describe the summary it
            # actually holds: `modules_csv`/`ships_csv` above were just
            # overwritten with this scan's answer, and claiming the wider
            # question is still answered would serve that narrow summary to it.
            "  scan_bits=excluded.scan_bits",
            (character_id, name, name.casefold(), level,
             int("fitted" in kinds), int("cargo" in kinds),
             int("hull_lost" in kinds), int("hull_flown" in kinds),
             pages_scanned, int(full_history), now,
             modules_csv, ships_csv, bits))
        if findings:
            c.executemany(
                "INSERT OR IGNORE INTO findings (character_id, killmail_id,"
                " kind, km_time, ship_type_id, module_type_id, system_id)"
                " VALUES (?,?,?,?,?,?,?)",
                [(character_id, f.killmail_id, f.kind, f.km_time,
                  f.ship_type_id, f.module_type_id, f.system_id)
                 for f in findings])
        c.commit()
    return True


def get_findings(character_id: int, limit: int = 200, conn=None,
                 filters=None) -> list[dict]:
    """One row per (kind, ship, module), newest first, with a count.

    This used to be one row per killmail ordered by date, capped at 50, and on
    an active pilot the cap was spent on a single hull: LIJaman had 62 findings
    across six hulls and the 50 newest were all the same Legion, so the Marshal
    and Redeemer in his icon row had no visible explanation. Raising the cap
    would not have helped -- the problem was sameness, not size.

    ⚠️ `killmail_id` and `system_id` are bare columns beside MAX(km_time).
    SQLite guarantees they come from the row that MAX picked; that guarantee is
    the whole reason a double-click here opens the newest killmail of the group
    rather than an arbitrary one. Do not rewrite this into a plain aggregate.

    The LIMIT is only a backstop now: groups are bounded by kinds x hulls.

    `filters` narrows what comes back, and it is not optional politeness. The
    table is append-only across every scan a pilot has ever had, so it is the
    UNION of the questions asked over time -- a hull row left behind by an
    older, wider scan would otherwise turn up under a row whose icons were
    built without it.
    """
    from . import analyze
    c = _conn_or_default(conn)
    where = ["character_id=?"]
    args: list = [character_id]
    if filters is not None:
        if not filters.potential:
            where.append("module_type_id IS NOT NULL")
        if not filters.industrial:
            where.append("(module_type_id IS NULL OR module_type_id NOT IN (%s))"
                         % ",".join(str(int(m))
                                    for m in sorted(analyze.INDUSTRIAL_CYNO)))
    args.append(limit)
    with _lock:
        rows = c.execute(
            "SELECT killmail_id, kind, MAX(km_time), ship_type_id,"
            " module_type_id, system_id, COUNT(*)"
            " FROM findings WHERE %s"
            " GROUP BY kind, ship_type_id, module_type_id"
            " ORDER BY MAX(km_time) DESC LIMIT ?" % " AND ".join(where),
            args).fetchall()
    keys = ("killmail_id", "kind", "km_time", "ship_type_id",
            "module_type_id", "system_id", "n")
    return [dict(zip(keys, r)) for r in rows]


def stats(conn=None) -> dict:
    from . import analyze
    c = _conn_or_default(conn)
    with _lock:
        pilots = c.execute("SELECT COUNT(*) FROM pilots").fetchone()[0]
        flagged = c.execute(
            "SELECT COUNT(*) FROM pilots WHERE level!=?",
            (analyze.LEVEL_NONE,)).fetchone()[0]
        finds = c.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
    return {"pilots": pilots, "flagged": flagged, "findings": finds}
