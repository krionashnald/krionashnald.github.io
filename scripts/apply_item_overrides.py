#!/usr/bin/env python3
"""
apply_item_overrides.py — Apply manual data overrides to items-vanilla.json.

For items where the .itm binary has incomplete or wrong data (e.g., VISCLCK
mage robes with no usability restrictions), this script patches them.

Re-runnable: applies overrides idempotently.

Usage: python scripts/apply_item_overrides.py [--write]
"""

import json, os, sys, struct

PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ITEMS = os.path.join(PROJ, "data", "items-vanilla.json")

# Generic item names that indicate creature/internal-only equipment
# when combined with no description and not-droppable + no-animation flags.
GENERIC_NAMES = {
    "Ring", "Helmet", "Helm", "Cloak", "Robe", "Boots", "Belt", "Gloves",
    "Bracers", "Amulet", "Necklace", "Shield", "Buckler", "Armor",
    "Leather Armor", "Chain Mail Armor", "Plate Mail", "Mage Robe",
    "Worn-out Boots", "Hide Armor", "Small Shield", "Medium Shield", "Large Shield",
}
EQUIP_TYPES_FOR_INTERNAL = {
    "armor", "shield", "helmet", "bracers", "boots", "belt",
    "cloak", "robe", "ring", "amulet",
}


def detect_internal_items(items):
    """Return set of resrefs that look like creature/internal equipment.

    Detects items that have ALL of: generic name, no description, not-droppable
    flag set or "no animation" marker. Reads the .itm binary directly to get
    flags. Falls back gracefully if binary isn't accessible.
    """
    internal = set()
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from populate_item_metadata import read_key, BifReader
        bif_names, itm_res = read_key()
        bif = BifReader(bif_names)
    except Exception as e:
        print(f"  WARNING: cannot read .itm files for internal detection: {e}")
        return internal

    import re as _re
    # Matches bare "Attack", "Attack +3", or "<Creature> Attack" (e.g. "Shadow
    # Elemental Attack"). All are monster-inventory strike items, never player-usable.
    _ATTACK_NAME_RX = _re.compile(r'^\s*(?:[\w\' -]+\s+)?Attack\s*(\+\d+)?\s*$', _re.I)
    for ref, it in items.items():
        if _ATTACK_NAME_RX.match(it.get("n", "") or ""):
            internal.add(ref)
            continue
        # Impossible-stat detection runs for ALL item types (weapons/arrows/etc.
        # are otherwise excluded from the equipment-focused logic below, but
        # debug/creature weapons with cheat stats should still be hidden).
        stats = it.get("stats") or {}
        thac0 = stats.get("thac0") or 0
        dmg_bonus = stats.get("dmgBonus") or 0
        price = it.get("price") or 0
        desc = it.get("desc") or ""
        has_real_description = len(desc) > 50
        # 1. Outright-impossible damage (>50): KILLSW01/OHBWING2 debug weapons.
        #    No legitimate item has this, escape hatches don't apply.
        if abs(dmg_bonus) > 50:
            internal.add(ref); continue
        # 2. Billion-coin pricing: GODBOW and similar deity/debug items.
        if price > 1_000_000:
            internal.add(ref); continue
        # 3. High-but-not-absurd damage (>10): flag unless it has a real
        #    description (which indicates extraction bug on a real item).
        if abs(dmg_bonus) > 10 and not has_real_description:
            internal.add(ref); continue
        # 4. Suspicious thac0 (>20, includes the 32767 sentinel): creature data
        #    unless it looks like a real player item (real desc + plausible price).
        if abs(thac0) > 20 and not (has_real_description and 0 < price < 100_000):
            internal.add(ref); continue
        n = it.get("n", "")
        # Dialogue-name check runs for ALL item types (scrolls, potions, etc. can
        # also inherit misrouted strrefs). Real item names never contain sentence
        # punctuation; any of `?`, `!`, mid-sentence `. `, or trailing `.` beyond
        # 15 chars is unambiguously a misrouted dialogue line.
        stripped = n.strip()
        is_strong_dialogue = (
            "?" in stripped
            or "!" in stripped
            or ". " in stripped
            or (stripped.endswith(".") and len(stripped) > 15)
        )
        if is_strong_dialogue:
            internal.add(ref)
            continue
        # Empty-shell rule (creature / engine data records):
        # an item with NO description is rarely a real player-facing item. Most
        # vanilla items ship full descriptions; items lacking one are usually
        # creature-attack inventory markers (Skull, Broken Shield, Ghoul hand,
        # Dragon Claw), debug/easter-egg entries (MDK2 "Big Gun"), or broken
        # extractions of quest resources. Neither `dmg` nor `usability` count
        # as evidence of a real item (monster natural weapons have both); only
        # an AC attribution (armor data) is strong enough to gate this off.
        # A substantial price (>=100) is also allowed through as real data.
        has_real_attribution = stats.get("ac") is not None or price >= 100
        if (
            not desc.strip()
            and stripped
            and len(stripped) <= 30
            and not has_real_attribution
        ):
            internal.add(ref)
            continue
        if it.get("type") not in EQUIP_TYPES_FOR_INTERNAL:
            continue
        # Equipment-only rules beyond this point:
        #   1. Explicit "undroppable" / "no anim" in name
        #   2. Generic name (just "Ring", "Helmet", etc.) with no description
        #   3. Long names (>40 chars) — weaker signal, requires not_droppable
        is_explicit = "undroppable" in n.lower() or "no anim" in n.lower()
        is_generic_empty = (n in GENERIC_NAMES) and not it.get("desc", "").strip()
        is_weak_dialogue = len(stripped) > 40
        is_dialogue_name = is_weak_dialogue
        if not (is_explicit or is_generic_empty or is_dialogue_name):
            continue
        if ref not in itm_res:
            continue
        d = bif.read(*itm_res[ref])
        if not d or len(d) < 0x60:
            continue
        flags = struct.unpack("<I", d[0x18:0x1C])[0]
        not_droppable = not (flags & 0x4)
        anim = d[0x22:0x24]
        no_anim = anim == b"  "
        # Weak dialogue-name items: require not-droppable specifically (no_anim alone
        # is too loose — real bracers/rings/amulets often have no body animation).
        if is_weak_dialogue and not not_droppable:
            continue
        # Don't flag items that have multiple "real game item" signals — these are
        # genuine player items even if their flag bits look weird.
        signals = sum([
            bool(it.get("price", 0) > 50),
            bool(it.get("stats")),
            bool(it.get("usability")),
            bool(it.get("desc", "").strip()) and not is_dialogue_name,
        ])
        if signals >= 2 and not is_explicit:
            continue
        if not_droppable or no_anim or is_explicit:
            internal.add(ref)
    return internal

# resref -> partial dict of fields to merge into the item
OVERRIDES = {
    # VISCLCK1-5: BG2EE Mage Robes — binary has no usability bits set, but
    # these are clearly mage-class restricted by name and description.
    "VISCLCK1": {
        "type": "robe",
        "usability": {"classes": ["Bard", "Mage", "Sorcerer"]},
    },
    "VISCLCK2": {
        "type": "robe",
        "usability": {"classes": ["Bard", "Mage", "Sorcerer"]},
    },
    "VISCLCK3": {
        "type": "robe",
        "usability": {"classes": ["Bard", "Mage", "Sorcerer"]},
    },
    "VISCLCK4": {
        "type": "robe",
        "usability": {"classes": ["Bard", "Mage", "Sorcerer"]},
    },
    "VISCLCK5": {
        "type": "robe",
        "usability": {"classes": ["Bard", "Mage", "Sorcerer"]},
    },
    # Hexxat's Amulet (OHHEXAM0-5, 9): companion-locked plot item that swaps
    # resref at quest stages. Player can never equip it — no stats, no special.
    "OHHEXAM0": {"internal": True},
    "OHHEXAM1": {"internal": True},
    "OHHEXAM2": {"internal": True},
    "OHHEXAM3": {"internal": True},
    "OHHEXAM4": {"internal": True},
    "OHHEXAM5": {"internal": True},
    "OHHEXAM9": {"internal": True},
}


def main():
    write_mode = "--write" in sys.argv

    with open(ITEMS, "r", encoding="utf-8") as f:
        items = json.load(f)

    # Detect and flag internal/creature equipment automatically
    print(f"Detecting internal/creature equipment items...")
    internal = detect_internal_items(items)
    flagged = unflagged = 0
    # Tag detected items
    for ref in internal:
        if items[ref].get("internal") is not True:
            items[ref]["internal"] = True
            flagged += 1
    # Remove flag from items no longer matching (in case overrides change)
    # BUT keep items that are explicitly flagged via OVERRIDES.
    override_internal = {ref for ref, patch in OVERRIDES.items() if patch.get("internal") is True}
    for ref, it in items.items():
        if it.get("internal") is True and ref not in internal and ref not in override_internal:
            del it["internal"]
            unflagged += 1
    print(f"  Flagged {flagged} items as internal (was {len(internal)-flagged} already flagged)")
    if unflagged:
        print(f"  Removed flag from {unflagged} items")

    # Apply manual overrides AFTER detection cleanup so they stick.
    applied = 0
    for ref, patch in OVERRIDES.items():
        if ref not in items:
            print(f"  WARNING: {ref} not in items-vanilla.json")
            continue
        item = items[ref]
        changed = False
        for k, v in patch.items():
            if item.get(k) != v:
                item[k] = v
                changed = True
        if changed:
            applied += 1
            print(f"  Patched {ref}: {item.get('n')}")

    print(f"\nApplied {applied} explicit overrides")

    total_changes = applied + flagged + unflagged
    if write_mode and total_changes > 0:
        sorted_items = dict(sorted(items.items()))
        with open(ITEMS, "w", encoding="utf-8") as f:
            json.dump(sorted_items, f, indent=2, ensure_ascii=False)
        print(f"\nWrote {ITEMS}")
    elif total_changes > 0:
        print("\nDry run. Use --write to apply.")
    else:
        print("\nNo changes (idempotent).")


if __name__ == "__main__":
    main()
