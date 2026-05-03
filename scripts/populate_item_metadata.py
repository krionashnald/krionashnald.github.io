#!/usr/bin/env python3
"""
populate_item_metadata.py — Add twoHanded, profType, usability, and charges to items.

Reads ITM binary fields:
- twoHanded: flags dword (0x18) bit 1
- profType: weapon proficiency byte (0x31) → name from WEAPPROF.2DA
- usability: 4-byte bitmask at 0x1E + 4 kit usability bytes + min stat requirements
- charges: extended header item abilities (location=3) charges field (0x22)

Usage:
    python scripts/populate_item_metadata.py [--write]
"""

import struct, json, os, sys

BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE, "chitin.key")
PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ITEMS_JSON = os.path.join(PROJ, "data", "items-vanilla.json")

RES_TYPE_ITM = 0x03ED

# ── Proficiency type IDs (from WEAPPROF.2DA) ────────────────────────────────
PROF_TYPES = {
    89: "bastard sword", 90: "long sword", 91: "short sword",
    92: "axe", 93: "two-handed sword", 94: "katana",
    95: "scimitar/wakizashi/ninjato", 96: "dagger", 97: "war hammer",
    98: "spear", 99: "halberd", 100: "flail/morning star",
    101: "mace", 102: "quarterstaff", 103: "crossbow",
    104: "long bow", 105: "short bow", 106: "dart",
    107: "sling", 115: "club",
}

# ── Header Usability bitmask (4 bytes = 32 bits) ────────────────────────────
# Each bit set = that group CANNOT use the item (exclusion)
# Byte 1 (0x1E): Alignments
USABILITY_ALIGNMENT = {
    0: "chaotic_evil", 1: "chaotic_neutral", 2: "chaotic_good",
    3: "lawful_evil", 4: "lawful_good", 5: "lawful_neutral",
    6: "neutral_evil", 7: "neutral_good",
    # Bit positions per IESDP: actually grouped weirdly
    # Bit 0=Chaotic..., 1=...Evil, 2=...Good, 3=...Neutral, 4=Lawful..., 5=Neutral...
    # And aligned are inferred from combinations
}
# Simpler: I'll just mark which alignments are RESTRICTED
# Byte 2 (0x1F): Multi-class
USABILITY_BYTE2 = {
    0: "Cleric/Mage", 1: "Cleric/Thief", 2: "Cleric/Ranger", 3: "Fighter",
    4: "Fighter/Druid", 5: "Fighter/Mage", 6: "Bard", 7: "Cleric",
}
# Byte 3 (0x20): Single-class & multi-class
USABILITY_BYTE3 = {
    0: "Fighter/Mage/Thief", 1: "Fighter/Thief", 2: "Mage/Sorcerer",
    3: "Mage/Thief", 4: "Paladin", 5: "Ranger", 6: "Thief", 7: "Elf",
}
# Byte 4 (0x21): Races
USABILITY_BYTE4 = {
    0: "Dwarf", 1: "Half-Elf", 2: "Halfling", 3: "Human",
    4: "Gnome", 5: "Monk", 6: "Druid", 7: "Half-Orc",
}

# Map class names from byte 2/3 to player-facing class set
ALL_CLASSES = {
    "Fighter", "Mage", "Sorcerer", "Cleric", "Ranger", "Paladin",
    "Thief", "Druid", "Bard", "Monk", "Barbarian", "Shaman",
}
ALL_RACES = {"Human", "Elf", "Half-Elf", "Dwarf", "Halfling", "Gnome", "Half-Orc"}


def parse_usability(usability_bytes, min_stats):
    """Parse usability bytes into a structured object. Returns None if no restrictions."""
    b1, b2, b3, b4 = usability_bytes

    # Collect restricted classes (bits SET = excluded)
    excluded_classes = set()
    excluded_races = set()
    excluded_alignments = set()

    # Byte 1: alignment axes (bits 0-5) + Bard (6) + Cleric (7)
    # IESDP table:
    #   bit 0: Chaotic...   bit 4: Lawful...
    #   bit 1: ...Evil      bit 5: Neutral...
    #   bit 2: ...Good      bit 6: Bard
    #   bit 3: ...Neutral   bit 7: Cleric
    # Alignment is excluded if BOTH its row bit AND column bit are set.
    if b1 & 0x40: excluded_classes.add("Bard")
    if b1 & 0x80: excluded_classes.add("Cleric")

    # Alignment matrix: row (bit 0=Chaotic, 4=Lawful, 5=Neutral) + column (1=Evil, 2=Good, 3=Neutral)
    rows = []
    if b1 & 0x01: rows.append("Chaotic")
    if b1 & 0x10: rows.append("Lawful")
    if b1 & 0x20: rows.append("Neutral")
    cols = []
    if b1 & 0x02: cols.append("Evil")
    if b1 & 0x04: cols.append("Good")
    if b1 & 0x08: cols.append("Neutral")
    for r in rows:
        for c in cols:
            excluded_alignments.add(f"{r} {c}")

    # Byte 2: single classes & multi-classes (only single classes matter for ALL_CLASSES)
    if b2 & 0x08: excluded_classes.add("Fighter")
    # Byte 3: single + multi
    if b3 & 0x04: excluded_classes.update(["Mage", "Sorcerer"])
    if b3 & 0x10: excluded_classes.add("Paladin")
    if b3 & 0x20: excluded_classes.add("Ranger")
    if b3 & 0x40: excluded_classes.add("Thief")
    if b3 & 0x80: excluded_races.add("Elf")
    # Byte 4: races + Druid/Monk/Shaman
    if b4 & 0x01: excluded_races.add("Dwarf")
    if b4 & 0x02: excluded_races.add("Half-Elf")
    if b4 & 0x04: excluded_races.add("Halfling")
    if b4 & 0x08: excluded_races.add("Human")
    if b4 & 0x10: excluded_races.add("Gnome")
    if b4 & 0x20: excluded_classes.add("Monk")
    if b4 & 0x40: excluded_classes.update(["Druid", "Shaman"])
    if b4 & 0x80: excluded_races.add("Half-Orc")

    # Compute allowed sets
    allowed_classes = ALL_CLASSES - excluded_classes
    allowed_races = ALL_RACES - excluded_races

    result = {}

    # Only emit "classes" if there are restrictions and not all classes allowed
    if excluded_classes and len(allowed_classes) < len(ALL_CLASSES):
        result["classes"] = sorted(allowed_classes)
    if excluded_races and len(allowed_races) < len(ALL_RACES):
        result["races"] = sorted(allowed_races)
    if excluded_alignments:
        result["excludedAlignments"] = sorted(excluded_alignments)

    # Min stat requirements
    if min_stats.get("str"):
        result["minStr"] = min_stats["str"]
    if min_stats.get("strBonus"):
        result["minStrBonus"] = min_stats["strBonus"]
    if min_stats.get("dex"):
        result["minDex"] = min_stats["dex"]
    if min_stats.get("con"):
        result["minCon"] = min_stats["con"]
    if min_stats.get("int"):
        result["minInt"] = min_stats["int"]
    if min_stats.get("wis"):
        result["minWis"] = min_stats["wis"]
    if min_stats.get("cha"):
        result["minCha"] = min_stats["cha"]
    if min_stats.get("level"):
        result["minLevel"] = min_stats["level"]

    return result if result else None


def extract_metadata(itm_data):
    """Extract twoHanded, profType, usability, charges from ITM binary."""
    if not itm_data or len(itm_data) < 0x72 or itm_data[0:4] != b"ITM ":
        return {}

    flags = struct.unpack("<I", itm_data[0x18:0x1C])[0]
    item_type = struct.unpack("<H", itm_data[0x1C:0x1E])[0]

    # Two-handed: flags bit 1
    two_handed = bool(flags & 0x02)

    # Usability bytes
    usability_bytes = (
        itm_data[0x1E], itm_data[0x1F], itm_data[0x20], itm_data[0x21],
    )

    # Min stats
    min_level = struct.unpack("<H", itm_data[0x24:0x26])[0]
    min_str = struct.unpack("<H", itm_data[0x26:0x28])[0]
    min_str_bonus = itm_data[0x28]
    min_int = itm_data[0x2A]
    min_dex = itm_data[0x2C]
    min_wis = itm_data[0x2E]
    min_con = itm_data[0x30]
    min_cha = struct.unpack("<H", itm_data[0x32:0x34])[0]

    min_stats = {}
    if min_level: min_stats["level"] = min_level
    if min_str: min_stats["str"] = min_str
    if min_str_bonus: min_stats["strBonus"] = min_str_bonus
    if min_int: min_stats["int"] = min_int
    if min_dex: min_stats["dex"] = min_dex
    if min_wis: min_stats["wis"] = min_wis
    if min_con: min_stats["con"] = min_con
    if min_cha: min_stats["cha"] = min_cha

    # Proficiency type (only meaningful for weapons)
    prof_byte = itm_data[0x31]
    prof_type = PROF_TYPES.get(prof_byte)

    # Fallback: infer profType from item_type when prof byte is 0
    # (some items like creature weapons / templates don't set the prof byte)
    if not prof_type:
        ITEM_TYPE_TO_PROF = {
            15: "long bow", 16: "dagger", 17: "mace", 18: "sling",
            19: "short sword", 20: "long sword", 21: "war hammer",
            22: "flail/morning star", 23: "flail/morning star",
            25: "axe", 26: "quarterstaff", 27: "crossbow",
            29: "spear", 30: "halberd", 24: "dart", 43: "club",
        }
        # For item type 20 (large sword), prefer "two-handed sword" if 2H
        if item_type == 20 and (flags & 0x02):
            prof_type = "two-handed sword"
        else:
            prof_type = ITEM_TYPE_TO_PROF.get(item_type)

    # Charges from extended headers (location=3 abilities)
    ext_hdr_offset = struct.unpack("<I", itm_data[0x64:0x68])[0]
    ext_hdr_count = struct.unpack("<H", itm_data[0x68:0x6A])[0]

    charges_total = 0
    recharge_type = None
    for ei in range(ext_hdr_count):
        eh_off = ext_hdr_offset + ei * 56
        if eh_off + 56 > len(itm_data):
            break
        eh = itm_data[eh_off:eh_off + 56]
        location = eh[2]
        if location != 3:  # Only item abilities
            continue
        ch = struct.unpack("<H", eh[0x22:0x24])[0]
        rch = struct.unpack("<H", eh[0x24:0x26])[0]
        if ch > 0:
            charges_total += ch
            recharge_type = rch

    # Build result
    result = {}

    # Two-handed only on weapons (item types: weapons, ranged)
    WEAPON_TYPES = {15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 29, 30, 28, 43}  # weapons + fist + club
    if item_type in WEAPON_TYPES and two_handed:
        result["twoHanded"] = True

    if prof_type:
        result["profType"] = prof_type

    usability = parse_usability(usability_bytes, min_stats)
    if usability:
        result["usability"] = usability

    if charges_total > 0:
        # Recharge type: 0=no recharge, 1=item vanishes, 2=replaced, 3=recharge after rest
        if recharge_type == 0:
            period = "permanent"  # Use until depleted (wands)
        elif recharge_type in (1, 2):
            period = "single use"  # Consumed
        else:
            period = "day"  # Default — recharges per rest
        result["charges"] = {"count": charges_total, "period": period}

    return result


def read_key():
    with open(KEY_PATH, "rb") as f:
        f.read(8)
        bif_count, res_count = struct.unpack("<II", f.read(8))
        bif_offset, res_offset = struct.unpack("<II", f.read(8))

        bif_names = []
        f.seek(bif_offset)
        raw = []
        for _ in range(bif_count):
            d = f.read(12)
            raw.append((struct.unpack("<I", d[4:8])[0], struct.unpack("<H", d[8:10])[0]))
        for no, nl in raw:
            f.seek(no)
            bif_names.append(f.read(nl).decode("ascii", errors="replace").rstrip("\x00").replace("\\", "/"))

        itm_res = {}
        f.seek(res_offset)
        for _ in range(res_count):
            d = f.read(14)
            name = d[0:8].rstrip(b"\x00").decode("ascii", errors="replace").upper()
            rt = struct.unpack("<H", d[8:10])[0]
            loc = struct.unpack("<I", d[10:14])[0]
            if rt == RES_TYPE_ITM:
                itm_res[name] = ((loc >> 20) & 0xFFF, loc & 0x3FFF)

    return bif_names, itm_res


class BifReader:
    def __init__(self, bif_names):
        self.bif_names = bif_names
        self._cache = {}

    def read(self, bif_idx, file_idx):
        if bif_idx not in self._cache:
            bif_path = os.path.join(BG2EE, self.bif_names[bif_idx].replace("/", os.sep))
            if not os.path.exists(bif_path):
                self._cache[bif_idx] = None
                return None
            with open(bif_path, "rb") as bf:
                d = bf.read()
            if d[:4] != b"BIFF":
                self._cache[bif_idx] = None
                return None
            fc = struct.unpack("<I", d[8:12])[0]
            feo = struct.unpack("<I", d[16:20])[0]
            idx = {}
            for i in range(fc):
                base = feo + i * 16
                loc = struct.unpack("<I", d[base:base+4])[0]
                off = struct.unpack("<I", d[base+4:base+8])[0]
                sz = struct.unpack("<I", d[base+8:base+12])[0]
                idx[loc & 0x3FFF] = (off, sz)
            self._cache[bif_idx] = (d, idx)

        entry = self._cache.get(bif_idx)
        if not entry:
            return None
        bif_data, idx = entry
        if file_idx not in idx:
            return None
        off, sz = idx[file_idx]
        return bif_data[off:off+sz]


def main():
    write_mode = "--write" in sys.argv

    print("Reading chitin.key...")
    bif_names, itm_res = read_key()
    bif = BifReader(bif_names)

    with open(ITEMS_JSON, "r", encoding="utf-8") as f:
        items = json.load(f)

    twoHanded_count = 0
    profType_count = 0
    usability_count = 0
    charges_count = 0
    updated = 0

    # Strip "ability X/day" entries from special arrays since charges replaces them
    cleaned_specials = 0

    for ref, item in items.items():
        if ref not in itm_res:
            continue
        bi, fi = itm_res[ref]
        itm_data = bif.read(bi, fi)
        if not itm_data:
            continue

        meta = extract_metadata(itm_data)
        if not meta:
            continue

        if meta.get("twoHanded"):
            item["twoHanded"] = True
            twoHanded_count += 1

        if "profType" in meta:
            item["profType"] = meta["profType"]
            profType_count += 1

        if "usability" in meta:
            item["usability"] = meta["usability"]
            usability_count += 1

        if "charges" in meta:
            item["charges"] = meta["charges"]
            charges_count += 1

            # Strip "ability X/day" entries from special since charges replaces them
            if "special" in item:
                new_special = [s for s in item["special"]
                               if not (s.get("type") == "ability" and "/day" in s.get("desc", ""))]
                if len(new_special) != len(item["special"]):
                    cleaned_specials += len(item["special"]) - len(new_special)
                    if new_special:
                        item["special"] = new_special
                    else:
                        del item["special"]

        updated += 1

    print(f"\nResults:")
    print(f"  Items updated: {updated}")
    print(f"  twoHanded: {twoHanded_count}")
    print(f"  profType: {profType_count}")
    print(f"  usability: {usability_count}")
    print(f"  charges: {charges_count}")
    print(f"  Stripped redundant ability/day specials: {cleaned_specials}")

    # Samples
    samples = ["SW2H10", "STAF11", "SW1H08", "SW1H01", "SW1H72", "RING39", "BRAC16",
               "WAND08", "BLUN30", "AROW01"]
    print(f"\nSamples:")
    for ref in samples:
        it = items.get(ref, {})
        print(f"  {ref} ({it.get('n','?')}):")
        for f in ("twoHanded", "profType", "usability", "charges"):
            if f in it:
                print(f"    {f}: {json.dumps(it[f])}")

    if write_mode:
        sorted_items = dict(sorted(items.items()))
        with open(ITEMS_JSON, "w", encoding="utf-8") as f:
            json.dump(sorted_items, f, indent=2, ensure_ascii=False)
        print(f"\nWrote {ITEMS_JSON}")
    else:
        print(f"\nDry run. Use --write to update.")


if __name__ == "__main__":
    main()
