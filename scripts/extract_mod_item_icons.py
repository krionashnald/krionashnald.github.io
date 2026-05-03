#!/usr/bin/env python3
"""
Extract item icons from mod extracted folders.
For each mod item in item_scan_report.json, finds the .itm file,
reads its inventory icon BAM resref, locates the BAM, and converts to PNG.

Usage:
    python scripts/extract_mod_item_icons.py [--write]
"""

import struct, json, os, sys, zlib, glob
from PIL import Image

PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_PATH = os.path.join(PROJ, "data", "item_scan_report.json")
ICONS_DIR = os.path.join(PROJ, "items", "icons")

# Also check vanilla BIF for shared BAMs
BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE, "chitin.key")

RES_TYPE_BAM = 0x03E8


def get_itm_icon_resref(itm_path):
    """Read inventory icon resref from an ITM file."""
    try:
        with open(itm_path, "rb") as f:
            data = f.read(0x42)
        if len(data) < 0x42 or data[0:4] != b"ITM ":
            return None
        resref = data[0x3A:0x42].rstrip(b"\x00").decode("ascii", errors="replace").strip()
        return resref.upper() if resref else None
    except:
        return None


def parse_bam_first_frame(bam_data):
    """Parse BAM v1/BAMC and return first frame as RGBA Image."""
    if not bam_data or len(bam_data) < 24:
        return None

    sig = bam_data[0:4]
    if sig == b"BAMC":
        if len(bam_data) < 12:
            return None
        try:
            bam_data = zlib.decompress(bam_data[12:])
        except zlib.error:
            return None
        sig = bam_data[0:4]

    if sig != b"BAM " or bam_data[4:8] != b"V1  ":
        return None

    frame_count = struct.unpack("<H", bam_data[8:10])[0]
    transparent_idx = bam_data[11]
    frame_offset = struct.unpack("<I", bam_data[12:16])[0]
    palette_offset = struct.unpack("<I", bam_data[16:20])[0]

    if frame_count == 0 or frame_offset + 12 > len(bam_data):
        return None
    if palette_offset + 1024 > len(bam_data):
        return None

    w = struct.unpack("<H", bam_data[frame_offset:frame_offset + 2])[0]
    h = struct.unpack("<H", bam_data[frame_offset + 2:frame_offset + 4])[0]
    data_field = struct.unpack("<I", bam_data[frame_offset + 8:frame_offset + 12])[0]
    is_uncomp = bool(data_field & 0x80000000)
    data_offset = data_field & 0x7FFFFFFF

    if w == 0 or h == 0 or w > 256 or h > 256:
        return None

    palette = []
    for i in range(256):
        po = palette_offset + i * 4
        b, g, r, a = bam_data[po], bam_data[po + 1], bam_data[po + 2], bam_data[po + 3]
        palette.append((r, g, b, 0 if i == transparent_idx else 255))

    pixel_count = w * h
    pixels = []

    if is_uncomp:
        for i in range(pixel_count):
            if data_offset + i >= len(bam_data):
                break
            idx = bam_data[data_offset + i]
            pixels.append((0, 0, 0, 0) if idx == transparent_idx else palette[idx])
    else:
        pos = data_offset
        while len(pixels) < pixel_count and pos < len(bam_data):
            idx = bam_data[pos]
            pos += 1
            if idx == transparent_idx:
                if pos >= len(bam_data):
                    pixels.append((0, 0, 0, 0))
                    break
                count = bam_data[pos] + 1
                pos += 1
                pixels.extend([(0, 0, 0, 0)] * count)
            else:
                pixels.append(palette[idx])

    if len(pixels) < pixel_count:
        pixels.extend([(0, 0, 0, 0)] * (pixel_count - len(pixels)))

    img = Image.new("RGBA", (w, h))
    img.putdata(pixels[:pixel_count])
    return img


def build_vanilla_bam_index():
    """Build lookup of BAM resrefs -> (bif_path, offset, size) from vanilla game."""
    if not os.path.exists(KEY_PATH):
        return {}

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

        bam_res = {}
        f.seek(res_offset)
        for _ in range(res_count):
            d = f.read(14)
            name = d[0:8].rstrip(b"\x00").decode("ascii", errors="replace").upper()
            rt = struct.unpack("<H", d[8:10])[0]
            loc = struct.unpack("<I", d[10:14])[0]
            if rt == RES_TYPE_BAM:
                bif_idx = (loc >> 20) & 0xFFF
                file_idx = loc & 0x3FFF
                bam_res[name] = (bif_idx, file_idx)

    return bam_res, bif_names


def read_vanilla_bam(bam_ref, bam_res, bif_names):
    """Read a BAM from vanilla BIF archives."""
    if bam_ref not in bam_res:
        return None
    bif_idx, file_idx = bam_res[bam_ref]
    bif_path = os.path.join(BG2EE, bif_names[bif_idx].replace("/", os.sep))
    if not os.path.exists(bif_path):
        return None
    with open(bif_path, "rb") as bf:
        bf.read(8)
        fc = struct.unpack("<I", bf.read(4))[0]
        bf.read(4)
        feo = struct.unpack("<I", bf.read(4))[0]
        bf.seek(feo)
        for _ in range(fc):
            d = bf.read(16)
            loc = struct.unpack("<I", d[0:4])[0]
            if (loc & 0x3FFF) == file_idx:
                off = struct.unpack("<I", d[4:8])[0]
                sz = struct.unpack("<I", d[8:12])[0]
                bf.seek(off)
                return bf.read(sz)
    return None


def main():
    write_mode = "--write" in sys.argv

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    print("Building vanilla BAM index...")
    bam_res, bif_names = build_vanilla_bam_index()
    print(f"  {len(bam_res)} vanilla BAMs indexed")

    if write_mode:
        os.makedirs(ICONS_DIR, exist_ok=True)

    extracted = 0
    skipped_existing = 0
    no_itm = 0
    no_bam = 0
    failed = 0
    icon_updates = {}  # tp2 -> {resref -> icon_path}

    for tp2, data in sorted(report.items()):
        if data.get("status") != "found" or not data.get("dir"):
            continue
        mod_dir = data["dir"]
        items = data.get("items", [])

        # Build case-insensitive file lookup for this mod
        all_files = {}
        for root, dirs, files in os.walk(mod_dir):
            for fname in files:
                all_files[fname.upper()] = os.path.join(root, fname)

        # Build dest->source mapping from tp2 COPY patterns
        # Handles cases like COPY ~mod/itm/CU#SC000.itm~ ~override/CU#SC001.itm~
        copy_map = {}  # dest_resref -> source_path
        for fkey, fpath in all_files.items():
            if not fkey.endswith((".TP2", ".TPA", ".TPH")):
                continue
            try:
                content = open(fpath, "r", errors="replace").read()
            except:
                continue
            import re
            for m in re.finditer(r'COPY\s+~([^~]+?([^~/\\]+)\.itm)~\s+~override/([^~]+\.itm)~', content, re.I):
                src_rel = m.group(1)  # e.g., customs/itm/CU#SC000.itm
                dst_name = m.group(3).upper().replace(".ITM", "")  # e.g., CU#SC001
                # Resolve source path
                src_key = m.group(2).upper() + ".ITM"
                src_path = all_files.get(src_key)
                if not src_path:
                    # Try resolving relative to mod's parent (tp2 paths are relative to game dir)
                    parts = src_rel.replace("\\", "/").split("/")
                    if len(parts) >= 2:
                        sub = os.sep.join(parts[1:]).upper()
                        for k, v in all_files.items():
                            if v.upper().endswith(sub):
                                src_path = v
                                break
                if src_path:
                    copy_map[dst_name] = src_path

        mod_icons = {}

        for item in items:
            resref = item["resref"]
            png_name = "I" + resref + ".png"
            png_path = os.path.join(ICONS_DIR, png_name)

            if os.path.exists(png_path):
                skipped_existing += 1
                mod_icons[resref] = f"items/icons/{png_name}"
                continue

            # Find the .itm file: direct match, then copy_map fallback
            itm_key = resref + ".ITM"
            itm_path = all_files.get(itm_key) or copy_map.get(resref)
            if not itm_path:
                no_itm += 1
                continue

            # Read icon BAM resref from ITM
            bam_ref = get_itm_icon_resref(itm_path)
            if not bam_ref:
                no_bam += 1
                continue

            # Find the BAM: first in mod folder, then in vanilla
            bam_key = bam_ref + ".BAM"
            bam_path = all_files.get(bam_key)
            bam_data = None

            if bam_path:
                with open(bam_path, "rb") as bf:
                    bam_data = bf.read()
            else:
                # Try vanilla
                bam_data = read_vanilla_bam(bam_ref, bam_res, bif_names)

            if not bam_data:
                no_bam += 1
                continue

            img = parse_bam_first_frame(bam_data)
            if not img:
                failed += 1
                continue

            if write_mode:
                if img.size != (48, 48):
                    img = img.resize((48, 48), Image.Resampling.NEAREST)
                img.save(png_path, "PNG", optimize=True)

            mod_icons[resref] = f"items/icons/{png_name}"
            extracted += 1

        if mod_icons:
            icon_updates[tp2] = mod_icons

    print(f"\nResults:")
    print(f"  Extracted: {extracted}")
    print(f"  Skipped (existing): {skipped_existing}")
    print(f"  No .itm found: {no_itm}")
    print(f"  No .bam found: {no_bam}")
    print(f"  Failed to parse: {failed}")
    print(f"  Mods with icons: {len(icon_updates)}")

    # Report icon availability
    if icon_updates:
        total_icons = sum(len(v) for v in icon_updates.values())
        print(f"\n  {total_icons} icons available across {len(icon_updates)} mods")

    if not write_mode:
        print(f"\nDry run. Use --write to extract icons.")
        for tp2, icons in list(icon_updates.items())[:5]:
            print(f"  {tp2}: {len(icons)} icons")
            for ref, path in list(icons.items())[:3]:
                print(f"    {ref} -> {path}")


if __name__ == "__main__":
    main()
