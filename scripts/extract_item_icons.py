#!/usr/bin/env python3
"""
Extract item inventory icons from BG2EE backup (chitin.key + BIF + BAM).
Reads the inventory icon resref from each ITM, finds the corresponding BAM,
extracts the first frame, and saves as 48x48 PNG to items/icons/.

Also updates items-vanilla.json with icon paths.

Usage:
    python scripts/extract_item_icons.py [--write]
"""

import struct, json, os, sys, zlib
from PIL import Image

# ── Paths ────────────────────────────────────────────────────────────────────
BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
KEY_PATH = os.path.join(BG2EE, "chitin.key")
PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
ICONS_DIR = os.path.join(PROJ, "items", "icons")
ITEMS_JSON = os.path.join(PROJ, "data", "items-vanilla.json")

RES_TYPE_ITM = 0x03ED
RES_TYPE_BAM = 0x03E8

# ── KEY reader ───────────────────────────────────────────────────────────────
def read_key(path):
    with open(path, "rb") as f:
        f.read(8)  # sig + ver
        bif_count, res_count = struct.unpack("<II", f.read(8))
        bif_offset, res_offset = struct.unpack("<II", f.read(8))

        # BIF names
        bif_names = []
        f.seek(bif_offset)
        raw_entries = []
        for _ in range(bif_count):
            d = f.read(12)
            name_off = struct.unpack("<I", d[4:8])[0]
            name_len = struct.unpack("<H", d[8:10])[0]
            raw_entries.append((name_off, name_len))
        for name_off, name_len in raw_entries:
            f.seek(name_off)
            nm = f.read(name_len).decode("ascii", errors="replace").rstrip("\x00")
            bif_names.append(nm.replace("\\", "/"))

        # Resources - collect ITM and BAM
        itm_res = {}  # name -> (bif_idx, file_idx)
        bam_res = {}  # name -> (bif_idx, file_idx)
        f.seek(res_offset)
        for _ in range(res_count):
            d = f.read(14)
            name = d[0:8].rstrip(b"\x00").decode("ascii", errors="replace").upper()
            rt = struct.unpack("<H", d[8:10])[0]
            loc = struct.unpack("<I", d[10:14])[0]
            bif_idx = (loc >> 20) & 0xFFF
            file_idx = loc & 0x3FFF
            if rt == RES_TYPE_ITM:
                itm_res[name] = (bif_idx, file_idx)
            elif rt == RES_TYPE_BAM:
                bam_res[name] = (bif_idx, file_idx)

    return bif_names, itm_res, bam_res


# ── BIF batch reader ─────────────────────────────────────────────────────────
class BifReader:
    """Caches BIF file entry indexes for batch reads."""

    def __init__(self, bg2ee_path, bif_names):
        self.bg2ee = bg2ee_path
        self.bif_names = bif_names
        self._cache = {}  # bif_idx -> {file_idx: (offset, size)}

    def _ensure_bif(self, bif_idx):
        if bif_idx in self._cache:
            return
        bif_rel = self.bif_names[bif_idx]
        bif_path = os.path.join(self.bg2ee, bif_rel.replace("/", os.sep))
        if not os.path.exists(bif_path):
            self._cache[bif_idx] = None
            return
        with open(bif_path, "rb") as bf:
            sig = bf.read(4)
            bf.read(4)  # ver
            if sig != b"BIFF":
                self._cache[bif_idx] = None
                return
            file_count = struct.unpack("<I", bf.read(4))[0]
            bf.read(4)  # tileset count
            feo = struct.unpack("<I", bf.read(4))[0]
            idx = {}
            bf.seek(feo)
            for _ in range(file_count):
                d = bf.read(16)
                loc = struct.unpack("<I", d[0:4])[0]
                offset = struct.unpack("<I", d[4:8])[0]
                size = struct.unpack("<I", d[8:12])[0]
                fi = loc & 0x3FFF
                idx[fi] = (offset, size)
            self._cache[bif_idx] = (bif_path, idx)

    def read(self, bif_idx, file_idx):
        self._ensure_bif(bif_idx)
        entry = self._cache.get(bif_idx)
        if not entry:
            return None
        bif_path, idx = entry
        if file_idx not in idx:
            return None
        offset, size = idx[file_idx]
        with open(bif_path, "rb") as bf:
            bf.seek(offset)
            return bf.read(size)


# ── ITM icon resref extractor ────────────────────────────────────────────────
def get_itm_icon_resref(itm_data):
    """Extract the inventory icon resref from ITM data (offset 0x003a, 8 bytes)."""
    if len(itm_data) < 0x42:
        return None
    resref = itm_data[0x3A:0x42].rstrip(b"\x00").decode("ascii", errors="replace").strip()
    return resref.upper() if resref else None


# ── BAM parser ───────────────────────────────────────────────────────────────
def parse_bam_first_frame(bam_data):
    """Parse a BAM v1 (or BAMC) file and return first frame as RGBA Image."""
    if not bam_data or len(bam_data) < 24:
        return None

    sig = bam_data[0:4]

    # Handle BAMC (compressed BAM)
    if sig == b"BAMC":
        if len(bam_data) < 12:
            return None
        uncompressed_len = struct.unpack("<I", bam_data[8:12])[0]
        try:
            bam_data = zlib.decompress(bam_data[12:])
        except zlib.error:
            return None
        sig = bam_data[0:4]

    if sig != b"BAM ":
        return None

    ver = bam_data[4:8]
    if ver != b"V1  ":
        return None

    frame_count = struct.unpack("<H", bam_data[8:10])[0]
    cycle_count = bam_data[10]
    transparent_idx = bam_data[11]
    frame_offset = struct.unpack("<I", bam_data[12:16])[0]
    palette_offset = struct.unpack("<I", bam_data[16:20])[0]

    if frame_count == 0:
        return None

    # Read first frame entry (12 bytes)
    fe_off = frame_offset
    if fe_off + 12 > len(bam_data):
        return None

    width = struct.unpack("<H", bam_data[fe_off:fe_off + 2])[0]
    height = struct.unpack("<H", bam_data[fe_off + 2:fe_off + 4])[0]
    # center_x, center_y = skip
    data_field = struct.unpack("<I", bam_data[fe_off + 8:fe_off + 12])[0]

    is_uncompressed = bool(data_field & 0x80000000)
    data_offset = data_field & 0x7FFFFFFF

    if width == 0 or height == 0 or width > 256 or height > 256:
        return None

    # Read palette (256 * 4 bytes = BGRA)
    if palette_offset + 1024 > len(bam_data):
        return None
    palette = []
    for i in range(256):
        po = palette_offset + i * 4
        b, g, r, a = bam_data[po], bam_data[po + 1], bam_data[po + 2], bam_data[po + 3]
        # Transparent index gets alpha 0; all others are opaque
        palette.append((r, g, b, 0 if i == transparent_idx else 255))

    # Decode frame pixels
    pixel_count = width * height
    pixels = []

    if is_uncompressed:
        for i in range(pixel_count):
            if data_offset + i >= len(bam_data):
                break
            idx = bam_data[data_offset + i]
            if idx == transparent_idx:
                pixels.append((0, 0, 0, 0))
            else:
                pixels.append(palette[idx])
    else:
        # RLE compressed
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

    # Create image
    img = Image.new("RGBA", (width, height))
    img.putdata(pixels[:pixel_count])
    return img


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    write_mode = "--write" in sys.argv

    print("Reading chitin.key...")
    bif_names, itm_res, bam_res = read_key(KEY_PATH)
    print(f"  {len(itm_res)} ITM resources, {len(bam_res)} BAM resources")

    bif = BifReader(BG2EE, bif_names)

    # Load existing items-vanilla.json
    with open(ITEMS_JSON, "r", encoding="utf-8") as f:
        items = json.load(f)
    print(f"  {len(items)} items in items-vanilla.json")

    # Step 1: Extract icon resref from each ITM
    print("Extracting icon resrefs from ITM files...")
    icon_map = {}  # item_resref -> bam_resref
    for item_ref, (bi, fi) in itm_res.items():
        itm_data = bif.read(bi, fi)
        if not itm_data:
            continue
        icon_resref = get_itm_icon_resref(itm_data)
        if icon_resref and icon_resref in bam_res:
            icon_map[item_ref] = icon_resref

    print(f"  {len(icon_map)} items have valid inventory icons")

    # Step 2: Deduplicate BAM resrefs to extract
    unique_bams = set(icon_map.values())
    print(f"  {len(unique_bams)} unique BAM icons to extract")

    # Step 3: Extract and convert BAMs to PNGs
    if write_mode:
        os.makedirs(ICONS_DIR, exist_ok=True)

    extracted = 0
    failed = 0
    skipped = 0

    print("Extracting BAM icons...")
    for bam_ref in sorted(unique_bams):
        png_path = os.path.join(ICONS_DIR, bam_ref + ".png")

        # Skip if already extracted
        if write_mode and os.path.exists(png_path):
            skipped += 1
            continue

        bi, fi = bam_res[bam_ref]
        bam_data = bif.read(bi, fi)
        if not bam_data:
            failed += 1
            continue

        img = parse_bam_first_frame(bam_data)
        if not img:
            failed += 1
            continue

        if write_mode:
            # Resize to 48x48 if not already (consistent with spell icons)
            if img.size != (48, 48):
                # Use NEAREST for pixel art
                img = img.resize((48, 48), Image.Resampling.NEAREST)
            img.save(png_path, "PNG", optimize=True)

        extracted += 1

    print(f"\nResults:")
    print(f"  Extracted: {extracted}")
    print(f"  Skipped (existing): {skipped}")
    print(f"  Failed: {failed}")

    # Step 4: Update items-vanilla.json with icon paths
    updated = 0
    for item_ref, item in items.items():
        bam_ref = icon_map.get(item_ref)
        if bam_ref:
            item["icon"] = f"items/icons/{bam_ref}.png"
            updated += 1
        elif "icon" in item:
            del item["icon"]

    print(f"  Updated {updated}/{len(items)} items with icon paths")

    if write_mode:
        sorted_items = dict(sorted(items.items()))
        with open(ITEMS_JSON, "w", encoding="utf-8") as f:
            json.dump(sorted_items, f, indent=2, ensure_ascii=False)
        print(f"  Wrote {ITEMS_JSON}")
    else:
        print(f"\nDry run. Use --write to extract icons and update JSON.")
        # Sample
        count = 0
        for ref, item in sorted(items.items()):
            if "icon" in item and count < 5:
                print(f"  {ref}: icon={item['icon']}")
                count += 1


if __name__ == "__main__":
    main()
