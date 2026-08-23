"""Pure classification of a killmail against one character. No I/O.

Three independent pieces of evidence, all read from the same killmail:

  A  fitted     -- died with a cyno module in a HIGH SLOT of the hull itself
  A' cargo      -- died with a cyno module aboard, but not fitted
  B  hull_lost  -- died in a hull that can carry a cyno
  C  hull_flown -- appeared as an attacker flying such a hull

Priority comes from WHICH module was involved, but the hull decides whether a
module in the HOLD counts at all: on a combat cyno hull a stowed cyno is one
undock away from being lit, on a freighter it is freight.

A hull with nothing aboard is weaker still, and is graded in three:
industrial hulls are not recorded at all (a lost Venture is a miner), Covert
Ops and Strategic Cruisers are recorded but score `seen` rather than a warning
(everybody flies one), and the rest score `hull`. See `Finding.level` for the
full table and `_QUIET_HULL_GROUPS` for the second rule.

Four traps, each verified against real killmails and the SDE, each covered
by a named test in tests/test_analyze.py:

  0. The hull must be able to mount THAT cyno today (`sets.can_fit`). Cynos
     really were fitted to rookie frigates before canFitShipGroup existed, and
     Stealth Bombers really did carry the non-covert one -- 727 of 1493 stored
     module findings were exactly this. The killmails are genuine; what they
     predict is nothing, because the pilot cannot repeat the fit. See the note
     in CLAUDE.md: this reverses an earlier decision, deliberately.
  1. depth == 0 is required for `fitted`. Nested items inherit their own slot
     flags: an assembled ship inside a Ship Maintenance Bay yields flag 28 at
     depth 1. Without the depth check a freighter hauling a fitted recon reads
     as "cyno fitted".
  2. A flag is not unique per slot. Loaded charges carry their module's flag,
     so one flag 27 can hold both a module and 52 rockets. Membership is
     decided by (type_id in modules) AND (flag range) together, never by flag.
  3. Hull membership comes from an explicit type set. Venture is groupID 25
     "Frigate" and Etana/Rabisu are groupID 832 "Logistics", so the artifact
     lists individual hulls rather than groups -- see sde/build_cyno_sets.py.
"""
from __future__ import annotations

import calendar
import time
from dataclasses import dataclass

HI_SLOT_MIN = 27
HI_SLOT_MAX = 34

# Ordered worst-first; index doubles as severity for picking a pilot's level.
KIND_FITTED = "fitted"
KIND_CARGO = "cargo"
KIND_HULL_LOST = "hull_lost"
KIND_HULL_FLOWN = "hull_flown"

# Which module was involved is what sets the priority. A covert or regular cyno
# is what lights a hostile fleet on top of you; an industrial cyno bridges
# nothing but jump freighters and the Rorqual, so it ranks below a combat hull.
COMBAT_CYNO = frozenset({21096, 28646})       # Cyno I, Covert Cyno I
INDUSTRIAL_CYNO = frozenset({52694})          # Industrial Cyno

# Display order, worst first. Explicit because sorting by type_id puts 21096
# ahead of 28646, which is backwards: the covert one is the module that drops
# a fleet on you out of a cloak, and it deserves the leftmost icon.
_MODULE_RANK = {28646: 0, 21096: 1, 52694: 2}

# Ship display order inside the combat block, by SDE groupID. Recons first --
# they are the classic hotdrop scout -- then Heavy Interdictors. Everything else
# cyno-capable follows in one bucket, then industrial hulls, and the quiet
# groups below come dead last (both splits are separate, coarser keys).
_HULL_GROUP_RANK = {
    833: 0,     # Force Recon Ship
    894: 1,     # Heavy Interdiction Cruiser
}
_HULL_GROUP_OTHER = 2

# Cyno-capable, but flying one predicts nothing. Covert Ops are the explorer's
# frigates (Buzzard, Helios, Anathema, Cheetah) and Strategic Cruisers are the
# game's general-purpose ride (Legion, Loki, Tengu, Proteus) -- both turn up
# constantly on pilots who have never lit a cyno. Same reasoning that retired
# the bare Venture, applied to two combat groups.
#
# This is about the HULL ALONE. A covert cyno aboard one of these is still a
# cyno: the module rules run first and never consult this set.
_QUIET_HULL_GROUPS = frozenset({
    830,        # Covert Ops
    963,        # Strategic Cruiser
})

# Verdict levels, strongest first:
#   cyno   a covert or regular cyno module was on the pilot's ship
#   hull   died in, or killed from, a hull that can mount a combat cyno
#   indy   an industrial cyno MODULE -- never a bare industrial hull
#   seen   only a quiet hull: cyno-capable, but no threat on its own
#   none   nothing found
LEVEL_CYNO = "cyno"
LEVEL_HULL = "hull"
LEVEL_INDY = "indy"
LEVEL_SEEN = "seen"
LEVEL_NONE = "none"

_LEVEL_RANK = {LEVEL_CYNO: 4, LEVEL_HULL: 3, LEVEL_INDY: 2,
               LEVEL_SEEN: 1, LEVEL_NONE: 0}

# Every cyno module in the game. Used for sizing the module column, so it is
# the count of TYPES rather than a three somebody remembered.
ALL_CYNO = COMBAT_CYNO | INDUSTRIAL_CYNO


@dataclass(frozen=True)
class Filters:
    """What kinds of evidence a scan is asking for.

    Not a display filter -- evidence that is switched off is never extracted,
    never levelled and never stored, so the verdict genuinely does not know
    about it. That is the point: with `potential` off the `/kills/` feed
    cannot contribute a single row, which is what lets `scan` skip half its
    requests. A display-only filter would have had to fetch everything first.

    Defaults match `config.DEFAULTS`. `ALL_EVIDENCE` below is the other
    useful value: everything, which is what the pure analyser assumes when a
    caller does not care.
    """

    # Bare cyno-capable hulls -- the `hull` and `seen` verdicts. A pilot who
    # merely flew a Falcon is a maybe; off by default because the maybes are
    # most of a trade hub and each one costs a second request.
    potential: bool = False
    # The industrial cyno module. Off, and a pilot with nothing else becomes
    # `none` and drops out of the list.
    industrial: bool = True

    @classmethod
    def from_config(cls, cfg: dict | None = None) -> "Filters":
        cfg = cfg or {}
        return cls(potential=bool(cfg.get("find_potential", False)),
                   industrial=bool(cfg.get("find_industrial", True)))

    def as_bits(self) -> int:
        """A two-bit summary, so the cache row can record what it was scanned
        with in one integer column.

        The cache compares these for EQUALITY, not containment. A wider stored
        scan looks like it should serve a narrower question, and it cannot: the
        stored `ships_csv` would carry hulls the narrow question never asked
        about, while the evidence list underneath is filtered down to the
        narrow ones -- the icon row and the expansion would disagree, which is
        the one failure this project has already paid for once.
        """
        return int(self.potential) | (int(self.industrial) << 1)

    @classmethod
    def from_bits(cls, bits: int) -> "Filters":
        return cls(potential=bool(bits & 1), industrial=bool(bits & 2))


ALL_EVIDENCE = Filters(potential=True, industrial=True)


@dataclass(frozen=True)
class Finding:
    killmail_id: int
    kind: str
    km_time: float
    ship_type_id: int | None = None
    module_type_id: int | None = None
    system_id: int | None = None

    # "combat" | "indy" | "unknown". Defaults to unknown on purpose: it used to
    # default to "combat", which quietly asserted that every hull carrying a
    # cyno was a combat hull -- including the freighter hauling a crate of them.
    hull_class: str = "unknown"

    # SDE groupID of the hull, or None. Rides along for the same reason
    # `hull_class` does: the level rules need it and the cache row cannot
    # answer it. Appended at the END -- Finding is built positionally, and a
    # field inserted mid-list silently shifts `system_id`.
    hull_group: int | None = None

    @property
    def level(self) -> str:
        """This finding on its own, as a verdict.

        | evidence                                   | level |
        |--------------------------------------------|-------|
        | combat cyno fitted                         | cyno  |
        | combat cyno in hold, on a combat cyno hull | cyno  |
        | combat cyno in hold, on anything else      | none  |
        | industrial cyno fitted                     | indy  |
        | industrial cyno in hold, on a combat hull  | indy  |
        | combat cyno hull, no module                | hull  |
        | quiet hull (Covert Ops, T3), no module     | seen  |
        | industrial hull, no module                 | none  |
        """
        if self.module_type_id is not None:
            # In the hold it only counts on a hull built to light one: the
            # pilot may have unfitted it an undock ago. On a freighter or a
            # Venture the same module is cargo, and cargo proves nothing.
            if self.kind == KIND_CARGO and self.hull_class != "combat":
                return LEVEL_NONE
            return (LEVEL_CYNO if self.module_type_id in COMBAT_CYNO
                    else LEVEL_INDY)
        # No module aboard: only a combat cyno hull is evidence. A lost Venture
        # or Badger with nothing in it is a hauler, not a scout -- 842 of the
        # flags in the 1547-pilot hub run were exactly that.
        if self.hull_class != "combat":
            return LEVEL_NONE
        # ...and a bare Covert Ops or T3 says only that the pilot was seen in
        # one. Worth showing, not worth a warning colour. See _QUIET_HULL_GROUPS.
        if self.hull_group in _QUIET_HULL_GROUPS:
            return LEVEL_SEEN
        return LEVEL_HULL


def parse_km_time(value) -> float:
    """ESI killmail_time -> epoch seconds. Always UTC; the box may not be."""
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return 0.0
    txt = str(value).replace("Z", "").replace("T", " ")
    txt = txt.split(".")[0]
    return calendar.timegm(time.strptime(txt, "%Y-%m-%d %H:%M:%S"))


def iter_items(items, depth: int = 0):
    """Yield (item_dict, depth) over the nested victim item tree.

    Recursion is unbounded rather than one level deep: nothing guarantees a
    container never nests twice, and the depth is what trap 1 turns on.
    """
    for it in items or ():
        yield it, depth
        nested = it.get("items")
        if nested:
            yield from iter_items(nested, depth + 1)


def _wanted_module(module_type_id: int, filters: Filters) -> bool:
    """Is this module one the user asked about? See `Filters.industrial`."""
    if module_type_id in INDUSTRIAL_CYNO:
        return filters.industrial
    return True


def _hull_is_evidence(type_id: int, sets) -> bool:
    """Is this bare hull worth recording at all?

    Industrial cyno hulls are not. A lost Venture or Badger with nothing in it
    is a hauler, so the finding scored `none`, earned no icon, and did nothing
    but pad the expandable killmail list -- which is where the noise was still
    visible. The module evidence on the very same hull is untouched: an
    industrial cyno bolted into an Epithal still counts, and still gets a ship
    icon, because `ships_of` admits a non-combat hull on a fitted module.
    """
    return sets.is_hull(type_id) and sets.hull_class(type_id) != "indy"


def analyze_killmail(km: dict, character_id: int, sets,
                     filters: Filters | None = None) -> list[Finding]:
    """Return every piece of evidence this killmail carries about one pilot.

    `filters` defaults to everything, which is the honest default for a pure
    analyser: a caller who did not ask to narrow the question gets the whole
    answer. `scan` always passes the user's actual choice.
    """
    filters = filters or ALL_EVIDENCE
    out: list[Finding] = []
    km_id = km.get("killmail_id")
    if km_id is None:
        return out
    when = parse_km_time(km.get("killmail_time"))
    system_id = km.get("solar_system_id")

    victim = km.get("victim") or {}
    if victim.get("character_id") == character_id:
        hull = victim.get("ship_type_id")

        # Module evidence only counts when the victim was an actual SHIP.
        # Killmails also exist for deployables and structures: a Mobile Tractor
        # Unit (33475) that scooped a cyno off a wreck and then died reads as
        # "cyno in cargo" for its owner, which proves nothing. Caught live on a
        # real pilot's 2015 killmail.
        victim_is_ship = hull is not None and sets.is_ship(hull)

        fitted_mods: set[int] = set()
        carried_mods: set[int] = set()
        for item, depth in iter_items(victim.get("items") if victim_is_ship else None):
            type_id = item.get("item_type_id")
            if type_id is None or not sets.is_module(type_id):
                continue
            flag = item.get("flag")
            # Trap 1 + trap 2: both conditions, and only on the hull itself.
            if depth == 0 and flag is not None and HI_SLOT_MIN <= flag <= HI_SLOT_MAX:
                fitted_mods.add(type_id)
            else:
                carried_mods.add(type_id)

        # The hull class rides along on module findings too -- it is what
        # decides whether a stowed cyno counts. `hull_class` answers "unknown"
        # for hulls outside the cyno set, which is the honest answer for a
        # Velator or a freighter.
        hull_cls = sets.hull_class(hull) if hull is not None else "unknown"
        hull_grp = sets.hull_group(hull) if hull is not None else None
        for mod in sorted(fitted_mods):
            if not sets.can_fit(hull, mod) or not _wanted_module(mod, filters):
                continue
            out.append(Finding(km_id, KIND_FITTED, when, hull, mod, system_id,
                               hull_cls, hull_grp))
        # A module that is also fitted says nothing extra by being in the hold.
        for mod in sorted(carried_mods - fitted_mods):
            if not sets.can_fit(hull, mod) or not _wanted_module(mod, filters):
                continue
            out.append(Finding(km_id, KIND_CARGO, when, hull, mod, system_id,
                               hull_cls, hull_grp))

        if (filters.potential and hull is not None
                and _hull_is_evidence(hull, sets)):
            out.append(Finding(km_id, KIND_HULL_LOST, when, hull, None, system_id,
                               hull_cls, hull_grp))

    # An attacker is never the victim, so this loop can only ever produce
    # `hull_flown` -- which is exactly the evidence `potential` switches off.
    # Skipping it here is what makes skipping the whole `/kills/` request in
    # `scan` a no-op rather than a shortcut.
    for att in (km.get("attackers") or ()) if filters.potential else ():
        if att.get("character_id") != character_id:
            continue
        ship = att.get("ship_type_id")
        if ship is not None and _hull_is_evidence(ship, sets):
            out.append(Finding(km_id, KIND_HULL_FLOWN, when, ship, None, system_id,
                               sets.hull_class(ship), sets.hull_group(ship)))

    return out


def level_of(findings) -> str:
    """Strongest level across a pilot's findings."""
    best = LEVEL_NONE
    for f in findings:
        if _LEVEL_RANK[f.level] > _LEVEL_RANK[best]:
            best = f.level
    return best


def _field(f, key, default=None):
    """Findings arrive as dataclasses (fresh) or as dicts (from the cache).

    The cache row is the lossy one -- it stores neither `hull_class` nor
    `hull_group` -- so every reader has to tolerate the key simply being
    absent, and re-derive it from the SDE when it matters.
    """
    if hasattr(f, "kind"):
        return getattr(f, key, default)
    return f[key] if key in f else default


def _hull_class(f, sets=None) -> str:
    """The finding's hull class, re-derived from the SDE when it was not stored."""
    cls = _field(f, "hull_class")
    if cls:
        return cls
    ship = _field(f, "ship_type_id")
    if sets is not None and ship is not None:
        return sets.hull_class(ship)
    return "unknown"


def _hull_group_of(f, sets=None):
    """The finding's hull group, re-derived from the SDE when it was not stored."""
    grp = _field(f, "hull_group")
    if grp is not None:
        return grp
    ship = _field(f, "ship_type_id")
    if sets is not None and ship is not None:
        return sets.hull_group(ship)
    return None


def is_quiet(f, sets=None) -> bool:
    """Does this finding rest on a hull that predicts nothing? See LEVEL_SEEN.

    True only for a BARE quiet hull. A Buzzard with a covert cyno bolted into
    it is a cyno finding and nothing about it is quiet -- which is why this
    asks the FINDING, not the ship. The same Buzzard can produce both kinds
    for one pilot, and `ships_of` has to keep the louder answer.
    """
    if _field(f, "module_type_id") is not None:
        return False
    return _hull_group_of(f, sets) in _QUIET_HULL_GROUPS


def counts_as_carried(f, sets=None) -> bool:
    """Is this finding's module the pilot's own cyno, rather than freight?

    Same rule as `Finding.level`, spelled once so the icons and the verdict can
    never disagree about a hauler.
    """
    if _field(f, "module_type_id") is None:
        return False
    return not (_field(f, "kind") == KIND_CARGO
                and _hull_class(f, sets) != "combat")


def modules_of(findings, sets=None) -> list:
    """Which cyno modules this pilot was actually caught with, worst first.

    This is the answer to "cyno -- and if so, which one", so it is derived
    from the findings rather than stored: a module seen once is a fact that
    cannot later become untrue.
    """
    seen = {_field(f, "module_type_id")
            for f in findings if counts_as_carried(f, sets)}
    seen.discard(None)
    return sorted(seen, key=lambda m: (_MODULE_RANK.get(m, 99), m))


def _hull_rank(ship, sets) -> int:
    """Where a combat hull sits in the display order. See _HULL_GROUP_RANK."""
    if sets is None:
        return _HULL_GROUP_OTHER
    return _HULL_GROUP_RANK.get(sets.hull_group(ship), _HULL_GROUP_OTHER)


def ships_of(findings, sets=None) -> list:
    """Which ships to show for this pilot, most dangerous first.

    A combat cyno hull speaks for itself. An industrial hull earns its place
    only when a cyno was actually bolted onto it -- otherwise every miner who
    ever lost a Venture would be wearing a ship icon.

    Order: recons, heavy interdictors, other combat hulls, industrials, and
    dead last the quiet hulls. Industrials outrank them on purpose: an
    industrial in this row means a cyno was fitted, which is evidence, while a
    bare Legion means nothing. Within a bucket, by type_id, so the row never
    reshuffles between two scans of the same pilot.
    """
    # Keyed by ship rather than collected as a set of keys: one hull can appear
    # in several findings with different keys -- a Buzzard that was flown bare
    # AND once had a cyno in it -- and a set would keep both, drawing the icon
    # twice and once in the wrong place. The loudest key wins.
    best: dict = {}
    for f in findings:
        ship = _field(f, "ship_type_id")
        if ship is None:
            continue
        is_combat = _hull_class(f, sets) == "combat"
        fitted_module = (_field(f, "kind") == KIND_FITTED
                         and _field(f, "module_type_id") is not None)
        if not (is_combat or fitted_module):
            continue
        key = (is_quiet(f, sets), not is_combat, _hull_rank(ship, sets), ship)
        if ship not in best or key < best[ship]:
            best[ship] = key
    return [key[-1] for key in sorted(best.values())]


def group_findings(findings) -> list[dict]:
    """Collapse a pilot's evidence to one row per (kind, ship, module).

    The expandable list used to be one row per killmail, newest first, capped
    at fifty -- and on a pilot who flies the same hull every day that cap is
    spent inside a week. LIJaman had 62 findings across six hulls; the fifty
    most recent were all the same Legion, so the Marshal and the Redeemer that
    his icon row (correctly) showed had no visible explanation anywhere. The
    icons were right and the list was lying, which is the worse way round.

    Grouping removes the disagreement by construction: every icon now has a
    row. `killmail_id` and `km_time` are the newest of the group, so a
    double-click still opens a real killmail; `n` is how many there were.

    Idempotent -- re-grouping already-grouped rows sums their `n` instead of
    counting them as one each.
    """
    groups: dict = {}
    for f in findings:
        key = (_field(f, "kind"), _field(f, "ship_type_id"),
               _field(f, "module_type_id"))
        when = _field(f, "km_time") or 0.0
        count = _field(f, "n", 1) or 1
        row = groups.get(key)
        if row is None:
            groups[key] = {
                "kind": key[0], "ship_type_id": key[1],
                "module_type_id": key[2],
                "killmail_id": _field(f, "killmail_id"),
                "km_time": when, "system_id": _field(f, "system_id"),
                "n": count,
            }
            continue
        row["n"] += count
        if when > row["km_time"]:
            row["killmail_id"] = _field(f, "killmail_id")
            row["km_time"] = when
            row["system_id"] = _field(f, "system_id")
    return sorted(groups.values(), key=lambda r: -r["km_time"])
