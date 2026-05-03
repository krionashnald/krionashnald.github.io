#!/usr/bin/env python3
"""Extract authoritative spell metadata from BG2EE SPL files via chitin.key/BIFs.

Replaces heuristic ct/rng/aoe/sv data in data/spells-vanilla.json with
authoritative values from the game data. Preserves: n, type, lv, school,
desc, icon, sph, cls, scr, si (these come from other passes).

Usage:
    python scripts/extract_vanilla_spells_spl.py            # report only
    python scripts/extract_vanilla_spells_spl.py --write    # update JSON
"""
import json
import os
import struct
import sys
from collections import OrderedDict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPELLS_PATH = os.path.join(ROOT, "data", "spells-vanilla.json")

BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE, "chitin.key")
DATA_DIR = os.path.join(BG2EE, "data")

SPL_TYPE = 0x3EE  # SPL resource type code

# Save bitfield in feature blocks (BG2EE):
#   0x01 spell, 0x02 breath, 0x04 death, 0x08 wand, 0x10 polymorph, 0x20 petr
SAVE_BITS = [
    (0x04, "death"),         # death/poison — strongest
    (0x20, "petrification"), # paralysis/petrification
    (0x10, "polymorph"),
    (0x02, "breath"),
    (0x01, "spell"),
    (0x08, "wand"),
]

# Target type from extended header (0x0C):
#   0=none, 1=creature, 2=area target, 3=dead, 4=area auto/caster, 5=projectile,
#   6=living actor, 7=self, 8=group, 9=area sticky
TARGET_TYPE_RNG = {
    0: "none", 7: "self", 4: "self", 9: "self",
}


def read_key(path):
    """Return (resources_by_name, bif_paths). resources is dict name->(bifIdx,fileIdx,type)."""
    with open(path, "rb") as f:
        sig = f.read(4); ver = f.read(4)
        bif_count, res_count, bif_off, res_off = struct.unpack("<IIII", f.read(16))

        # Read BIF entries
        f.seek(bif_off)
        bifs = []
        for _ in range(bif_count):
            length = struct.unpack("<I", f.read(4))[0]
            offset = struct.unpack("<I", f.read(4))[0]
            name_len = struct.unpack("<H", f.read(2))[0]
            location = struct.unpack("<H", f.read(2))[0]
            bifs.append({"length": length, "offset": offset, "name_len": name_len, "loc": location})
        # Read BIF names
        for b in bifs:
            cur = f.tell()
            f.seek(b["offset"])
            b["name"] = f.read(b["name_len"]).rstrip(b"\x00").decode("latin-1").replace("\\", "/")
            f.seek(cur)

        # Read resource entries
        f.seek(res_off)
        resources = {}
        for _ in range(res_count):
            name = f.read(8).rstrip(b"\x00").decode("latin-1").upper()
            rtype = struct.unpack("<H", f.read(2))[0]
            locator = struct.unpack("<I", f.read(4))[0]
            if rtype != SPL_TYPE:
                continue
            bif_idx = (locator >> 20) & 0xFFF
            file_idx = locator & 0x3FFF
            resources[name] = (bif_idx, file_idx)

    return resources, bifs


def read_bif_resource(bif_path, file_idx):
    """Read a single resource from a BIF V1 file by file_idx."""
    with open(bif_path, "rb") as f:
        sig = f.read(4); ver = f.read(4)
        if sig != b"BIFF":
            raise ValueError(f"Not a BIFF: {bif_path}")
        file_count, tile_count, files_off = struct.unpack("<III", f.read(12))
        f.seek(files_off + file_idx * 16)
        locator = struct.unpack("<I", f.read(4))[0]
        offset = struct.unpack("<I", f.read(4))[0]
        size = struct.unpack("<I", f.read(4))[0]
        rtype = struct.unpack("<H", f.read(2))[0]
        f.seek(offset)
        return f.read(size)


def parse_spl(data):
    """Parse SPL V1 bytes. Returns dict with ct, rng, aoe, sv."""
    if len(data) < 0x72 or data[:4] != b"SPL ":
        return None

    # Header fields (SPL V1.0 — note: spell level lives at 0x34 not 0x32;
    # 0x32 is a 2-byte sub-type/pad field)
    spell_type = struct.unpack_from("<H", data, 0x1C)[0]
    school = data[0x25]
    sph_byte = data[0x26]
    spell_level = struct.unpack_from("<I", data, 0x34)[0]
    ext_off = struct.unpack_from("<I", data, 0x64)[0]
    ext_count = struct.unpack_from("<H", data, 0x68)[0]
    fb_off = struct.unpack_from("<I", data, 0x6A)[0]
    casting_idx = struct.unpack_from("<H", data, 0x6E)[0]
    casting_count = struct.unpack_from("<H", data, 0x70)[0]

    if ext_count == 0 or ext_off + 40 > len(data):
        return {"ct": spell_level or 1, "rng": "self", "aoe": "single", "sv": "none"}

    # Read first extended header (primary cast)
    eh = data[ext_off : ext_off + 40]
    target_type = eh[0x0C]
    rng_ft = struct.unpack_from("<h", eh, 0x0E)[0]   # signed feet
    cast_time = struct.unpack_from("<H", eh, 0x12)[0]
    eh_fb_count = struct.unpack_from("<H", eh, 0x1E)[0]
    eh_fb_idx = struct.unpack_from("<H", eh, 0x20)[0]
    projectile = struct.unpack_from("<H", eh, 0x26)[0]

    # Range string. SPL stores ft directly; categorize sensibly.
    if target_type in TARGET_TYPE_RNG:
        rng = TARGET_TYPE_RNG[target_type]
    elif rng_ft <= 0:
        rng = "self"
    elif rng_ft <= 1:
        rng = "touch"
    elif rng_ft >= 100:
        rng = "visual"
    else:
        rng = f"{rng_ft} ft"

    # AoE from target_type (IESDP):
    #   0=none, 1=creature, 2=area target, 3=dead, 4=area auto/caster,
    #   5=any creature (single, projectile-delivered), 6=living, 7=self,
    #   8=key/group, 9=area sticky
    if target_type in (2, 4, 9):
        aoe = "area"
    elif target_type == 7:
        aoe = "caster"
    else:
        # 1, 3, 5, 6, 8 are all single-target variants
        aoe = "single"

    # Save type — scan feature blocks attached to this casting header.
    # Take the highest-priority save bit found across all FBs (death > petr >
    # polymorph > breath > spell > wand) per SAVE_BITS order.
    save_type = "none"
    save_priority = len(SAVE_BITS)
    if eh_fb_count > 0 and fb_off > 0:
        for i in range(eh_fb_count):
            block_off = fb_off + (eh_fb_idx + i) * 48
            if block_off + 48 > len(data):
                break
            save_byte = data[block_off + 0x24]
            if save_byte == 0:
                continue
            for prio, (bit, name) in enumerate(SAVE_BITS):
                if save_byte & bit and prio < save_priority:
                    save_type = name
                    save_priority = prio
                    break

    return {
        "ct": cast_time if cast_time > 0 else (spell_level or 1),
        "rng": rng,
        "aoe": aoe,
        "sv": save_type,
    }


def main():
    write = "--write" in sys.argv

    print("Reading chitin.key...")
    resources, bifs = read_key(KEY_PATH)
    print(f"  Found {len(resources)} SPL resources in {len(bifs)} BIFs")

    with open(SPELLS_PATH, "r", encoding="utf-8") as f:
        spells = json.load(f, object_pairs_hook=OrderedDict)

    matched = 0
    parse_fails = 0
    not_in_bif = []
    sv_dist = Counter()
    rng_dist = Counter()
    aoe_dist = Counter()
    ct_dist = Counter()

    diffs = []  # ref, field, old, new

    for ref, entry in spells.items():
        # Skip non-spell metadata entries (e.g. _slotBaseline)
        if not isinstance(entry, dict) or entry.get("type") not in ("wizard","priest","innate","hla"):
            continue
        ref_u = ref.upper()
        if ref_u not in resources:
            not_in_bif.append(ref)
            continue
        bif_idx, file_idx = resources[ref_u]
        bif = bifs[bif_idx]
        bif_path = os.path.join(BG2EE, bif["name"])
        if not os.path.exists(bif_path):
            not_in_bif.append(ref + " (bif missing)")
            continue
        try:
            data = read_bif_resource(bif_path, file_idx)
            parsed = parse_spl(data)
            if not parsed:
                parse_fails += 1
                continue
        except Exception as e:
            print(f"  ERR {ref}: {e}")
            parse_fails += 1
            continue

        matched += 1
        for field in ("ct", "rng", "aoe", "sv"):
            old = entry.get(field)
            new = parsed[field]
            if old != new:
                diffs.append((ref, field, old, new))
            if write:
                entry[field] = new
        sv_dist[parsed["sv"]] += 1
        rng_dist[parsed["rng"]] += 1
        aoe_dist[parsed["aoe"]] += 1
        ct_dist[parsed["ct"]] += 1

    print(f"\nMatched: {matched}")
    print(f"Parse failures: {parse_fails}")
    print(f"Not in BIF: {len(not_in_bif)}")
    if not_in_bif:
        print(f"  {not_in_bif[:20]}")
    print(f"\nDiffs vs heuristic data: {len(diffs)}")
    if diffs:
        print(f"  Sample: {diffs[:10]}")
    print(f"\nSave distribution (from SPL): {dict(sv_dist)}")
    print(f"Range distribution top: {sorted(rng_dist.items(), key=lambda x:-x[1])[:8]}")
    print(f"AoE distribution: {dict(aoe_dist)}")
    print(f"CT distribution: {sorted(ct_dist.items())}")

    if write:
        with open(SPELLS_PATH, "w", encoding="utf-8") as f:
            json.dump(spells, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("\n[WROTE] spells-vanilla.json updated.")
    else:
        print("\n(dry run — pass --write to apply)")


if __name__ == "__main__":
    main()
