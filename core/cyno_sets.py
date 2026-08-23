"""Load the cyno_sets.json artifact built by sde/build_cyno_sets.py.

The app never opens an SDE at runtime -- everything it needs about cyno
modules and the hulls that can carry them lives in this one JSON file.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

def _artifact_path() -> str:
    """Where cyno_sets.json lives, running from source or from a frozen exe.

    PyInstaller unpacks bundled data under `sys._MEIPASS`. Walking up from
    `__file__` happens to land in the same place today, but that is an
    implementation detail of how frozen modules are named -- asking directly
    is the contract, and this file is the one thing the app cannot start
    without.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "sde", "cyno_sets.json")


_DEFAULT = _artifact_path()


@dataclass(frozen=True)
class CynoSets:
    modules: dict = field(default_factory=dict)       # type_id -> module name
    hulls: dict = field(default_factory=dict)         # type_id -> hull info dict
    ship_names: dict = field(default_factory=dict)    # type_id -> name, all ships
    meta_groups: dict = field(default_factory=dict)   # type_id -> metaGroupID
    built_at: str = ""

    def is_module(self, type_id: int) -> bool:
        return type_id in self.modules

    def is_hull(self, type_id: int) -> bool:
        return type_id in self.hulls

    def is_ship(self, type_id: int) -> bool:
        """Is this an actual ship (SDE category 6)?

        Killmails are also written for deployables and structures. A Mobile
        Tractor Unit that scooped a cyno module off a wreck and then died
        produces a killmail whose "cargo" holds a cyno -- which says nothing
        about the owner. See analyze.analyze_killmail.
        """
        return type_id in self.ship_names

    def module_name(self, type_id: int) -> str:
        return self.modules.get(type_id, "type %d" % type_id)

    def hull_name(self, type_id: int) -> str:
        """Name any ship, not just cyno-capable ones: evidence A can land on a
        rookie frigate from before the canFitShipGroup restriction existed."""
        h = self.hulls.get(type_id)
        if h:
            return h["name"]
        return self.ship_names.get(type_id) or "type %d" % type_id

    def hull_class(self, type_id: int) -> str:
        h = self.hulls.get(type_id)
        return h["class"] if h else "unknown"

    def hull_group(self, type_id: int):
        """SDE groupID of a cyno hull, or None if it is not one."""
        h = self.hulls.get(type_id)
        return h["group_id"] if h else None

    def meta_group(self, type_id: int):
        """Tech tier: 2 = Tech II, 14 = Tech III, 4 = faction, None = plain.

        Tech I and the rookie corvettes are simply absent from the artifact --
        they have no badge to draw.
        """
        return self.meta_groups.get(type_id)

    def can_fit(self, type_id: int, module_type_id: int) -> bool:
        """Can this hull mount THIS cyno, by the current SDE?

        Two different questions hide here, and both used to be answered wrong:

        * a hull outside the cyno set entirely -- a Velator, an Ibis, a
          freighter. Cynos really were fitted to rookie frigates before the
          canFitShipGroup restriction, so the killmails are genuine, but the
          pilot cannot do it today and the evidence predicts nothing.
        * a real cyno hull carrying the WRONG cyno. A Stealth Bomber or a
          Covert Ops takes only the covert variant; a Hauler only the
          industrial one. `hulls[id]["modules"]` has always listed exactly
          which -- nothing was reading it.
        """
        h = self.hulls.get(type_id)
        return bool(h) and module_type_id in h["modules"]


_cache: CynoSets | None = None


def load(path: str | None = None, force: bool = False) -> CynoSets:
    """Load and memoise the artifact. Raises if it is missing or empty -- a
    silently empty set would make every pilot look clean, which is the one
    failure mode this tool must never have."""
    global _cache
    if _cache is not None and not force and path is None:
        return _cache

    p = path or _DEFAULT
    with open(p, "r", encoding="utf-8") as fh:
        raw = json.load(fh)

    modules = {int(k): v for k, v in raw.get("modules", {}).items()}
    hulls = {int(k): v for k, v in raw.get("hulls", {}).items()}
    ship_names = {int(k): v for k, v in raw.get("ship_names", {}).items()}
    meta_groups = {int(k): v for k, v in raw.get("meta_groups", {}).items()}
    if not modules or not hulls:
        raise ValueError("%s has no modules/hulls -- rerun sde/build_cyno_sets.py" % p)

    sets = CynoSets(modules=modules, hulls=hulls, ship_names=ship_names,
                    meta_groups=meta_groups,
                    built_at=raw.get("_built_at", ""))
    if path is None:
        _cache = sets
    return sets
