#!/usr/bin/env python3
"""
populate_item_stats.py — Extract stats from vanilla ITM binary and add to items-vanilla.json.

Reads equipping feature blocks + extended headers from each .itm to populate:
  ac, thac0, dmg, dmgBonus, saves, stat bonuses, resistances, speed, apr, special

Usage:
    python scripts/populate_item_stats.py [--write]
"""

import struct, json, os, sys

BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE, "chitin.key")
TLK_PATH = os.path.join(BG2EE, "lang", "en_US", "dialog.tlk")
PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ITEMS_JSON = os.path.join(PROJ, "data", "items-vanilla.json")

RES_TYPE_ITM = 0x03ED

# Opcode → stat key mapping for equipping effects (timing=2 "while equipped")
OPCODE_MAP = {
    0: "ac",           # AC bonus
    1: "apr",          # Modify attacks per round
    6: "cha",
    10: "con",
    15: "dex",
    19: "int",
    44: "str",
    49: "wis",
    28: "coldResist",
    30: "fireResist",
    33: "saveDeath",
    34: "saveWand",
    35: "savePoly",
    36: "saveBreath",
    37: "saveSpell",
    166: "magicResist",
}

# Armor types that report base AC (not a bonus)
ARMOR_TYPES = {2}  # item_type 2 = armor
# Types that report AC as a bonus
AC_BONUS_TYPES = {12, 6, 10, 32, 7}  # shield, bracers, ring, cloak, helmet

# Meaningful equipping effect opcodes for "special" text
# Skips visual-only opcodes (142 display icon, 7 set color, 169 icon immunity, etc.)
SPECIAL_OPCODES = {
    20: "Haste",
    40: "Slow",
    45: "Free Action",
    74: "Regeneration",
    98: "Invisibility",
    219: "Immunity to Backstab",
}

# Opcodes to check with parameter context
def resolve_special_opcode(opcode, param1, param2):
    """Return a human-readable special ability string, or None to skip."""
    if opcode == 126:  # Movement rate modifier
        if param1 > 0:
            return "Increased Movement"
    if opcode == 16:
        if param1 != 0:
            return f"Luck {'+' if param1 > 0 else ''}{param1}"
    if opcode == 60 and param1 > 0:
        return f"Miscast Magic {param1}%"
    if opcode == 74:  # Regeneration
        if param2 == 0 and param1 > 0:
            return f"Regenerate {param1} HP/round"
        elif param2 == 1 and param1 > 0:
            return f"Regenerate {param1} HP/second"
    if opcode == 12:  # Damage bonus (elemental)
        dmg_types = {1: "Fire", 2: "Cold", 4: "Electricity", 8: "Acid", 16: "Magic",
                     32: "Poison", 64: "Slashing", 128: "Crushing", 512: "Missile"}
        dtype = dmg_types.get(param2 & 0xFFFF, "")
        if dtype and param1 > 0:
            return f"+{param1} {dtype} Damage"
    if opcode == 98:
        return "Invisibility"
    if opcode == 20:
        return "Haste"
    if opcode == 40:
        return "Slow"
    if opcode == 45:
        return "Free Action"
    if opcode == 219:
        return "Immunity to Backstab"
    if opcode == 1:  # APR — already handled as numeric stat
        return None
    return None


def read_key():
    """Read chitin.key, return (bif_names, itm_resources)."""
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


def extract_stats(itm_data):
    """Extract stats from an ITM binary. Returns a dict of non-zero stats."""
    if not itm_data or len(itm_data) < 0x72:
        return None
    if itm_data[0:4] != b"ITM ":
        return None

    item_type = struct.unpack("<H", itm_data[0x1C:0x1E])[0]
    enchantment = struct.unpack("<I", itm_data[0x60:0x64])[0]

    ext_hdr_offset = struct.unpack("<I", itm_data[0x64:0x68])[0]
    ext_hdr_count = struct.unpack("<H", itm_data[0x68:0x6A])[0]
    feat_offset = struct.unpack("<I", itm_data[0x6A:0x6E])[0]
    equip_feat_idx = struct.unpack("<H", itm_data[0x6E:0x70])[0]
    equip_feat_count = struct.unpack("<H", itm_data[0x70:0x72])[0]

    stats = {}

    # ── Extended header (first ability): weapon damage, THAC0, speed ──
    if ext_hdr_count > 0 and ext_hdr_offset + 56 <= len(itm_data):
        eh = itm_data[ext_hdr_offset:ext_hdr_offset + 56]
        attack_type = eh[0]  # 1=melee, 2=ranged, 3=magical, 4=launcher

        if attack_type in (1, 2, 3, 4):
            speed = eh[0x12]
            thac0 = struct.unpack("<h", eh[0x14:0x16])[0]
            dice_sides = eh[0x16]
            dice_thrown = eh[0x18]
            dmg_bonus = struct.unpack("<h", eh[0x1A:0x1C])[0]

            if speed:
                stats["speed"] = speed
            if thac0:
                stats["thac0"] = thac0
            if dice_thrown and dice_sides:
                stats["dmg"] = f"{dice_thrown}d{dice_sides}"
            if dmg_bonus:
                stats["dmgBonus"] = dmg_bonus

    # ── Equipping feature blocks: AC, saves, stats, resistances, APR ──
    specials = []
    for i in range(equip_feat_count):
        fb_off = feat_offset + (equip_feat_idx + i) * 48
        if fb_off + 48 > len(itm_data):
            break
        fb = itm_data[fb_off:fb_off + 48]
        opcode = struct.unpack("<H", fb[0:2])[0]
        target = fb[2]
        param1 = struct.unpack("<i", fb[4:8])[0]  # signed
        param2 = struct.unpack("<I", fb[8:12])[0]
        timing = fb[12]

        # Only care about "while equipped" effects (timing=2) targeting self (target=1)
        # Some items use timing=0 with duration=0 which is also permanent
        if timing not in (0, 2):
            continue
        if target not in (0, 1):
            continue

        if opcode in OPCODE_MAP:
            key = OPCODE_MAP[opcode]

            if opcode == 0:  # AC
                # param2 bits determine AC type:
                # 0=overall, 1=crushing, 2=missile, 4=piercing, 8=slashing, 16=set base AC
                ac_type = param2 & 0xFFFF
                if ac_type == 16:
                    # Set base AC — used by armor items
                    stats["ac"] = param1
                elif ac_type == 0:
                    # Overall AC modifier — used by shields, rings, cloaks
                    if param1 != 0 and "ac" not in stats:
                        stats["ac"] = abs(param1)
            elif opcode == 1:  # APR
                # param1 is the number of extra attacks (1 = 0.5 APR, 2 = 1 APR)
                # param2: 0=increment, 1=set, 2=percent
                if param2 == 0 and param1 != 0:
                    stats["apr"] = param1 * 0.5 if param1 <= 2 else param1
            elif opcode in (33, 34, 35, 36, 37):  # Saves
                if param1 != 0:
                    stats[key] = param1
            elif opcode in (6, 10, 15, 19, 44, 49):  # Ability scores
                if param1 != 0:
                    stats[key] = param1
            elif opcode in (28, 30, 166):  # Resistances
                if param1 != 0:
                    stats[key] = param1
        # Check for meaningful special abilities
        sp = resolve_special_opcode(opcode, param1, param2)
        if sp:
            specials.append(sp)

    # ── On-hit effects from first extended header (bonus elemental damage, etc.) ──
    if ext_hdr_count > 0 and ext_hdr_offset + 56 <= len(itm_data):
        eh = itm_data[ext_hdr_offset:ext_hdr_offset + 56]
        eh_feat_count = struct.unpack("<H", eh[0x1E:0x20])[0]
        eh_feat_idx = struct.unpack("<H", eh[0x20:0x22])[0]
        for i in range(eh_feat_count):
            fb_off = feat_offset + (eh_feat_idx + i) * 48
            if fb_off + 48 > len(itm_data):
                break
            fb = itm_data[fb_off:fb_off + 48]
            opcode = struct.unpack("<H", fb[0:2])[0]
            param1 = struct.unpack("<i", fb[4:8])[0]
            param2 = struct.unpack("<I", fb[8:12])[0]
            sp = resolve_special_opcode(opcode, param1, param2)
            if sp:
                specials.append(sp)

    # Collapse individual saves into "saves" if all 5 are the same
    save_keys = ["saveDeath", "saveWand", "savePoly", "saveBreath", "saveSpell"]
    save_vals = [stats.get(k, 0) for k in save_keys]
    if all(v == save_vals[0] and v != 0 for v in save_vals):
        stats["saves"] = save_vals[0]
        for k in save_keys:
            del stats[k]

    # Build special text
    unique_specials = list(dict.fromkeys(specials))  # dedupe preserving order
    if unique_specials:
        stats["special"] = ", ".join(unique_specials[:3])  # cap at 3

    # Clean: remove zero/empty values, but keep ac=0 (valid for AC 0 armor)
    stats = {k: v for k, v in stats.items() if v is not None and v != "" and (v != 0 or k == "ac")}

    return stats if stats else None


def main():
    write_mode = "--write" in sys.argv

    print("Reading chitin.key...")
    bif_names, itm_res = read_key()
    print(f"  {len(itm_res)} ITM resources")

    bif = BifReader(bif_names)

    with open(ITEMS_JSON, "r", encoding="utf-8") as f:
        items = json.load(f)
    print(f"  {len(items)} items in items-vanilla.json")

    updated = 0
    no_stats = 0
    errors = 0

    for ref, item in items.items():
        if ref not in itm_res:
            continue
        bi, fi = itm_res[ref]
        itm_data = bif.read(bi, fi)
        if not itm_data:
            errors += 1
            continue

        stats = extract_stats(itm_data)
        if stats:
            item["stats"] = stats
            updated += 1
        else:
            no_stats += 1

    print(f"\nResults:")
    print(f"  Items with stats: {updated}")
    print(f"  Items with no stats: {no_stats}")
    print(f"  Errors: {errors}")

    # Sample output
    samples = ["PLAT05", "SW1H01", "RING06", "BOOT01", "CLCK01", "HAMM06", "BOW01", "SHLD06", "BRAC14"]
    print(f"\nSamples:")
    for ref in samples:
        if ref in items and "stats" in items[ref]:
            print(f"  {ref} ({items[ref]['n']}): {json.dumps(items[ref]['stats'])}")

    if write_mode:
        sorted_items = dict(sorted(items.items()))
        with open(ITEMS_JSON, "w", encoding="utf-8") as f:
            json.dump(sorted_items, f, indent=2, ensure_ascii=False)
        print(f"\nWrote {ITEMS_JSON}")
    else:
        print(f"\nDry run. Use --write to update.")


if __name__ == "__main__":
    main()
