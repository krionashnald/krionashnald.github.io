#!/usr/bin/env python3
"""
Extract spells + icons for a specific mod prefix from an INSTALLED BG2EE game.

Unlike extract_mod_spell_icons.py (which works on mod source), this reads the
game's override/ (populated by WeiDU installs) plus the patched dialog.tlk,
so you get real spell NAMES along with metadata.

Usage:
    python scripts/extract_installed_mod_spells.py <prefix> [--write] [--report out.json]

    <prefix>   Mod spell prefix (e.g. "D5" for Faiths and Powers, "AC" for Aerial,
               "B_" for bardic mods, etc.)
    --write    Write PNG icons to spells/icons/ (otherwise dry-run)
    --report   Write parsed spell metadata to given JSON path (ref -> {n,type,lv,school,sph,icon})

Installed game path is hard-coded at INSTALL_PATH below.
"""
import glob
import json
import os
import re
import struct
import sys
import zlib

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ICONS_DIR = os.path.join(PROJ, "spells", "icons")

INSTALL_PATH = r"F:\SteamLibrary\steamapps\common\Baldur's Gate II Enhanced Edition"
OVERRIDE_DIR = os.path.join(INSTALL_PATH, "override")
TLK_PATH = os.path.join(INSTALL_PATH, "lang", "en_US", "dialog.tlk")

# Vanilla BIF fallback (for BAMs not in override)
BG2EE_BACKUP = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE_BACKUP, "chitin.key")
RES_TYPE_BAM = 0x03E8


# ── TLK ──────────────────────────────────────────────────────────────────────
def load_tlk(path):
    with open(path, "rb") as f:
        header = f.read(0x12)
        if header[:4] != b"TLK ":
            raise ValueError(f"Not a TLK: {path}")
        count = struct.unpack_from("<I", header, 0x0A)[0]
        strings_offset = struct.unpack_from("<I", header, 0x0E)[0]
        entries = f.read(count * 26)
    return {"count": count, "strings_offset": strings_offset, "entries": entries, "path": path}


def get_string(tlk, strref):
    if strref < 0 or strref >= tlk["count"]:
        return None
    o = strref * 26
    e = tlk["entries"]
    flags = struct.unpack_from("<H", e, o)[0]
    if not (flags & 1):
        return None
    s_off = struct.unpack_from("<I", e, o + 18)[0]
    s_len = struct.unpack_from("<I", e, o + 22)[0]
    with open(tlk["path"], "rb") as f:
        f.seek(tlk["strings_offset"] + s_off)
        return f.read(s_len).decode("latin-1", errors="replace").strip()


# ── BAM → PNG (shared with extract_mod_spell_icons.py) ───────────────────────
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


# ── Vanilla BIF BAM index for fallback ───────────────────────────────────────
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
                bam_res[name] = ((loc >> 20) & 0xFFF, loc & 0x3FFF)
    return bam_res, bif_names


def read_vanilla_bam(bam_ref, bam_res, bif_names):
    if bam_ref not in bam_res:
        return None
    bif_idx, file_idx = bam_res[bam_ref]
    bif_path = os.path.join(BG2EE_BACKUP, bif_names[bif_idx].replace("/", os.sep))
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
            if (struct.unpack("<I", d[0:4])[0] & 0x3FFF) == file_idx:
                off = struct.unpack("<I", d[4:8])[0]
                sz = struct.unpack("<I", d[8:12])[0]
                bf.seek(off)
                return bf.read(sz)
    return None


# ── SPL header parsing ───────────────────────────────────────────────────────
TYPE_MAP = {1: "wizard", 2: "priest", 4: "innate", 5: "song"}
SCHOOL_NAMES = {
    1: "Abjuration", 2: "Conjuration", 3: "Divination", 4: "Enchantment",
    5: "Illusion", 6: "Evocation", 7: "Necromancy", 8: "Alteration",
}

def parse_spl(path, tlk):
    """Return dict with parsed metadata, or None if not a V1 SPL."""
    try:
        with open(path, "rb") as f:
            data = f.read(0x80)
    except Exception:
        return None
    if len(data) < 0x44 or data[0:4] != b"SPL ":
        return None
    name_strref = struct.unpack_from("<I", data, 0x08)[0]
    spell_type = struct.unpack_from("<H", data, 0x1C)[0]
    school = data[0x25]
    lv = struct.unpack_from("<I", data, 0x34)[0]
    icon = data[0x3A:0x42].rstrip(b"\x00").decode("latin-1", errors="replace").strip()
    return {
        "name": get_string(tlk, name_strref),
        "type": TYPE_MAP.get(spell_type, "other"),
        "type_raw": spell_type,
        "lv": lv,
        "school": SCHOOL_NAMES.get(school, f"School{school}"),
        "school_raw": school,
        "icon_ref": icon.upper() if icon else None,
    }


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    write_mode = "--write" in args
    if write_mode:
        args.remove("--write")
    report_path = None
    if "--report" in args:
        i = args.index("--report")
        report_path = args[i + 1]
        args = args[:i] + args[i + 2:]

    if not args:
        print(__doc__)
        sys.exit(1)

    prefix = args[0].upper()
    print(f"Loading TLK from {TLK_PATH}...")
    tlk = load_tlk(TLK_PATH)
    print(f"  {tlk['count']} strings loaded")

    print(f"Building vanilla BAM index...")
    bam_res, bif_names = build_vanilla_bam_index()
    print(f"  {len(bam_res)} vanilla BAMs")

    # Case-insensitive file lookup in override/ for BAMs
    print(f"Indexing override/ BAMs...")
    override_bams = {}
    for p in glob.glob(os.path.join(OVERRIDE_DIR, "*.bam")) + glob.glob(os.path.join(OVERRIDE_DIR, "*.BAM")):
        k = os.path.basename(p).upper()[:-4]
        if k not in override_bams:
            override_bams[k] = p
    print(f"  {len(override_bams)} override BAMs")

    # Find all SPLs matching prefix
    print(f"\nScanning override/ for {prefix}*.spl ...")
    seen = {}
    for p in glob.glob(os.path.join(OVERRIDE_DIR, f"{prefix}*.spl")) + glob.glob(os.path.join(OVERRIDE_DIR, f"{prefix}*.SPL")):
        k = os.path.basename(p).upper()[:-4]
        if k not in seen:
            seen[k] = p
    spls = sorted(seen.items())
    print(f"  {len(spls)} unique {prefix}* SPLs")

    results = {}
    stats = {"parsed": 0, "no_name": 0, "named": 0, "icon_extracted": 0, "icon_missing": 0, "icon_skipped_existing": 0}

    for ref, path in spls:
        meta = parse_spl(path, tlk)
        if not meta:
            continue
        stats["parsed"] += 1
        if meta["name"]:
            stats["named"] += 1
        else:
            stats["no_name"] += 1
        results[ref] = meta

        # Extract icon
        icon_ref = meta["icon_ref"]
        png_path = os.path.join(ICONS_DIR, f"{ref}.png")
        if os.path.exists(png_path):
            stats["icon_skipped_existing"] += 1
            continue
        if not icon_ref:
            stats["icon_missing"] += 1
            continue

        bam_data = None
        if icon_ref in override_bams:
            with open(override_bams[icon_ref], "rb") as f:
                bam_data = f.read()
        else:
            bam_data = read_vanilla_bam(icon_ref, bam_res, bif_names)

        if not bam_data:
            stats["icon_missing"] += 1
            continue

        img = parse_bam_first_frame(bam_data)
        if not img:
            stats["icon_missing"] += 1
            continue

        stats["icon_extracted"] += 1
        if write_mode:
            os.makedirs(ICONS_DIR, exist_ok=True)
            img.save(png_path)

    print("\nStats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nWrote report to {report_path}")

    if not write_mode:
        print("\n(dry run — pass --write to save PNGs)")


if __name__ == "__main__":
    main()
