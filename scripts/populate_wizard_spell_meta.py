"""Phase 3: populate `cls`, `scr`, `si` on all 176 wizard spells.

Defaults (AD&D 2e / BG2 vanilla):
- cls: [mage, sorcerer, bard] for L1-L6, [mage, sorcerer] for L7-L9 (bard cap=6)
- scr: true (all vanilla wizard spells are scroll-learnable including Wish/Limited Wish)
- si:  minimum INT to scribe, derived from spell level:
       L1-L4 -> 9, L5 -> 10, L6 -> 12, L7 -> 14, L8 -> 16, L9 -> 18

Per-spell overrides (for spells that diverge from defaults) go in OVERRIDES.
"""
import json
import os
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPELLS_PATH = os.path.join(ROOT, "data", "spells-vanilla.json")

# Minimum INT by spell level to learn/scribe the spell
SCRIBE_INT_BY_LEVEL = {
    1: 9, 2: 9, 3: 9, 4: 9,
    5: 10, 6: 12, 7: 14, 8: 16, 9: 18,
}

# Per-spell overrides — for the rare spell that doesn't follow defaults.
# (BG2 vanilla has very few such cases; all SPWI spells are scrollable and
# bards get the full mage list up to their level cap.)
OVERRIDES = {
    # Example placeholder — no known vanilla overrides for cls/scr/si.
    # If we later discover bard-excluded spells, add them here:
    #   "SPWI508": {"cls": ["mage", "sorcerer"]},   # hypothetical bard exclude
}


def main():
    with open(SPELLS_PATH, "r", encoding="utf-8") as f:
        spells = json.load(f, object_pairs_hook=OrderedDict)

    applied = 0
    skipped = []
    for ref, entry in spells.items():
        if entry.get("type") != "wizard":
            continue
        lv = entry.get("lv")
        if not isinstance(lv, int) or lv < 1 or lv > 9:
            skipped.append((ref, entry.get("n"), lv))
            continue

        # Default class eligibility
        cls = ["mage", "sorcerer"]
        if lv <= 6:
            cls.append("bard")

        entry["cls"] = cls
        entry["scr"] = True
        entry["si"] = SCRIBE_INT_BY_LEVEL[lv]

        # Apply overrides if present
        if ref in OVERRIDES:
            for k, v in OVERRIDES[ref].items():
                entry[k] = v

        applied += 1

    with open(SPELLS_PATH, "w", encoding="utf-8") as f:
        json.dump(spells, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Applied cls+scr+si to {applied} wizard spells")
    if skipped:
        print(f"Skipped (bad lv): {skipped}")


if __name__ == "__main__":
    main()
