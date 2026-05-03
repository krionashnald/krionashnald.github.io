#!/usr/bin/env python3
"""
populate_item_specials.py — Build structured special arrays for items.

Reads equipping effects and item abilities from ITM binaries to create:
  "special": [
    {"type": "immunity", "target": "charm"},
    {"type": "resistance", "target": "fire", "value": 50},
    {"type": "regen", "value": 1, "desc": "Regenerate 1 HP/round"},
    {"type": "ability", "desc": "Cast Dire Charm 3/day"}
  ]

Usage:
    python scripts/populate_item_specials.py [--write]
"""

import struct, json, os, sys

BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE, "chitin.key")
TLK_PATH = os.path.join(BG2EE, "lang", "en_US", "dialog.tlk")
PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ITEMS_JSON = os.path.join(PROJ, "data", "items-vanilla.json")

RES_TYPE_ITM = 0x03ED

# Immunity opcodes: opcode 101 param2 values → creature types
CREATURE_TYPES = {
    2: "demonic", 3: "lycanthrope", 4: "undead", 5: "giant",
    6: "golem", 25: "undead",
}

# Opcode 100 (Protection from opcode): param1 → what it protects from
OPCODE_IMMUNITIES = {
    5: "charm", 24: "fear", 39: "stun", 45: "death",
    74: "disease", 78: "poison", 109: "paralysis",
    128: "confusion", 157: "petrification", 175: "hold",
    216: "level drain", 25: "sleep",
}

# Opcode 267 immunity strings (param2 values for specific immunity types)
# param2=25 → immunity to certain effects (varies by param1 strref)
# This is complex; we'll handle via known param1 strref patterns

# Resistances beyond fire/cold/magic
RESISTANCE_OPCODES = {
    27: "acid",
    28: "cold",
    29: "electricity",
    30: "fire",
    31: "electricity",
    33: None,  # save vs death - handled elsewhere
    86: "slashing",
    87: "crushing",
    88: "piercing",
    89: "physical",
    166: "magic",
}

# Spell school names for op 296
SPELL_SCHOOLS = {
    1: "Abjuration", 2: "Conjuration", 3: "Divination",
    4: "Enchantment", 5: "Illusion", 6: "Evocation",
    7: "Necromancy", 8: "Alteration",
}


class TlkReader:
    def __init__(self, path):
        self.f = open(path, "rb")
        self.f.read(10)
        self.count = struct.unpack("<I", self.f.read(4))[0]
        self.str_offset = struct.unpack("<I", self.f.read(4))[0]

    def get(self, strref):
        if strref < 0 or strref >= self.count or strref == 0xFFFFFFFF:
            return ""
        self.f.seek(18 + strref * 26)
        flags = struct.unpack("<H", self.f.read(2))[0]
        self.f.read(16)
        str_off = struct.unpack("<I", self.f.read(4))[0]
        str_len = struct.unpack("<I", self.f.read(4))[0]
        if not (flags & 1) or str_len == 0:
            return ""
        self.f.seek(self.str_offset + str_off)
        return self.f.read(str_len).decode("utf-8", errors="replace").rstrip("\x00")

    def close(self):
        self.f.close()


def extract_specials(itm_data, tlk):
    """Extract structured special abilities from an ITM binary."""
    if not itm_data or len(itm_data) < 0x72 or itm_data[0:4] != b"ITM ":
        return None

    ext_hdr_offset = struct.unpack("<I", itm_data[0x64:0x68])[0]
    ext_hdr_count = struct.unpack("<H", itm_data[0x68:0x6A])[0]
    feat_offset = struct.unpack("<I", itm_data[0x6A:0x6E])[0]
    equip_feat_idx = struct.unpack("<H", itm_data[0x6E:0x70])[0]
    equip_feat_count = struct.unpack("<H", itm_data[0x70:0x72])[0]

    specials = []
    seen = set()  # dedup key

    def add(entry):
        key = json.dumps(entry, sort_keys=True)
        if key not in seen:
            seen.add(key)
            specials.append(entry)

    # ── Equipping effects ──
    for i in range(equip_feat_count):
        fb_off = feat_offset + (equip_feat_idx + i) * 48
        if fb_off + 48 > len(itm_data):
            break
        fb = itm_data[fb_off:fb_off + 48]
        opcode = struct.unpack("<H", fb[0:2])[0]
        target = fb[2]
        param1 = struct.unpack("<i", fb[4:8])[0]
        param2 = struct.unpack("<I", fb[8:12])[0]
        timing = fb[12]

        if timing not in (0, 2) or target not in (0, 1):
            continue

        # Immunity to creature type
        if opcode == 101:
            ct = CREATURE_TYPES.get(param2)
            if ct:
                add({"type": "immunity", "target": ct})

        # Protection from opcode (immunity)
        elif opcode == 100:
            imm = OPCODE_IMMUNITIES.get(param1)
            if imm:
                add({"type": "immunity", "target": imm})

        # Immunity to specific state via opcode 267
        elif opcode == 267:
            # param2 tells the context: 5=spell school, 25=specific immunity
            if param2 == 25:
                # strref-based immunity — check what the string says
                desc = tlk.get(param1).lower() if tlk else ""
                if "charm" in desc:
                    add({"type": "immunity", "target": "charm"})
                elif "fear" in desc or "horror" in desc or "panic" in desc:
                    add({"type": "immunity", "target": "fear"})
                elif "hold" in desc:
                    add({"type": "immunity", "target": "hold"})
                elif "stun" in desc:
                    add({"type": "immunity", "target": "stun"})
                elif "sleep" in desc:
                    add({"type": "immunity", "target": "sleep"})
                elif "confusion" in desc:
                    add({"type": "immunity", "target": "confusion"})
                elif "silence" in desc:
                    add({"type": "immunity", "target": "silence"})
                elif "level drain" in desc:
                    add({"type": "immunity", "target": "level drain"})
                elif "poison" in desc:
                    add({"type": "immunity", "target": "poison"})
                elif "disease" in desc:
                    add({"type": "immunity", "target": "disease"})
                elif "petrif" in desc:
                    add({"type": "immunity", "target": "petrification"})

        # Poison immunity via opcode 173
        elif opcode == 173:
            if param1 >= 100:
                add({"type": "immunity", "target": "poison"})

        # Regeneration
        elif opcode == 74:
            if param1 > 0:
                if param2 == 0:
                    add({"type": "regen", "value": param1, "desc": f"Regenerate {param1} HP/round"})
                elif param2 == 1:
                    add({"type": "regen", "value": param1, "desc": f"Regenerate {param1} HP/sec"})
                elif param2 == 3:
                    add({"type": "regen", "value": param1, "desc": f"Regenerate 1 HP/{param1}s"})

        # Free Action
        elif opcode == 45:
            add({"type": "freeAction", "desc": "Free Action"})

        # Haste
        elif opcode == 20:
            add({"type": "other", "desc": "Haste"})

        # Invisibility
        elif opcode == 98:
            add({"type": "other", "desc": "Invisibility"})

        # Immunity to backstab
        elif opcode == 219:
            add({"type": "immunity", "target": "backstab"})

        # Movement rate bonus
        elif opcode == 126:
            if param1 > 0:
                add({"type": "other", "desc": "Increased Movement Rate"})

        # Protection from spell school
        elif opcode == 296:
            school = SPELL_SCHOOLS.get(param2 & 0xFF, "")
            if school:
                add({"type": "immunity", "target": f"{school} spells"})

        # Resistances (not already in numeric stats)
        elif opcode in (27, 29, 31, 86, 87, 88, 89):
            rtype = RESISTANCE_OPCODES.get(opcode)
            if rtype and param1 != 0:
                add({"type": "resistance", "target": rtype, "value": param1})

        # Extra spell slots
        elif opcode == 42:  # Bonus wizard spells
            if param1 > 0:
                add({"type": "extraSpellSlot", "level": param2 + 1, "spellType": "wizard"})

        elif opcode == 62:  # Bonus priest spells
            if param1 > 0:
                add({"type": "extraSpellSlot", "level": param2 + 1, "spellType": "priest"})

        # Max HP bonus
        elif opcode == 18:
            if param1 > 0:
                add({"type": "other", "desc": f"+{param1} Max HP"})

    # ── Item abilities (castable charges) ──
    for ei in range(ext_hdr_count):
        eh_off = ext_hdr_offset + ei * 56
        if eh_off + 56 > len(itm_data):
            break
        eh = itm_data[eh_off:eh_off + 56]
        location = eh[2]  # 3 = item ability
        if location != 3:
            continue
        charges = struct.unpack("<H", eh[0x22:0x24])[0]
        # The ability's name would need tooltip.2da lookup — use a generic description
        # Read the number of on-hit effects to get a sense of what it does
        eh_feat_count = struct.unpack("<H", eh[0x1E:0x20])[0]
        eh_feat_idx = struct.unpack("<H", eh[0x20:0x22])[0]

        ability_effects = []
        for i in range(min(eh_feat_count, 10)):
            fb_off = feat_offset + (eh_feat_idx + i) * 48
            if fb_off + 48 > len(itm_data):
                break
            fb = itm_data[fb_off:fb_off + 48]
            op = struct.unpack("<H", fb[0:2])[0]
            p1 = struct.unpack("<i", fb[4:8])[0]
            p2 = struct.unpack("<I", fb[8:12])[0]
            ability_names = {
                12: "Damage", 17: "Heal", 20: "Haste", 24: "Horror",
                25: "Poison", 40: "Slow", 45: "Free Action",
                58: "Dispel Magic", 74: "Cure Disease", 98: "Invisibility",
                109: "Paralyze", 134: "Petrify",
                153: "Fireball", 174: "Summon", 180: "Stoneskin",
                206: "Spell Immunity", 215: "Restoration",
            }
            # Op 141 = Visual animation, but param2 tells the real effect
            if op == 141:
                anim_effects = {4: "Improved Haste", 8: "Protection from Evil",
                                9: "Protection from Normal Missiles", 14: "Globe of Invulnerability"}
                name = anim_effects.get(p2)
                if name:
                    ability_effects.append(name)
            elif op == 146:  # Cast spell
                res = fb[14:22].rstrip(b"\x00").decode("ascii", errors="replace").upper()
                # We can't resolve the spell name without another lookup, use generic
                ability_effects.append("Cast Spell")
            elif op in ability_names:
                ability_effects.append(ability_names[op])

        if ability_effects:
            primary = ability_effects[0]
            charges_text = f" {charges}/day" if charges > 0 else ""
            add({"type": "ability", "desc": f"{primary}{charges_text}"})

    return specials if specials else None


def main():
    write_mode = "--write" in sys.argv

    print("Reading chitin.key...")
    sys.path.insert(0, os.path.dirname(__file__))
    from populate_item_stats import read_key, BifReader
    bif_names, itm_res = read_key()
    bif = BifReader(bif_names)

    print("Loading dialog.tlk...")
    tlk = TlkReader(TLK_PATH)

    with open(ITEMS_JSON, "r", encoding="utf-8") as f:
        items = json.load(f)

    updated = 0
    for ref, item in items.items():
        if ref not in itm_res:
            continue
        bi, fi = itm_res[ref]
        itm_data = bif.read(bi, fi)
        if not itm_data:
            continue

        specials = extract_specials(itm_data, tlk)
        if specials:
            # Replace old string "special" with new array
            if "stats" in item and "special" in item["stats"]:
                del item["stats"]["special"]
            item["special"] = specials
            updated += 1
        else:
            # Remove old special string if it exists
            if "stats" in item and "special" in item["stats"]:
                del item["stats"]["special"]

    tlk.close()

    # Clean empty stats
    for item in items.values():
        if "stats" in item and not item["stats"]:
            del item["stats"]

    print(f"\nResults:")
    print(f"  Items with specials: {updated}")

    # Samples
    samples = ["RING39", "STAF11", "BOOT01", "SW2H10", "HELM07", "SW1H34", "BELT10", "CLCK01", "BRAC16"]
    print(f"\nSamples:")
    for ref in samples:
        it = items.get(ref, {})
        sp = it.get("special", [])
        if sp:
            print(f"  {ref} ({it.get('n', '?')}):")
            for s in sp:
                print(f"    {json.dumps(s)}")

    if write_mode:
        sorted_items = dict(sorted(items.items()))
        with open(ITEMS_JSON, "w", encoding="utf-8") as f:
            json.dump(sorted_items, f, indent=2, ensure_ascii=False)
        print(f"\nWrote {ITEMS_JSON}")
    else:
        print(f"\nDry run. Use --write to update.")


if __name__ == "__main__":
    main()
