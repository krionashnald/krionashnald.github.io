#!/usr/bin/env python3
"""
Extract spell icons from mod extracted folders.

For each .spl file in a mod directory, reads the spell-book icon BAM resref
at offset 0x38, locates the BAM (in the mod first, then vanilla BIFs), and
converts its first frame to PNG. Output: spells/icons/<SPL_name>.png.

Usage:
    python scripts/extract_mod_spell_icons.py <mod_dir> [--write]
    python scripts/extract_mod_spell_icons.py --all-placeholders [--write]

Without --write, prints a report only. With --write, creates PNG files in
spells/icons/.

Shares the BAM parser with extract_mod_item_icons.py.
"""
import glob
import json
import os
import struct
import sys
import zlib

# Windows console: force UTF-8 output
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ICONS_DIR = os.path.join(PROJ, "spells", "icons")
MODS_DIR = os.path.join(PROJ, "data", "mods")

BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE, "chitin.key")

RES_TYPE_BAM = 0x03E8


# ── BAM → PNG (copied from extract_mod_item_icons.py) ────────────────────────
def parse_bam_first_frame(bam_data):
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


# ── Vanilla BAM index (BIF) ──────────────────────────────────────────────────
def build_vanilla_bam_index():
    if not os.path.exists(KEY_PATH):
        return {}, []
    with open(KEY_PATH, "rb") as f:
        f.read(8)
        bif_count, res_count = struct.unpack("<II", f.read(8))
        bif_offset, res_offset = struct.unpack("<II", f.read(8))
        f.seek(bif_offset)
        raw = []
        for _ in range(bif_count):
            d = f.read(12)
            raw.append((struct.unpack("<I", d[4:8])[0], struct.unpack("<H", d[8:10])[0]))
        bif_names = []
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


# ── SPL parsing ──────────────────────────────────────────────────────────────
def get_spl_icon_resref(spl_path):
    """Read the spell-book icon resref from an SPL V1 file.

    Layout (post 2-byte shift fix — see extract_vanilla_spells_spl.py notes):
      0x34  4b  spell level
      0x38  2b  stack amount
      0x3A  8b  spell book icon (resref)
    """
    try:
        with open(spl_path, "rb") as f:
            data = f.read(0x44)
        if len(data) < 0x44 or data[0:4] != b"SPL ":
            return None
        resref = data[0x3A:0x42].rstrip(b"\x00").decode("ascii", errors="replace").strip()
        return resref.upper() if resref else None
    except Exception:
        return None


# ── Mod extraction ───────────────────────────────────────────────────────────
def extract_mod_spells(mod_dir, bam_res, bif_names, write_mode=False):
    """Walk mod dir, extract all .spl icons, emit stats + (if --write) PNGs."""
    spls = glob.glob(os.path.join(mod_dir, "**", "*.spl"), recursive=True)
    # Also build a case-insensitive map of .bam files in the mod
    mod_bams = {}
    for root, dirs, files in os.walk(mod_dir):
        for fname in files:
            if fname.upper().endswith(".BAM"):
                mod_bams[fname.upper()[:-4]] = os.path.join(root, fname)

    stats = {
        "total_spls": len(spls),
        "no_icon_ref": 0,
        "extracted": 0,
        "from_mod": 0,
        "from_vanilla": 0,
        "bam_missing": 0,
        "parse_failed": 0,
        "already_exists": 0,
    }
    results = []

    for spl_path in spls:
        spl_name = os.path.basename(spl_path)[:-4].upper()
        # Spell icon filename convention: <SPL_NAME>.png
        png_path = os.path.join(ICONS_DIR, f"{spl_name}.png")

        if os.path.exists(png_path) and not write_mode:
            stats["already_exists"] += 1
            continue
        if os.path.exists(png_path):
            stats["already_exists"] += 1
            continue

        icon_ref = get_spl_icon_resref(spl_path)
        if not icon_ref:
            stats["no_icon_ref"] += 1
            continue

        # Try mod-local BAM first
        bam_data = None
        source = None
        if icon_ref in mod_bams:
            with open(mod_bams[icon_ref], "rb") as f:
                bam_data = f.read()
            source = "mod"
        else:
            # Fallback to vanilla
            bam_data = read_vanilla_bam(icon_ref, bam_res, bif_names)
            if bam_data:
                source = "vanilla"

        if not bam_data:
            stats["bam_missing"] += 1
            results.append((spl_name, icon_ref, "BAM_MISSING"))
            continue

        img = parse_bam_first_frame(bam_data)
        if not img:
            stats["parse_failed"] += 1
            results.append((spl_name, icon_ref, "PARSE_FAIL"))
            continue

        stats["extracted"] += 1
        stats[f"from_{source}"] += 1
        results.append((spl_name, icon_ref, f"OK ({source})"))

        if write_mode:
            os.makedirs(ICONS_DIR, exist_ok=True)
            img.save(png_path)

    return stats, results


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    write_mode = "--write" in args
    if write_mode:
        args.remove("--write")

    if not args:
        print(__doc__)
        sys.exit(1)

    print("Building vanilla BAM index...")
    bam_res, bif_names = build_vanilla_bam_index()
    print(f"  {len(bam_res)} vanilla BAMs")

    mod_dir = args[0]
    if not os.path.isdir(mod_dir):
        print(f"ERROR: {mod_dir} is not a directory")
        sys.exit(1)

    print(f"\nExtracting from: {mod_dir}")
    stats, results = extract_mod_spells(mod_dir, bam_res, bif_names, write_mode)

    print(f"\nStats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    # Show any failures (coerce icon ref to ASCII-safe repr for Windows cp1252)
    fails = [r for r in results if r[2] != "OK (mod)" and r[2] != "OK (vanilla)"]
    if fails:
        print(f"\nFailures ({len(fails)}):")
        for r in fails[:15]:
            safe_icon = repr(r[1])
            print(f"  {r[0]:20} icon={safe_icon:15} {r[2]}")

    if not write_mode:
        print("\n(dry run — pass --write to create PNG files)")


if __name__ == "__main__":
    main()
