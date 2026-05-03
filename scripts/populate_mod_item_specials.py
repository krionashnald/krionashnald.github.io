#!/usr/bin/env python3
"""
populate_mod_item_specials.py — Extract structured special arrays for mod items.

Reads .itm files from extracted mod folders, builds special arrays,
and stores them in the mod detail files alongside the stats (position 4).

The stats dict at position 4 gets a "special" key removed (old format),
and a new top-level "special" key is added to the stats dict...
Actually, for mod items the special goes INTO the stats object at position 4
since that's what gets merged into resolvedItems.

Usage:
    python scripts/populate_mod_item_specials.py [--write]
"""

import struct, json, os, sys, re

PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_PATH = os.path.join(PROJ, "data", "item_scan_report.json")
MODS_DIR = os.path.join(PROJ, "data", "mods")
BG2EE = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition"
TLK_PATH = os.path.join(BG2EE, "lang", "en_US", "dialog.tlk")

sys.path.insert(0, os.path.dirname(__file__))
from populate_item_specials import extract_specials, TlkReader


def build_file_index(mod_dir):
    idx = {}
    for root, dirs, files in os.walk(mod_dir):
        for fname in files:
            idx[fname.upper()] = os.path.join(root, fname)
    return idx


def build_copy_map(all_files):
    copy_map = {}
    pat = re.compile(r'COPY\s+~([^~]+)\.itm~\s+~override/([^~]+)\.itm~', re.I)
    for fkey, fpath in all_files.items():
        if not fkey.endswith((".TP2", ".TPA", ".TPH")):
            continue
        try:
            content = open(fpath, "r", errors="replace").read()
        except:
            continue
        for m in pat.finditer(content):
            src_base = m.group(1).replace("\\", "/").split("/")[-1].upper()
            dst = m.group(2).upper()
            sp = all_files.get(src_base + ".ITM")
            if sp:
                copy_map[dst] = sp
    return copy_map


def main():
    write_mode = "--write" in sys.argv

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    print("Loading dialog.tlk...")
    tlk = TlkReader(TLK_PATH)

    print("Populating mod item specials...\n")

    total = 0
    specials_added = 0
    old_removed = 0
    mods_updated = 0

    for tp2, data in sorted(report.items()):
        if data.get("status") != "found" or not data.get("dir"):
            continue
        mod_dir = data["dir"]

        # Find mod detail file
        mod_path = None
        mod = None
        for fname in os.listdir(MODS_DIR):
            if not fname.endswith(".json") or fname.startswith("_"):
                continue
            fp = os.path.join(MODS_DIR, fname)
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    m = json.load(f)
                if m.get("t", "").lower() == tp2.lower():
                    mod_path = fp
                    mod = m
                    break
            except:
                continue

        if not mod_path or "items" not in mod:
            continue

        all_files = build_file_index(mod_dir)
        copy_map = build_copy_map(all_files)
        mod_changed = False

        for ci_str, entry in mod["items"].items():
            if "new" not in entry:
                continue
            for arr in entry["new"]:
                resref = arr[0]
                total += 1

                # Ensure array has stats dict at position 4
                while len(arr) < 5:
                    arr.append({} if len(arr) == 4 else "")
                if not isinstance(arr[4], dict):
                    arr[4] = {}

                stats = arr[4]

                # Remove old string "special" from stats
                if "special" in stats and isinstance(stats["special"], str):
                    del stats["special"]
                    old_removed += 1
                    mod_changed = True

                # Find .itm file
                itm_path = all_files.get(resref + ".ITM") or copy_map.get(resref)
                if not itm_path:
                    continue

                try:
                    with open(itm_path, "rb") as f:
                        itm_data = f.read()
                except:
                    continue

                specials = extract_specials(itm_data, tlk)
                if specials:
                    stats["special"] = specials
                    specials_added += 1
                    mod_changed = True

        if mod_changed:
            mods_updated += 1
            if write_mode:
                with open(mod_path, "w", encoding="utf-8") as f:
                    json.dump(mod, f, indent=2, ensure_ascii=False)

    tlk.close()

    print(f"Results:")
    print(f"  Total mod items: {total}")
    print(f"  Specials added: {specials_added}")
    print(f"  Old string specials removed: {old_removed}")
    print(f"  Mods updated: {mods_updated}")

    if not write_mode:
        print(f"\nDry run. Use --write to update mod files.")


if __name__ == "__main__":
    main()
