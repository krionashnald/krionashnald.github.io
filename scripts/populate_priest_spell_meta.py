"""Phase 2: populate `sph` (sphere) and `cls` (class eligibility) on all 110
priest spells in data/spells-vanilla.json.

Source: AD&D 2e Player's Handbook / Priest's Handbook sphere assignments as
implemented in BG2 EE. Only the 15 BG2 spheres are used; druid-exclusive
spheres (plant, animal, weather) are folded into the closest BG2 sphere —
this does not affect cleric deity filtering because those spells are not on
the cleric list.

Class codes: cleric, druid, ranger, paladin, shaman
- Ranger caps at L3, Paladin caps at L4, Shaman caps at L6.
- Existing `sph` entries are preserved unless this map supplies different data.
"""
import json
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPELLS_PATH = os.path.join(ROOT, "data", "spells-vanilla.json")

# ref -> (sph_list, cls_list)
# sph: list of sphere IDs from spell-tables.json sphereList
# cls: list of class IDs that can cast this spell
META = {
    # Level 1
    "SPPR101": (["protection"],           ["cleric", "paladin"]),
    "SPPR102": (["combat"],               ["cleric", "paladin"]),
    "SPPR103": (["charm"],                ["cleric", "paladin"]),
    "SPPR104": (["healing"],              ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR105": (["divination"],           ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR106": (["summoning"],            ["druid", "ranger", "shaman"]),
    "SPPR107": (["combat"],               ["cleric"]),
    "SPPR108": (["protection"],           ["cleric", "paladin"]),
    "SPPR109": (["protection"],           ["cleric", "paladin"]),
    "SPPR110": (["protection"],           ["cleric"]),
    "SPPR111": (["combat"],               ["druid", "ranger", "shaman"]),
    "SPPR112": (["combat"],               ["cleric", "druid", "shaman"]),
    "SPPR113": (["sun"],                  ["cleric", "druid", "shaman"]),

    # Level 2
    "SPPR201": (["combat", "healing"],    ["cleric", "paladin"]),
    "SPPR202": (["protection"],           ["druid", "ranger", "shaman"]),
    "SPPR203": (["combat"],               ["cleric"]),
    "SPPR204": (["charm"],                ["druid", "ranger", "shaman"]),
    "SPPR205": (["combat"],               ["cleric", "paladin"]),
    "SPPR206": (["divination"],           ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR207": (["combat", "elemental"],  ["druid", "ranger", "shaman"]),
    "SPPR208": (["creation", "healing"],  ["druid", "ranger"]),
    "SPPR209": (["charm"],                ["cleric"]),
    "SPPR210": (["divination"],           ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR211": (["protection", "elemental"], ["cleric", "druid", "ranger", "shaman"]),
    "SPPR212": (["combat"],               ["cleric"]),
    "SPPR213": (["healing"],              ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR214": (["combat"],               ["cleric", "paladin"]),

    # Level 3 (Ranger cap = L3; rangers get druid-list spells here)
    "SPPR301": (["summoning"],            ["cleric"]),
    "SPPR302": (["elemental"],            ["druid", "ranger", "shaman"]),
    "SPPR303": (["healing"],              ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR304": (["healing"],              ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR305": (["protection"],           ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR306": (["combat", "protection"], ["cleric"]),
    "SPPR307": (["charm"],                ["druid", "ranger", "shaman"]),
    "SPPR308": (["divination"],           ["cleric"]),
    "SPPR309": (["protection"],           ["cleric"]),
    "SPPR310": (["protection", "elemental"], ["cleric", "druid", "ranger", "paladin", "shaman"]),
    "SPPR311": (["protection"],           ["cleric", "paladin"]),
    "SPPR312": (["protection", "healing"],["cleric", "paladin"]),
    "SPPR313": (["charm"],                ["cleric"]),
    "SPPR314": (["combat"],               ["cleric"]),
    "SPPR315": (["summoning"],            ["druid", "ranger", "shaman"]),
    "SPPR316": (["protection"],           ["druid", "ranger", "shaman"]),

    # Level 4
    "SPPR401": (["summoning"],            ["druid", "shaman"]),
    "SPPR402": (["summoning"],            ["druid", "shaman"]),
    "SPPR403": (["combat"],               ["cleric"]),
    "SPPR404": (["charm"],                ["cleric"]),
    "SPPR405": (["healing"],              ["cleric", "druid", "paladin", "shaman"]),
    "SPPR406": (["protection"],           ["cleric", "paladin"]),
    "SPPR407": (["protection", "combat"], ["cleric", "paladin"]),
    "SPPR408": (["divination"],           ["cleric"]),
    "SPPR409": (["protection"],           ["cleric", "druid", "paladin", "shaman"]),
    "SPPR410": (["combat"],               ["cleric", "paladin"]),
    "SPPR411": (["healing"],              ["cleric", "paladin"]),
    "SPPR412": (["charm"],                ["cleric"]),
    "SPPR413": (["protection"],           ["cleric", "paladin"]),
    "SPPR414": (["healing"],              ["cleric", "druid", "paladin"]),
    "SPPR415": (["combat"],               ["druid", "shaman"]),
    "SPPR416": (["protection"],           ["cleric", "paladin"]),
    "SPPR417": (["protection", "elemental"], ["cleric", "druid", "paladin", "shaman"]),

    # Level 5 (Ranger cap = 3; Paladin cap = 4 — neither on L5+)
    "SPPR501": (["summoning"],            ["druid", "shaman"]),
    "SPPR502": (["protection", "chaos"],  ["cleric"]),
    "SPPR503": (["healing"],              ["cleric", "druid", "shaman"]),
    "SPPR504": (["combat", "elemental"],  ["cleric", "druid", "shaman"]),
    "SPPR505": (["charm"],                ["cleric"]),
    "SPPR506": (["summoning"],            ["druid", "shaman"]),
    "SPPR507": (["protection"],           ["druid", "shaman"]),
    "SPPR508": (["protection"],           ["cleric"]),
    "SPPR509": (["healing"],              ["cleric"]),
    "SPPR510": (["healing"],              ["cleric"]),
    "SPPR511": (["combat"],               ["cleric"]),
    "SPPR512": (["combat"],               ["cleric"]),
    "SPPR513": (["divination"],           ["cleric", "druid", "shaman"]),
    "SPPR514": (["combat"],               ["cleric"]),
    "SPPR515": (["protection"],           ["druid", "shaman"]),
    "SPPR516": (["protection"],           ["cleric"]),

    # Level 6
    "SPPR601": (["summoning"],            ["cleric"]),
    "SPPR602": (["summoning"],            ["druid", "shaman"]),
    "SPPR603": (["combat", "protection"], ["cleric"]),
    "SPPR604": (["combat", "sun"],        ["cleric"]),
    "SPPR605": (["summoning"],            ["druid", "shaman"]),
    "SPPR606": (["summoning", "elemental"], ["cleric", "druid", "shaman"]),
    "SPPR607": (["combat"],               ["cleric"]),
    "SPPR608": (["sun", "combat"],        ["cleric"]),
    "SPPR609": (["elemental", "combat"],  ["druid"]),
    "SPPR610": (["combat"],               ["cleric"]),
    "SPPR611": (["healing"],              ["cleric"]),
    "SPPR612": (["protection"],           ["cleric"]),
    "SPPR613": (["sun"],                  ["cleric"]),
    "SPPR614": (["divination"],           ["cleric"]),

    # Level 7
    "SPPR701": (["chaos"],                ["cleric"]),
    "SPPR702": (["summoning", "elemental"], ["cleric", "druid"]),
    "SPPR703": (["summoning"],            ["druid"]),
    "SPPR704": (["elemental"],            ["druid"]),
    "SPPR705": (["elemental", "destruction"], ["druid"]),
    "SPPR706": (["summoning"],            ["cleric"]),
    "SPPR707": (["healing"],              ["cleric"]),
    "SPPR708": (["combat"],               ["cleric"]),
    "SPPR709": (["charm"],                ["druid"]),
    "SPPR710": (["healing"],              ["cleric"]),
    "SPPR711": (["healing"],              ["cleric"]),
    "SPPR712": (["protection"],           ["cleric"]),
    "SPPR713": (["sun", "destruction"],   ["cleric"]),
    "SPPR714": (["summoning"],            ["cleric"]),
    "SPPR715": (["charm"],                ["cleric"]),
    "SPPR716": (["charm"],                ["cleric"]),
    "SPPR717": (["combat"],               ["cleric"]),
    "SPPR718": (["combat"],               ["cleric"]),
    "SPPR719": (["combat"],               ["cleric"]),
    "SPPR720": (["protection"],           ["cleric"]),
}


def main():
    with open(SPELLS_PATH, "r", encoding="utf-8") as f:
        spells = json.load(f, object_pairs_hook=OrderedDict)

    applied_sph = 0
    applied_cls = 0
    missing = []
    extras = []

    # Apply META
    for ref, (sph, cls) in META.items():
        entry = spells.get(ref)
        if not entry or entry.get("type") != "priest":
            extras.append(ref)
            continue
        entry["sph"] = list(sph)
        entry["cls"] = list(cls)
        applied_sph += 1
        applied_cls += 1

    # Find priest spells not covered
    for ref, v in spells.items():
        if v.get("type") == "priest" and "sph" not in v:
            missing.append(ref)

    with open(SPELLS_PATH, "w", encoding="utf-8") as f:
        json.dump(spells, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Applied sph+cls to {applied_sph} priest spells")
    if extras:
        print(f"META refs not in vanilla (dropped): {extras}")
    if missing:
        print(f"Still missing sph: {missing}")
    else:
        print("All priest spells now carry sph + cls. [OK]")


if __name__ == "__main__":
    main()
