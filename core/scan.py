"""Scan orchestration: clipboard text in, pilot verdicts out.

    guard -> ESI (final arbiter) -> cache -> zKillboard -> analyze

WHAT IS BEING ASKED DECIDES WHAT IS FETCHED
-------------------------------------------
Module evidence -- the `fitted` and `cargo` findings, the ones that make a
pilot red or blue -- is read only from `victim.items`, which exists only on the
pilot's OWN losses. The `/kills/` feed carries killmails where he was an
attacker and somebody else was the victim, so it can produce exactly one kind
of finding: `hull_flown`.

That is the evidence `Filters.potential` switches off. With it off the kills
feed cannot contribute a single row to the screen, so it is not requested at
all: one request per pilot instead of two, ~175 s instead of ~350 s on a
1400-name paste. Not a heuristic and not a sampling trade -- nothing that would
have been shown is missed.

Depth is one page everywhere, a single pasted name included. See CLAUDE.md for
what that costs: the honest form of the answer is "in the last 200 losses",
not "ever".
"""
from __future__ import annotations

import concurrent.futures as cf
import logging
import threading
import time
from dataclasses import dataclass, field

from . import analyze, cache, config, cyno_sets, esi, guard, i18n, zkb
from .http import ZKB_CONCURRENCY

log = logging.getLogger("cc.scan")

# Below this many pilots, "stop at the first combat cyno" is ignored and the
# scan reads everything. One pilot costs a fraction of a second either way, so
# there is nothing to save and a full answer is strictly better; the toggle
# exists for the paste where the same choice is paid for a thousand times.
STOP_AT_FIRST_MIN = 10

# Stages reported through `on_stage`, so the window can put something on screen
# before the first verdict lands. Keys, not sentences: i18n owns the wording.
STAGE_RESOLVING = "resolving"
STAGE_SCANNING = "scanning"


@dataclass
class PilotResult:
    character_id: int
    name: str
    level: str = analyze.LEVEL_NONE
    findings: list = field(default_factory=list)
    pages_scanned: int = 0
    full_history: bool = False
    from_cache: bool = False
    error: str = ""

    # The pilot's whole truth, worst first. Fields rather than properties
    # derived from `findings`: `findings` is GROUPED and capped, so deriving
    # there would report whatever survived grouping rather than what was seen.
    modules: list = field(default_factory=list)
    ships: list = field(default_factory=list)

    # When the cached answer was recorded, epoch seconds; 0.0 for a fresh scan.
    # Shown in the pilot's tooltip so a stale-looking row can be argued with.
    checked_at: float = 0.0

    @property
    def is_flagged(self) -> bool:
        return self.level != analyze.LEVEL_NONE


def pilot_sort_key(p):
    """Display order, worst first. The one definition, called from both places.

    Streaming inserts each pilot as he lands and the final render sorts the
    whole list; two copies of this rule would let those two orders drift, and
    the drift would look like the window shuffling itself for no reason.

    Having a cyno aboard outranks the level, because the levels alone put
    `indy` (rank 2) below `hull` (rank 3) -- so a pilot caught WITH an
    industrial cyno sorted below one who merely flew a cyno hull with nothing
    in it. Whoever is actually carrying goes on top.
    """
    return (not p.modules,
            -analyze._LEVEL_RANK.get(p.level, 0),
            p.name.casefold())


@dataclass
class ScanResult:
    accepted: bool
    mode: str = "rejected"
    reason: str = ""
    pilots: list = field(default_factory=list)
    own_seen: tuple = ()
    unresolved: tuple = ()
    elapsed: float = 0.0
    # The same refusal as `reason`, but as a translation key plus its
    # arguments, so the window can say it in the reader's language while the
    # log keeps the English. Appended at the END on purpose: ScanResult is
    # built positionally in places, and inserting a field mid-list silently
    # shifts `pilots` and `own_seen` into the wrong slots.
    reason_key: str = ""
    reason_args: tuple = ()

    def at_least(self, min_level: str = analyze.LEVEL_INDY) -> list:
        """Pilots at or above a level, most dangerous first.

        The ranks are read here for filtering only; the order comes from
        `pilot_sort_key`, and that is a different question.
        """
        floor = analyze._LEVEL_RANK.get(min_level, 1)
        return sorted(
            (p for p in self.pilots
             if analyze._LEVEL_RANK.get(p.level, 0) >= floor and p.is_flagged),
            key=pilot_sort_key)

    @property
    def flagged(self) -> list:
        """Everything found, in priority order.

        Down to `seen`, not `indy`: a pilot whose only evidence is a bare
        Covert Ops or T3 is no threat, but he is still shown -- greyed, at the
        bottom. Dropping him entirely would hide the fact that we looked. With
        "potential cyno" off no such pilot exists in the first place.
        """
        return self.at_least(analyze.LEVEL_SEEN)


def feeds_for(filters: analyze.Filters) -> tuple:
    """Which zKillboard feeds this question actually needs.

    The whole speed story in one function -- see the module docstring.
    """
    if filters.potential:
        return (zkb.KIND_LOSSES, zkb.KIND_KILLS)
    return (zkb.KIND_LOSSES,)


def _proven(findings) -> bool:
    """Is a combat cyno already established beyond argument?

    What "until the first combat cyno" stops at. Deliberately the top verdict
    and not merely `fitted`: an industrial cyno is not the thing being looked
    for, and stopping on one would leave a red pilot reported as blue.
    """
    return any(f.level == analyze.LEVEL_CYNO for f in findings)


def _from_cache(entry: dict, character_id: int, name: str,
                filters) -> PilotResult:
    res = PilotResult(character_id, name)
    res.level = entry["level"]
    res.pages_scanned = entry["pages_scanned"]
    res.full_history = bool(entry["full_history"])
    res.from_cache = True
    res.checked_at = float(entry.get("checked_at") or 0.0)
    res.modules = entry["modules"]
    res.ships = entry["ships"]
    # Grouped evidence for the expandable list only -- never for the icons,
    # which come from the summary above. Filtered for the same reason the
    # summary was: see cache.get_findings.
    res.findings = cache.get_findings(character_id, filters=filters)
    return res


def scan_pilot(character_id: int, name: str, sets, max_pages: int,
               ttl_days: float, use_cache: bool = True, filters=None,
               stop_at_first: bool = False) -> PilotResult:
    """One pilot: cache first, then whatever feeds the question needs."""
    filters = filters or analyze.ALL_EVIDENCE
    res = PilotResult(character_id, name)

    if use_cache:
        entry = cache.get_pilot(character_id)
        if cache.is_fresh(entry, ttl_days, filters):
            return _from_cache(entry, character_id, name, filters)

    findings: list = []
    pages = 0
    complete = True
    # Losses carry the module evidence, so they come first: proving a combat
    # cyno there makes the kills feed pointless.
    for kind in feeds_for(filters):
        if stop_at_first and _proven(findings):
            complete = False
            break
        try:
            seen_pages = 0
            # Checked between pages, so it only bites when a scan reads more
            # than one -- with the default single page the saving comes from
            # skipping the whole second feed above.
            stop = (lambda: _proven(findings)) if stop_at_first else None
            for km in zkb.iter_killmails(character_id, kind,
                                         max_pages=max_pages, stop=stop):
                findings.extend(
                    analyze.analyze_killmail(km, character_id, sets, filters))
                seen_pages = 1
            pages += seen_pages
        except Exception as exc:
            log.warning("zkb %s failed for %s (%d): %s", kind, name,
                        character_id, exc)
            res.error = str(exc)[:120]
            complete = False

    res.level = analyze.level_of(findings)
    res.modules = analyze.modules_of(findings, sets)
    res.ships = analyze.ships_of(findings, sets)
    # Grouped so that a fresh scan and a cached one hand the UI the same shape.
    # The raw list still goes to the cache -- that is what `n` is counted from.
    res.findings = analyze.group_findings(findings)
    res.pages_scanned = pages
    res.full_history = complete and max_pages >= zkb.MAX_PAGE

    if not res.error:
        try:
            # Returns False for a pilot with nothing aboard: those are not
            # stored at all. See cache.save_pilot for the sizing decision.
            cache.save_pilot(character_id, name, res.level, findings,
                             res.pages_scanned, res.full_history,
                             modules=res.modules, ships=res.ships,
                             filters=filters)
        except Exception:
            log.exception("cache write failed for %d", character_id)
    return res


def scan_text(text: str, own_names=(), cfg: dict | None = None,
              on_result=None, use_cache: bool = True,
              on_stage=None) -> ScanResult:
    """The whole pipeline.

    `on_result` is called once per pilot as answers land, `on_stage(stage, n)`
    when the pipeline reaches a point worth putting on screen. Neither fires on
    a refusal: junk in the clipboard is the normal case and must stay silent.
    """
    cfg = cfg or config.load()
    started = time.time()

    verdict = guard.inspect(text, own_names=own_names)
    if not verdict.accepted:
        return ScanResult(False, "rejected", verdict.reason,
                          reason_key=verdict.reason_key,
                          reason_args=verdict.reason_args)

    _stage(on_stage, STAGE_RESOLVING, len(verdict.names))

    # Stage 4: ESI decides what is really a character. Anything it does not
    # know is dropped without a word -- that is what keeps a stray copy quiet.
    resolved = esi.resolve_names(verdict.names)
    if not resolved:
        return ScanResult(False, "rejected",
                          i18n.en("reason.no_name_resolved"),
                          reason_key="reason.no_name_resolved")

    unresolved = tuple(n for n in verdict.names if n.casefold() not in resolved)
    pilots = [(cid, nm) for cid, nm in resolved.values()]
    _stage(on_stage, STAGE_SCANNING, len(pilots))

    max_pages = max(1, int(cfg.get("list_pages", 1)))
    ttl = float(cfg.get("negative_ttl_days", 7))
    filters = analyze.Filters.from_config(cfg)
    # One pilot is fast enough that stopping early saves nothing worth having,
    # and a complete answer on a name somebody typed deliberately is worth
    # more than the fraction of a second. See STOP_AT_FIRST_MIN.
    stop_at_first = (bool(cfg.get("stop_at_first", True))
                     and len(pilots) > STOP_AT_FIRST_MIN)
    sets = cyno_sets.load()

    out: list = []
    lock = threading.Lock()

    def emit(r):
        if on_result is None:
            return
        with lock:
            try:
                on_result(r)
            except Exception:
                log.exception("on_result callback failed")

    # Cached pilots go out FIRST, before a single request leaves the machine.
    # Only pilots caught with a cyno are cached, so this puts the dangerous
    # names on screen instantly and leaves the network to fill in the rest.
    pending: list = []
    for cid, nm in pilots:
        entry = cache.get_pilot(cid) if use_cache else None
        if entry is not None and cache.is_fresh(entry, ttl, filters):
            r = _from_cache(entry, cid, nm, filters)
            out.append(r)
            emit(r)
        else:
            pending.append((cid, nm))

    def work(item):
        cid, nm = item
        # use_cache=False: this pilot was already looked up above, and looking
        # again would only pay for the miss twice.
        r = scan_pilot(cid, nm, sets, max_pages, ttl, use_cache=False,
                       filters=filters, stop_at_first=stop_at_first)
        emit(r)
        return r

    if pending:
        workers = min(ZKB_CONCURRENCY, len(pending))
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            out.extend(ex.map(work, pending))

    return ScanResult(True, verdict.mode, "", out, verdict.own_seen,
                      unresolved, time.time() - started)


def _stage(on_stage, stage: str, n: int) -> None:
    if on_stage is None:
        return
    try:
        on_stage(stage, n)
    except Exception:
        log.exception("on_stage callback failed")
