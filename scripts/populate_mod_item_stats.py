#!/usr/bin/env python3
"""
populate_mod_item_stats.py — Extract stats from mod .itm files and add to mod detail files.

Reads equipping effects + extended headers from each mod item's .itm binary,
then appends a stats object as the 5th element of each items[ci].new array entry.

Usage:
    python scripts/populate_mod_item_stats.py [--write]
"""

import struct, json, os, sys, re

PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_PATH = os.path.join(PROJ, "data", "item_scan_report.json")
MODS_DIR = os.path.join(PROJ, "data", "mods")

# Import extract_stats from the vanilla script
sys.path.insert(0, os.path.dirname(__file__))
from populate_item_stats import extract_stats


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

    print("Populating mod item stats...\n")

    total_items = 0
    stats_added = 0
    no_itm = 0
    no_stats = 0
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
                total_items += 1

                # Ensure array has at least 4 elements
                while len(arr) < 4:
                    arr.append("")

                # Skip if stats already populated (5th element exists and is a dict)
                if len(arr) >= 5 and isinstance(arr[4], dict) and arr[4]:
                    continue

                # Find .itm file
                itm_path = all_files.get(resref + ".ITM") or copy_map.get(resref)
                if not itm_path:
                    no_itm += 1
                    continue

                try:
                    with open(itm_path, "rb") as f:
                        itm_data = f.read()
                except:
                    no_itm += 1
                    continue

                stats = extract_stats(itm_data)
                if stats:
                    # Ensure array has exactly 4 elements before adding stats
                    while len(arr) < 4:
                        arr.append("")
                    if len(arr) == 4:
                        arr.append(stats)
                    elif len(arr) >= 5:
                        arr[4] = stats
                    stats_added += 1
                    mod_changed = True
                else:
                    no_stats += 1

        if mod_changed:
            mods_updated += 1
            if write_mode:
                with open(mod_path, "w", encoding="utf-8") as f:
                    json.dump(mod, f, indent=2, ensure_ascii=False)

    print(f"Results:")
    print(f"  Total mod items: {total_items}")
    print(f"  Stats added: {stats_added}")
    print(f"  No .itm found: {no_itm}")
    print(f"  No stats (empty): {no_stats}")
    print(f"  Mods updated: {mods_updated}")

    if not write_mode:
        print(f"\nDry run. Use --write to update mod files.")

        # Show samples
        print("\nSamples:")
        count = 0
        for tp2, data in sorted(report.items()):
            if data.get("status") != "found":
                continue
            for fname in os.listdir(MODS_DIR):
                if not fname.endswith(".json") or fname.startswith("_"):
                    continue
                fp = os.path.join(MODS_DIR, fname)
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        m = json.load(f)
                    if m.get("t", "").lower() != tp2.lower():
                        continue
                    if "items" not in m:
                        continue
                    for ci_str, entry in m["items"].items():
                        if "new" not in entry:
                            continue
                        for arr in entry["new"]:
                            if len(arr) >= 5 and arr[4]:
                                print(f"  {tp2}: {arr[0]} ({arr[2] or '?'}) -> {json.dumps(arr[4])}")
                                count += 1
                                if count >= 8:
                                    break
                        if count >= 8:
                            break
                except:
                    pass
                if count >= 8:
                    break
            if count >= 8:
                break


if __name__ == "__main__":
    main()
