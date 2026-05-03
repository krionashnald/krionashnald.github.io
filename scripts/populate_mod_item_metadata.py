#!/usr/bin/env python3
"""
populate_mod_item_metadata.py — Add twoHanded, profType, usability, charges to mod items.

Reads .itm files from extracted mod folders, extracts the same metadata
as populate_item_metadata.py for vanilla, and stores it in the mod item array's
position 4 stats dict (alongside ac/dmg/etc).

Schema in stats dict at position 4:
  {"ac": ..., "dmg": ..., "twoHanded": true, "profType": "...",
   "usability": {...}, "charges": {...}, "special": [...]}

Usage:
    python scripts/populate_mod_item_metadata.py [--write]
"""

import struct, json, os, sys, re

PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_PATH = os.path.join(PROJ, "data", "item_scan_report.json")
MODS_DIR = os.path.join(PROJ, "data", "mods")

sys.path.insert(0, os.path.dirname(__file__))
from populate_item_metadata import extract_metadata


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

    print("Populating mod item metadata...\n")

    total = 0
    twoHanded_added = 0
    profType_added = 0
    usability_added = 0
    charges_added = 0
    cleaned_specials = 0
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

                # Ensure stats dict at position 4
                while len(arr) < 5:
                    arr.append({} if len(arr) == 4 else "")
                if not isinstance(arr[4], dict):
                    arr[4] = {}
                stats = arr[4]

                itm_path = all_files.get(resref + ".ITM") or copy_map.get(resref)
                if not itm_path:
                    continue

                try:
                    with open(itm_path, "rb") as f:
                        itm_data = f.read()
                except:
                    continue

                meta = extract_metadata(itm_data)
                if not meta:
                    continue

                if meta.get("twoHanded"):
                    stats["twoHanded"] = True
                    twoHanded_added += 1
                    mod_changed = True
                if "profType" in meta:
                    stats["profType"] = meta["profType"]
                    profType_added += 1
                    mod_changed = True
                if "usability" in meta:
                    stats["usability"] = meta["usability"]
                    usability_added += 1
                    mod_changed = True
                if "charges" in meta:
                    stats["charges"] = meta["charges"]
                    charges_added += 1
                    mod_changed = True

                    # Strip "ability X/day" entries from special since charges replaces them
                    if "special" in stats and isinstance(stats["special"], list):
                        new_special = [s for s in stats["special"]
                                       if not (s.get("type") == "ability" and "/day" in s.get("desc", ""))]
                        if len(new_special) != len(stats["special"]):
                            cleaned_specials += len(stats["special"]) - len(new_special)
                            if new_special:
                                stats["special"] = new_special
                            else:
                                del stats["special"]

        if mod_changed:
            mods_updated += 1
            if write_mode:
                with open(mod_path, "w", encoding="utf-8") as f:
                    json.dump(mod, f, indent=2, ensure_ascii=False)

    print(f"Results:")
    print(f"  Total mod items: {total}")
    print(f"  twoHanded added: {twoHanded_added}")
    print(f"  profType added: {profType_added}")
    print(f"  usability added: {usability_added}")
    print(f"  charges added: {charges_added}")
    print(f"  Stripped redundant ability/day specials: {cleaned_specials}")
    print(f"  Mods updated: {mods_updated}")

    if not write_mode:
        print(f"\nDry run. Use --write to update mod files.")


if __name__ == "__main__":
    main()
