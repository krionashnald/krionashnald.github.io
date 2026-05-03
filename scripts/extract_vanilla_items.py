#!/usr/bin/env python3
"""
Extract vanilla item data from BG2EE backup (chitin.key + BIF + dialog.tlk).
Produces data/items-vanilla.json matching the project's compact style.

Usage:
    python scripts/extract_vanilla_items.py [--write]
    Without --write, prints stats only. With --write, writes items-vanilla.json.
"""

import struct, json, os, sys, re

# ── Paths ────────────────────────────────────────────────────────────────────
BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE, "chitin.key")
TLK_PATH = os.path.join(BG2EE, "lang", "en_US", "dialog.tlk")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "items-vanilla.json")
OUT_PATH = os.path.normpath(OUT_PATH)

# ── Item category mapping (ITEMCAT.IDS from IESDP) ──────────────────────────
ITEM_CATEGORIES = {
    0: "misc",
    1: "amulet",
    2: "armor",
    3: "belt",
    4: "boots",
    5: "arrow",
    6: "bracers",
    7: "helmet",
    8: "key",
    9: "potion",
    10: "ring",
    11: "scroll",
    12: "shield",
    13: "food",
    14: "bullet",
    15: "bow",
    16: "dagger",
    17: "mace",
    18: "sling",
    19: "short sword",
    20: "large sword",
    21: "hammer",
    22: "morning star",
    23: "flail",
    24: "dart",
    25: "axe",
    26: "staff",
    27: "crossbow",
    28: "fist",
    29: "spear",
    30: "halberd",
    31: "bolt",
    32: "cloak",
    33: "coin",
    34: "gem",
    35: "wand",
    36: "container",
    37: "broken",  # BROKEN1
    38: "familiar",
    39: "tattoo",
    40: "lens",
    41: "buckler",
    42: "candle",
    43: "club",
    44: "large shield",
    45: "container",  # EE
    46: "note",
    47: "small shield",
    48: "medium shield",  # EE (repurposed)
    49: "small shield",  # EE
    50: "misc",   # EE
    51: "misc",   # EE
    52: "misc",   # EE
    53: "small shield",  # EE
    57: "wand",   # EE
    60: "leather armor",  # EE
    61: "studded leather",  # EE
    62: "chain mail",  # EE
    63: "splint mail",  # EE
    64: "plate mail",  # EE
    65: "full plate",  # EE
    66: "hide armor",  # EE
    67: "robe",   # EE
    68: "scale mail",  # EE
    69: "wand",   # EE
    72: "helmet",  # SoD/EE
}

# Resource type for ITM in KEY file
RES_TYPE_ITM = 0x03ED

# ── TLK reader ───────────────────────────────────────────────────────────────
class TlkReader:
    """Reads string references from a TLK v1 file."""

    def __init__(self, path):
        self.f = open(path, "rb")
        sig = self.f.read(4)
        ver = self.f.read(4)
        assert sig == b"TLK " and ver == b"V1  ", f"Bad TLK: {sig} {ver}"
        self.lang = struct.unpack("<H", self.f.read(2))[0]
        self.count = struct.unpack("<I", self.f.read(4))[0]
        self.str_offset = struct.unpack("<I", self.f.read(4))[0]
        # Entry section starts at byte 18 (0x12)
        self.entry_base = 18

    def get(self, strref):
        """Return string for a strref, or '' if invalid."""
        if strref < 0 or strref >= self.count or strref == 0xFFFFFFFF:
            return ""
        # Each entry is 26 bytes
        self.f.seek(self.entry_base + strref * 26)
        flags = struct.unpack("<H", self.f.read(2))[0]
        self.f.read(8)   # sound resref
        self.f.read(4)   # volume variance
        self.f.read(4)   # pitch variance
        str_off = struct.unpack("<I", self.f.read(4))[0]
        str_len = struct.unpack("<I", self.f.read(4))[0]
        if not (flags & 1) or str_len == 0:
            return ""
        self.f.seek(self.str_offset + str_off)
        raw = self.f.read(str_len)
        return raw.decode("utf-8", errors="replace").rstrip("\x00")

    def close(self):
        self.f.close()


# ── KEY reader ───────────────────────────────────────────────────────────────
def read_key(path):
    """Parse chitin.key, return (bif_entries, itm_resources)."""
    with open(path, "rb") as f:
        sig = f.read(4)
        ver = f.read(4)
        assert sig == b"KEY " and ver == b"V1  "
        bif_count, res_count = struct.unpack("<II", f.read(8))
        bif_offset, res_offset = struct.unpack("<II", f.read(8))

        # Read BIF entries
        bif_entries = []
        f.seek(bif_offset)
        for _ in range(bif_count):
            bif_len, name_off, name_len, loc_flags = struct.unpack("<IHHI", f.read(12))
            # Wait -- BIF entry is 12 bytes: 4+4+2+2
            # Actually: Length(4) + Offset to name(4) + Name length(2) + Location(2) = 12 bytes
            bif_entries.append((bif_len, name_off, name_len, loc_flags))

        # Re-read with correct struct (my struct was wrong)
        bif_entries = []
        f.seek(bif_offset)
        for _ in range(bif_count):
            data = f.read(12)
            bif_len = struct.unpack("<I", data[0:4])[0]
            name_off = struct.unpack("<I", data[4:8])[0]
            name_len = struct.unpack("<H", data[8:10])[0]
            loc_flags = struct.unpack("<H", data[10:12])[0]
            bif_entries.append((bif_len, name_off, name_len, loc_flags))

        # Read BIF filenames
        bif_names = []
        for _, name_off, name_len, _ in bif_entries:
            f.seek(name_off)
            raw = f.read(name_len)
            name = raw.decode("ascii", errors="replace").rstrip("\x00")
            # Normalize path separators
            name = name.replace("\\", "/")
            bif_names.append(name)

        # Read resource entries - filter to ITM only
        itm_resources = []
        f.seek(res_offset)
        for _ in range(res_count):
            data = f.read(14)
            name = data[0:8].rstrip(b"\x00").decode("ascii", errors="replace")
            res_type = struct.unpack("<H", data[8:10])[0]
            locator = struct.unpack("<I", data[10:14])[0]
            if res_type == RES_TYPE_ITM:
                bif_idx = (locator >> 20) & 0xFFF
                file_idx = locator & 0x3FFF
                itm_resources.append((name, bif_idx, file_idx))

    return bif_names, itm_resources


# ── BIF reader ───────────────────────────────────────────────────────────────
def read_bif_resource(bif_path, file_idx):
    """Read a single resource from a BIF file by its file index."""
    with open(bif_path, "rb") as f:
        sig = f.read(4)
        ver = f.read(4)
        if sig != b"BIFF" or ver != b"V1  ":
            return None
        file_count = struct.unpack("<I", f.read(4))[0]
        tileset_count = struct.unpack("<I", f.read(4))[0]
        file_entries_off = struct.unpack("<I", f.read(4))[0]

        # Each file entry is 16 bytes
        # Search for matching file_idx
        f.seek(file_entries_off)
        for i in range(file_count):
            data = f.read(16)
            loc = struct.unpack("<I", data[0:4])[0]
            offset = struct.unpack("<I", data[4:8])[0]
            size = struct.unpack("<I", data[8:12])[0]
            res_type = struct.unpack("<H", data[12:14])[0]
            entry_file_idx = loc & 0x3FFF
            if entry_file_idx == file_idx:
                f.seek(offset)
                return f.read(size)
    return None


# ── ITM parser ───────────────────────────────────────────────────────────────
def parse_itm(data):
    """Parse an ITM v1 header. Returns dict or None if invalid."""
    if len(data) < 0x72:
        return None
    sig = data[0:4]
    if sig != b"ITM ":
        return None

    unid_name_ref = struct.unpack("<i", data[0x08:0x0C])[0]
    id_name_ref   = struct.unpack("<i", data[0x0C:0x10])[0]
    flags         = struct.unpack("<I", data[0x18:0x1C])[0]
    item_type     = struct.unpack("<H", data[0x1C:0x1E])[0]
    price         = struct.unpack("<I", data[0x34:0x38])[0]
    stack         = struct.unpack("<H", data[0x38:0x3A])[0]
    lore          = struct.unpack("<H", data[0x42:0x44])[0]
    weight        = struct.unpack("<I", data[0x4C:0x50])[0]
    unid_desc_ref = struct.unpack("<i", data[0x50:0x54])[0]
    id_desc_ref   = struct.unpack("<i", data[0x54:0x58])[0]
    enchantment   = struct.unpack("<I", data[0x60:0x64])[0]

    # Extended header count & offset for damage info
    ext_hdr_offset = struct.unpack("<I", data[0x64:0x68])[0]
    ext_hdr_count  = struct.unpack("<H", data[0x68:0x6A])[0]

    # Parse first extended header for weapon damage info
    dmg_dice = dmg_sides = dmg_bonus = thac0_bonus = speed = 0
    attack_type = 0
    if ext_hdr_count > 0 and ext_hdr_offset + 56 <= len(data):
        eh = data[ext_hdr_offset:ext_hdr_offset + 56]
        attack_type = eh[0]
        speed       = eh[0x12]
        thac0_bonus = struct.unpack("<h", eh[0x14:0x16])[0]
        dmg_sides   = eh[0x16]
        dmg_dice    = eh[0x18]
        dmg_bonus   = struct.unpack("<h", eh[0x1A:0x1C])[0]

    return {
        "unid_name_ref": unid_name_ref,
        "id_name_ref": id_name_ref,
        "flags": flags,
        "item_type": item_type,
        "price": price,
        "stack": stack,
        "lore": lore,
        "weight": weight,
        "unid_desc_ref": unid_desc_ref,
        "id_desc_ref": id_desc_ref,
        "enchantment": enchantment,
        "attack_type": attack_type,
        "speed": speed,
        "thac0_bonus": thac0_bonus,
        "dmg_dice": dmg_dice,
        "dmg_sides": dmg_sides,
        "dmg_bonus": dmg_bonus,
    }


# ── Description summarizer ───────────────────────────────────────────────────
def summarize_desc(full_desc, max_len=2000):
    """Create a summary from a full item description. Cards truncate visually via
    CSS line-clamp; the modal shows the full text. 2000 chars is enough for all
    vanilla descriptions while still capping pathological edge cases."""
    if not full_desc:
        return ""
    # Take first meaningful sentence/line
    # Remove common header patterns
    text = full_desc.strip()
    # Skip lines that are just the item name or STATISTICS header
    lines = text.split("\n")
    summary_lines = []
    in_stats = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("STATISTICS"):
            in_stats = True
            continue
        if in_stats:
            # Grab key stats lines
            if any(line.startswith(p) for p in ["Damage:", "THAC0:", "Speed Factor:", "Armor Class:",
                                                  "Weight:", "Combat Abilities:", "Equipped Abilities:",
                                                  "Charge Abilities:", "Special:"]):
                summary_lines.append(line)
        elif not in_stats and len(summary_lines) == 0:
            # First paragraph before STATISTICS
            if len(line) > 10:
                summary_lines.append(line)
                if len(" ".join(summary_lines)) > max_len:
                    break

    result = " ".join(summary_lines)
    if len(result) > max_len:
        result = result[:max_len - 3] + "..."
    return result


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    write_mode = "--write" in sys.argv

    print("Reading chitin.key...")
    bif_names, itm_resources = read_key(KEY_PATH)
    print(f"  Found {len(bif_names)} BIF files, {len(itm_resources)} ITM resources")

    print("Loading dialog.tlk...")
    tlk = TlkReader(TLK_PATH)
    print(f"  {tlk.count} string entries")

    # Group ITM resources by BIF index for efficient batch reading
    by_bif = {}
    for name, bif_idx, file_idx in itm_resources:
        by_bif.setdefault(bif_idx, []).append((name, file_idx))

    items = {}
    skipped = 0
    errors = 0

    print("Extracting items from BIF archives...")
    for bif_idx, entries in sorted(by_bif.items()):
        bif_rel = bif_names[bif_idx]
        bif_path = os.path.join(BG2EE, bif_rel.replace("/", os.sep))
        if not os.path.exists(bif_path):
            print(f"  WARNING: BIF not found: {bif_path}")
            skipped += len(entries)
            continue

        # Read entire BIF into memory for batch extraction
        with open(bif_path, "rb") as bf:
            bif_data = bf.read()

        if bif_data[:4] != b"BIFF" or bif_data[4:8] != b"V1  ":
            print(f"  WARNING: Bad BIF signature: {bif_path}")
            skipped += len(entries)
            continue

        file_count = struct.unpack("<I", bif_data[8:12])[0]
        file_entries_off = struct.unpack("<I", bif_data[16:20])[0]

        # Build index of file entries
        file_index = {}
        for i in range(file_count):
            base = file_entries_off + i * 16
            loc = struct.unpack("<I", bif_data[base:base+4])[0]
            offset = struct.unpack("<I", bif_data[base+4:base+8])[0]
            size = struct.unpack("<I", bif_data[base+8:base+12])[0]
            idx = loc & 0x3FFF
            file_index[idx] = (offset, size)

        for name, file_idx in entries:
            if file_idx not in file_index:
                skipped += 1
                continue
            offset, size = file_index[file_idx]
            itm_data = bif_data[offset:offset+size]
            parsed = parse_itm(itm_data)
            if not parsed:
                errors += 1
                continue

            # Resolve names from TLK
            id_name = tlk.get(parsed["id_name_ref"])
            unid_name = tlk.get(parsed["unid_name_ref"])
            display_name = id_name or unid_name

            # Skip items with no name (internal/unused)
            if not display_name:
                skipped += 1
                continue

            # Get description
            id_desc = tlk.get(parsed["id_desc_ref"])
            unid_desc = tlk.get(parsed["unid_desc_ref"])
            desc = summarize_desc(id_desc or unid_desc)

            # Build compact item entry
            cat = ITEM_CATEGORIES.get(parsed["item_type"], f"unknown({parsed['item_type']})")
            resref = name.upper()

            entry = {"n": display_name, "type": cat}

            # Only include enchantment for weapons/armor/shields
            if parsed["enchantment"] > 0:
                entry["ench"] = parsed["enchantment"]

            # Price (skip 0)
            if parsed["price"] > 0:
                entry["price"] = parsed["price"]

            # Weight (skip 0)
            if parsed["weight"] > 0:
                entry["wt"] = parsed["weight"]

            # Description summary
            if desc:
                entry["desc"] = desc

            items[resref] = entry

    tlk.close()

    # Stats
    print(f"\nResults:")
    print(f"  Total ITM resources: {len(itm_resources)}")
    print(f"  Extracted items: {len(items)}")
    print(f"  Skipped (no name/missing): {skipped}")
    print(f"  Errors: {errors}")

    # Category breakdown
    cats = {}
    for v in items.values():
        cats[v["type"]] = cats.get(v["type"], 0) + 1
    print(f"\nBy category:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    if write_mode:
        # Sort by resref for stable output
        sorted_items = dict(sorted(items.items()))
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted_items, f, indent=2, ensure_ascii=False)
        print(f"\nWrote {OUT_PATH} ({os.path.getsize(OUT_PATH) // 1024} KB)")
    else:
        print(f"\nDry run. Use --write to generate {OUT_PATH}")
        # Print a few samples
        print("\nSample items:")
        count = 0
        for ref, item in sorted(items.items()):
            if count >= 10:
                break
            print(f"  {ref}: {json.dumps(item)}")
            count += 1


if __name__ == "__main__":
    main()
