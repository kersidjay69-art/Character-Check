"""Generate cyno_sets.json from an EVE SDE database.

The runtime never opens an SDE: this script bakes everything the app needs
into a small JSON artifact that is committed to the repo.

Why group 658 instead of a name LIKE:
    Group 658 "Cynosural Field Generator" (category 7 = Module) holds exactly
    the three fittable cyno modules and nothing else -- no blueprints, no
    Standup structure module, no NPC field. A name match would need a hand
    maintained exclusion list; the group needs none, and a future faction
    variant lands in it automatically.

Why canFit* attributes are resolved BY NAME:
    There are 32 of them (canFitShipGroup01..20, canFitShipType1..12) and the
    numbering is not contiguous -- 1298,1299,1300,1301,1872,1879,1880,... A
    hardcoded range silently drops hulls. 28646 alone uses 1301, 1872 and 1879.

Groups and types are expanded separately and only merged at the very end.
Venture is groupID 25 "Frigate" and Etana/Rabisu are groupID 832 "Logistics",
so folding a canFitShipType value back into its group would flag every T1
frigate and every logistics cruiser in the game.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time

CYNO_MODULE_GROUP = 658  # "Cynosural Field Generator", category 7 (Module)
SHIP_CATEGORY = 6

# Two SDE dialects are supported. pyfa ships lowercase table names and a single
# `value` column; the Fuzzwork dump used by Jump planer uses CamelCase and
# splits the value into valueInt/valueFloat.
DIALECTS = {
    "pyfa": {
        "probe": "dgmattribs",
        "types": "SELECT typeID, typeName, groupID FROM invtypes WHERE published=1",
        "groups": "SELECT groupID, name, categoryID FROM invgroups",
        "attr_names": "SELECT attributeID, attributeName FROM dgmattribs",
        "type_attrs": "SELECT typeID, attributeID, value FROM dgmtypeattribs",
        "meta": "SELECT typeID, metaGroupID FROM invtypes WHERE published=1",
    },
    "fuzzwork": {
        "probe": "dgmAttributeTypes",
        "types": "SELECT typeID, typeName, groupID FROM invTypes WHERE published=1",
        "groups": "SELECT groupID, groupName, categoryID FROM invGroups",
        "attr_names": "SELECT attributeID, attributeName FROM dgmAttributeTypes",
        "type_attrs": (
            "SELECT typeID, attributeID, COALESCE(valueInt, valueFloat) "
            "FROM dgmTypeAttributes"
        ),
        "meta": "SELECT typeID, metaGroupID FROM invTypes WHERE published=1",
    },
}


def detect_dialect(conn: sqlite3.Connection) -> str:
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for name, spec in DIALECTS.items():
        if spec["probe"] in have:
            return name
    raise SystemExit(
        "Unrecognised SDE: needs either `dgmattribs` (pyfa) or "
        "`dgmAttributeTypes` (Fuzzwork). Found %d tables." % len(have))


def build(db_path: str) -> dict:
    conn = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    dialect = detect_dialect(conn)
    q = DIALECTS[dialect]

    types = {tid: (name, gid) for tid, name, gid in conn.execute(q["types"])}
    groups = {gid: (name, cat) for gid, name, cat in conn.execute(q["groups"])}
    attr_names = dict(conn.execute(q["attr_names"]))

    group_attrs = {a for a, n in attr_names.items() if n.startswith("canFitShipGroup")}
    type_attrs = {a for a, n in attr_names.items() if n.startswith("canFitShipType")}
    if not group_attrs or not type_attrs:
        raise SystemExit("No canFitShip* attributes found -- wrong SDE?")

    modules = {tid: types[tid][0] for tid, (_n, gid) in types.items()
               if gid == CYNO_MODULE_GROUP}
    if not modules:
        raise SystemExit("Group %d is empty -- wrong SDE?" % CYNO_MODULE_GROUP)

    # Collect canFit* values per module, keeping groups and types apart.
    per_module = {tid: {"groups": set(), "types": set()} for tid in modules}
    for tid, aid, value in conn.execute(q["type_attrs"]):
        if tid not in per_module or value is None:
            continue
        val = int(value)
        if aid in group_attrs:
            per_module[tid]["groups"].add(val)
        elif aid in type_attrs:
            per_module[tid]["types"].add(val)
    # Tech tier, read before the connection goes away.
    meta = {t: m for t, m in conn.execute(q["meta"]) if t in types}
    conn.close()

    # Expand each module's reach into a flat hull set, then merge. `hulls` maps
    # a ship typeID to the modules it can carry, which is what the runtime and
    # the UI both need -- no group lookup at scan time.
    hulls = {}
    by_group = {}
    for mod_id, reach in per_module.items():
        for gid in reach["groups"]:
            if gid not in groups:
                continue
            by_group.setdefault(gid, set()).add(mod_id)
            for tid, (_name, tgid) in types.items():
                if tgid == gid:
                    hulls.setdefault(tid, set()).add(mod_id)
        for tid in reach["types"]:
            if tid in types:
                hulls.setdefault(tid, set()).add(mod_id)

    # A hull is "indy" only if the sole module it takes is the industrial cyno,
    # which bridges nothing but jump freighters and the Rorqual.
    indy_only = {tid for tid, mods in hulls.items() if mods == {52694}}

    out = {
        "_generated_by": "sde/build_cyno_sets.py",
        "_built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "_sde_path": os.path.abspath(db_path),
        "_sde_dialect": dialect,
        "_module_group": CYNO_MODULE_GROUP,
        "modules": {str(t): n for t, n in sorted(modules.items())},
        "hull_groups": {
            str(g): {"name": groups[g][0], "modules": sorted(by_group[g])}
            for g in sorted(by_group)
        },
        "hulls": {
            str(t): {
                "name": types[t][0],
                "group_id": types[t][1],
                "group_name": groups.get(types[t][1], ("?",))[0],
                "class": "indy" if t in indy_only else "combat",
                "modules": sorted(hulls[t]),
            }
            for t in sorted(hulls)
        },
        # Every published ship, purely so findings can be labelled. This is
        # needed because evidence A (a cyno in a high slot) is NOT limited to
        # the hulls above: before CCP added the canFitShipGroup restriction,
        # cynos were routinely fitted to rookie frigates, and real killmails
        # from 2014-2018 show exactly that (Velator, Ibis). Without these names
        # such a finding renders as "type 606".
        "ship_names": {
            str(t): types[t][0] for t, (_n, gid) in types.items()
            if groups.get(gid, (None, None))[1] == SHIP_CATEGORY
        },
        # Tech tier, for the corner badge the UI draws itself. 1 (Tech I) and
        # NULL (rookie corvettes) are omitted -- they carry no badge, so
        # storing them would only pad the artifact.
        #
        # This exists because CCP's image server composites the badge onto
        # only SOME icons: of the 37 Tech II cyno hulls, 25 come back without
        # one (Falcon, Rapier, Onyx, Widow, every Blockade Runner and DST),
        # while Jaguar, Redeemer and all four Tech III hulls have it. There is
        # no pattern to it, so the badge cannot be left to the server.
        "meta_groups": {
            str(t): m for t, m in sorted(meta.items())
            if m not in (None, 1)
            and groups.get(types[t][1], (None, None))[1] == SHIP_CATEGORY
        },
    }

    non_ship = {t: types[t][1] for t in hulls
                if groups.get(types[t][1], (None, None))[1] != SHIP_CATEGORY}
    if non_ship:
        out["_warning_non_ship_hulls"] = non_ship
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build cyno_sets.json from an SDE")
    ap.add_argument("--sde", default=r"f:\123\fleet-manager-online\dps\data\eve.db",
                    help="path to an SDE sqlite file (pyfa or Fuzzwork dialect)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__),
                                                  "cyno_sets.json"))
    args = ap.parse_args()

    if not os.path.exists(args.sde):
        print("SDE not found: %s" % args.sde, file=sys.stderr)
        return 2

    data = build(args.sde)

    tmp = args.out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    os.replace(tmp, args.out)

    print("dialect      : %s" % data["_sde_dialect"])
    print("modules      : %d" % len(data["modules"]))
    for tid, name in data["modules"].items():
        print("   %s  %s" % (tid, name))
    print("hull groups  : %d" % len(data["hull_groups"]))
    for gid, g in data["hull_groups"].items():
        print("   %-6s %-26s <- %s" % (gid, g["name"], g["modules"]))
    combat = sum(1 for h in data["hulls"].values() if h["class"] == "combat")
    print("hulls        : %d  (combat %d, indy %d)"
          % (len(data["hulls"]), combat, len(data["hulls"]) - combat))
    print("ship names   : %d" % len(data["ship_names"]))
    if "_warning_non_ship_hulls" in data:
        print("WARNING non-ship hulls: %s" % data["_warning_non_ship_hulls"])
    print("written      : %s (%d bytes)" % (args.out, os.path.getsize(args.out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
