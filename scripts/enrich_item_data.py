#!/usr/bin/env python3
"""
enrich_item_data.py — Fix item types from .itm binary and resolve names from TRA files.

For each mod with items data:
1. Read the .itm file to get the real item_type (offset 0x1C)
2. Parse SAY NAME2 @NNN references and resolve from English TRA files
3. Recalculate component itC breakdowns
4. Optionally populate Item Revisions modify entries

Usage:
    python scripts/enrich_item_data.py [--write]
"""

import struct, json, os, sys, re, glob

PROJ = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
REPORT_PATH = os.path.join(PROJ, "data", "item_scan_report.json")
MODS_DIR = os.path.join(PROJ, "data", "mods")
EXTRACTED = r"F:\BGMods\Extracted"

ITEM_CATEGORIES = {
    0: "misc", 1: "amulet", 2: "armor", 3: "belt", 4: "boots", 5: "arrow",
    6: "bracers", 7: "helmet", 8: "key", 9: "potion", 10: "ring", 11: "scroll",
    12: "shield", 13: "food", 14: "bullet", 15: "bow", 16: "dagger", 17: "mace",
    18: "sling", 19: "short sword", 20: "large sword", 21: "hammer", 22: "morning star",
    23: "flail", 24: "dart", 25: "axe", 26: "staff", 27: "crossbow", 28: "fist",
    29: "spear", 30: "halberd", 31: "bolt", 32: "cloak", 33: "coin", 34: "gem",
    35: "wand", 36: "container", 37: "broken", 38: "familiar",
    45: "container", 51: "misc", 72: "helmet",
}


def build_file_index(mod_dir):
    """Build case-insensitive filename -> path map for a mod folder."""
    idx = {}
    for root, dirs, files in os.walk(mod_dir):
        for fname in files:
            idx[fname.upper()] = os.path.join(root, fname)
    return idx


def build_copy_map(all_files):
    """Build dest_resref -> source_path map from tp2 COPY patterns."""
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


def build_copy_existing_map(all_files):
    """Build dest_resref -> vanilla_source_resref map from COPY_EXISTING patterns.

    COPY_EXISTING ~SW1H01.itm~ ~override/MYSWORD.itm~ creates MYSWORD as a
    derivative of vanilla SW1H01. We use this to inherit the vanilla description
    when the mod doesn't explicitly SAY DESC.
    """
    copy_existing = {}
    pat = re.compile(
        r'COPY_EXISTING\s+~([^~/\\]+)\.itm~\s+~override/([^~]+)\.itm~',
        re.I,
    )
    for fkey, fpath in all_files.items():
        if not fkey.endswith((".TP2", ".TPA", ".TPH")):
            continue
        try:
            content = open(fpath, "r", errors="replace").read()
        except Exception:
            continue
        for m in pat.finditer(content):
            src = m.group(1).upper()
            dst = m.group(2).upper().replace(".ITM", "")
            copy_existing[dst] = src
    return copy_existing


def read_item_type(itm_path):
    """Read the item_type field from an ITM file."""
    try:
        with open(itm_path, "rb") as f:
            d = f.read(0x1E)
        if len(d) < 0x1E or d[0:4] != b"ITM ":
            return None
        itype = struct.unpack("<H", d[0x1C:0x1E])[0]
        return ITEM_CATEGORIES.get(itype, "misc")
    except:
        return None


def read_item_strrefs(itm_path):
    """Read the four name/desc strref fields from an ITM v1 binary.

    Returns dict with keys name1, name2, unid_desc, ident_desc — values may be
    -1 (unset). The mod's .itm files often have these baked in pointing into
    the post-install dialog.tlk; vanilla strrefs (small numbers) can be
    resolved against the vanilla dialog.tlk. Mod-added strrefs (>= vanilla
    string count) cannot be resolved and are returned as-is.
    """
    try:
        with open(itm_path, "rb") as f:
            d = f.read(0x60)
        if len(d) < 0x58 or d[0:4] != b"ITM ":
            return None
        return {
            "name1": struct.unpack("<i", d[0x08:0x0C])[0],
            "name2": struct.unpack("<i", d[0x0C:0x10])[0],
            "unid_desc": struct.unpack("<i", d[0x50:0x54])[0],
            "ident_desc": struct.unpack("<i", d[0x54:0x58])[0],
        }
    except Exception:
        return None


# Lazy-loaded vanilla TLK strref -> text map.
_TLK_CACHE = None


def load_vanilla_tlk():
    """Build a strref -> text dict from the BG2EE dialog.tlk. Cached after first call.

    Strrefs are vanilla-only (mod-installed strrefs aren't in the backup TLK).
    Returns {} if the TLK isn't accessible.
    """
    global _TLK_CACHE
    if _TLK_CACHE is not None:
        return _TLK_CACHE
    tlk_path = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition\lang\en_US\dialog.tlk"
    out = {}
    try:
        with open(tlk_path, "rb") as f:
            sig = f.read(4); ver = f.read(4)
            if sig != b"TLK " or ver != b"V1  ":
                _TLK_CACHE = {}
                return _TLK_CACHE
            f.read(2)  # language ID
            nstrings = struct.unpack("<I", f.read(4))[0]
            str_data_offset = struct.unpack("<I", f.read(4))[0]
            HEADER = 18
            ENTRY_SIZE = 26
            # Read all entry headers in one go for speed.
            f.seek(HEADER)
            entries = f.read(nstrings * ENTRY_SIZE)
            for i in range(nstrings):
                base = i * ENTRY_SIZE
                offset = struct.unpack("<I", entries[base + 18:base + 22])[0]
                length = struct.unpack("<I", entries[base + 22:base + 26])[0]
                if length <= 0 or length > 8000:
                    continue
                f.seek(str_data_offset + offset)
                raw = f.read(length)
                try:
                    out[i] = raw.decode("utf-8", errors="replace").strip()
                except Exception:
                    pass
        print(f"  Loaded {len(out)} vanilla TLK strrefs")
    except Exception as e:
        print(f"  WARNING: vanilla TLK not accessible: {e}")
    _TLK_CACHE = out
    return out


def load_tra_files(mod_dir):
    """Load all English TRA file entries into a {number: text} map."""
    tra_map = {}
    tra_files = []
    for root, dirs, files in os.walk(mod_dir):
        for fname in files:
            if not fname.lower().endswith(".tra"):
                continue
            rel = os.path.relpath(root, mod_dir).lower()
            fp = os.path.join(root, fname)
            # Prioritize English folders
            if "english" in rel or "en_us" in rel or "american" in rel:
                tra_files.insert(0, fp)
            else:
                tra_files.append(fp)

    # Parse TRA: @NNN = ~text~ (possibly multiline). Open UTF-8 with fallback.
    for tf in tra_files:
        content = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                with open(tf, "r", encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, OSError):
                continue
        if content is None:
            continue
        for m in re.finditer(r'@(\d+)\s*=\s*~([^~]*)~', content):
            num = m.group(1)
            text = m.group(2).strip()
            if num not in tra_map and text:
                tra_map[num] = text
    return tra_map


def _parse_tra_file(path):
    """Parse a single TRA file into {num: text}. Supports multiline ~...~ values.

    Opens with UTF-8 explicitly — WeiDU mods almost universally store TRA files
    as UTF-8, and the Windows default (cp1252) mangles characters like en-dash
    (U+2013 → "â€""). Falls back to latin-1 for older/malformed files.
    """
    entries = {}
    content = None
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, OSError):
            continue
    if content is None:
        return entries
    # Greedy-to-closing-tilde match; DOTALL for multi-line strings.
    for m in re.finditer(r'@(\d+)\s*=\s*~([^~]*)~', content, re.DOTALL):
        entries[m.group(1)] = m.group(2).strip()
    return entries


def load_per_item_tras(mod_dir, resrefs):
    """Find per-item TRA files (e.g. a7-am01.tra) keyed by resref.

    Returns {resref_upper: {num: text}} for items that define their strings in a
    TRA file named after the resref (Wares of the Planes, and similar layouts).
    Prefers English translations when multiple language folders exist.
    """
    want = {r.lower() for r in resrefs}
    # Collect candidates grouped by resref → [(lang_prio, path)]
    cands = {}
    for root, dirs, files in os.walk(mod_dir):
        rel = os.path.relpath(root, mod_dir).lower()
        # Language priority: 0 = English, 1 = other
        lang_prio = 0 if ("english" in rel or "en_us" in rel or "american" in rel) else 1
        for fname in files:
            if not fname.lower().endswith(".tra"):
                continue
            base = fname[:-4].lower()
            if base in want:
                cands.setdefault(base, []).append((lang_prio, os.path.join(root, fname)))
    out = {}
    for base, lst in cands.items():
        lst.sort()  # English first
        out[base.upper()] = _parse_tra_file(lst[0][1])
    return out


def build_name_map(all_files, items, tra_map, per_item_tras=None):
    """For each item resref, find its display name and description.

    Tries, in order:
      1. Per-item TRA file (<resref>.tra with @1/@11 = identified name/desc)
      2. SAY NAME2 @NNN pattern in tp2/tph files
      3. SAY NAME2 ~literal~ pattern

    Returns ({resref: name}, {resref: desc}). per_item_tras is {RESREF: {num: text}}.
    """
    per_item_tras = per_item_tras or {}
    # Collect all tp2 content
    all_content = ""
    for fkey, fpath in all_files.items():
        if not fkey.endswith((".TP2", ".TPA", ".TPH")):
            continue
        try:
            all_content += open(fpath, "r", errors="replace").read() + "\n"
        except:
            pass

    # Unresolved WeiDU variable names (e.g. "%blackbow_name%") must never leak
    # into the UI — skip any candidate text that still contains %...%.
    def _usable(text):
        if not text:
            return False
        t = text.strip()
        return bool(t) and "%" not in t

    # Fix double-encoded UTF-8 in a string: bytes like c3 83 c2 bb (Ã»)
    # should be c3 bb (û). Encode as Latin-1 to recover the raw bytes, then
    # re-decode as UTF-8. Silently returns the original if it doesn't work.
    def _fix_double_encoding(s):
        if not s:
            return s
        try:
            return s.encode("latin-1").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            return s

    name_map = {}  # resref -> name
    desc_map = {}  # resref -> desc
    for item in items:
        resref = item["resref"]
        # 1. Per-item TRA file: @1 identified name (fall back to @0)
        tra = per_item_tras.get(resref.upper())
        if tra:
            nm = tra.get("1") or tra.get("0")
            ds = tra.get("11") or tra.get("10")
            if _usable(nm):
                name_map[resref] = nm
            if _usable(ds):
                desc_map[resref] = ds
            if resref in name_map:  # if we have the name, no need to fall through
                continue

        escaped = re.escape(resref)

        # 2. SAY NAME2 @NNN in tp2/tph
        pat = re.compile(escaped + r'.{0,500}?SAY\s+(?:NAME2|0x0?[Cc])\s+@(\d+)', re.I | re.DOTALL)
        m = pat.search(all_content)
        if m and m.group(1) in tra_map and _usable(tra_map[m.group(1)]):
            name_map[resref] = tra_map[m.group(1)]

        # 2b. SAY NAME2 ~literal~ fallback (only if @NNN didn't resolve)
        if resref not in name_map:
            pat = re.compile(escaped + r'.{0,500}?SAY\s+(?:NAME2|0x0?[Cc])\s+~([^~]+)~', re.I | re.DOTALL)
            m = pat.search(all_content)
            if m and _usable(m.group(1)):
                name_map[resref] = m.group(1).strip()

        # 3. SAY DESC / IDENTIFIED_DESC / 0x54 @NNN — identified description.
        # Field aliases: DESC == IDENTIFIED_DESC == 0x54. Falls through to
        # UNIDENTIFIED_DESC (0x50) if identified is missing.
        if resref not in desc_map:
            pat = re.compile(
                escaped + r'.{0,800}?SAY\s+(?:DESC|IDENTIFIED_DESC|0x0?54)\s+@(\d+)',
                re.I | re.DOTALL,
            )
            m = pat.search(all_content)
            if m and m.group(1) in tra_map and _usable(tra_map[m.group(1)]):
                desc_map[resref] = tra_map[m.group(1)]
        if resref not in desc_map:
            pat = re.compile(
                escaped + r'.{0,800}?SAY\s+(?:DESC|IDENTIFIED_DESC|0x0?54)\s+~([^~]+)~',
                re.I | re.DOTALL,
            )
            m = pat.search(all_content)
            if m and _usable(m.group(1)):
                desc_map[resref] = m.group(1).strip()
        if resref not in desc_map:
            # 4. UNIDENTIFIED_DESC @NNN as last-resort description.
            pat = re.compile(
                escaped + r'.{0,800}?SAY\s+(?:UNIDENTIFIED_DESC|0x0?50)\s+@(\d+)',
                re.I | re.DOTALL,
            )
            m = pat.search(all_content)
            if m and m.group(1) in tra_map and _usable(tra_map[m.group(1)]):
                desc_map[resref] = tra_map[m.group(1)]

    # Post-pass: fix double-encoded UTF-8 in resolved names/descs. Some mod TRA
    # files ship broken (e.g. Derats_Archery has "FaerÃ»n" instead of "Faerûn").
    for d in (name_map, desc_map):
        for k in d:
            fixed = _fix_double_encoding(d[k])
            if fixed != d[k]:
                d[k] = fixed

    return name_map, desc_map


def enrich_item_revisions(write_mode):
    """Special handling for Item Revisions: populate modify entries from items.2da."""
    ir_dir = None
    for folder in os.listdir(EXTRACTED):
        if "item revision" in folder.lower():
            candidate = os.path.join(EXTRACTED, folder, "item_rev")
            if os.path.isdir(candidate):
                ir_dir = candidate
                break

    if not ir_dir:
        print("  Item Revisions extracted folder not found, skipping")
        return 0

    # Parse items.2da — the master table of all items IR modifies
    items_2da = os.path.join(ir_dir, "components", "main", "items.2da")
    if not os.path.exists(items_2da):
        print("  items.2da not found")
        return 0

    vanilla_mods = []
    with open(items_2da, "r", errors="replace") as f:
        lines = f.readlines()
    for line in lines[3:]:  # skip 2DA header
        parts = line.split()
        if len(parts) < 10:
            continue
        name = parts[0]
        resref = parts[2].upper()
        eet_flag = parts[8]  # EET column
        if eet_flag == "1":
            vanilla_mods.append(resref)

    if not vanilla_mods:
        print("  No EET items found in items.2da")
        return 0

    print(f"  Item Revisions: {len(vanilla_mods)} vanilla items modified (from items.2da)")

    # Load IR mod file
    ir_path = os.path.join(MODS_DIR, "item_rev.json")
    if not os.path.exists(ir_path):
        print("  item_rev.json not found")
        return 0

    with open(ir_path, "r", encoding="utf-8") as f:
        mod = json.load(f)

    # Add modify entries to component 0
    if "items" not in mod:
        mod["items"] = {}
    entry = mod["items"].get("0", {})
    entry["scope"] = "overhaul"

    # Create modify array
    modify = [[ref, "replace", "Item Revisions overhaul"] for ref in sorted(vanilla_mods)]
    entry["modify"] = modify
    mod["items"]["0"] = entry

    if write_mode:
        with open(ir_path, "w", encoding="utf-8") as f:
            json.dump(mod, f, indent=2, ensure_ascii=False)
        print(f"  Wrote {ir_path} with {len(modify)} modify entries")

    return len(modify)


def main():
    write_mode = "--write" in sys.argv

    with open(REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    # Vanilla item index for COPY_EXISTING description fallback.
    vanilla_items_path = os.path.join(PROJ, "data", "items-vanilla.json")
    vanilla_items = {}
    try:
        with open(vanilla_items_path, "r", encoding="utf-8") as f:
            vanilla_items = json.load(f)
    except Exception as e:
        print(f"  WARNING: could not load vanilla items for fallback: {e}")

    print("Enriching item data across mods...\n")

    total_items = 0
    types_fixed = 0
    names_found = 0
    mods_updated = 0

    for tp2, data in sorted(report.items()):
        if data.get("status") != "found" or not data.get("dir"):
            continue
        mod_dir = data["dir"]
        scan_items = data.get("items", [])
        if not scan_items:
            continue

        # Load the mod detail file
        # Find it by matching tp2 ID
        mod_path = None
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
        copy_existing_map = build_copy_existing_map(all_files)
        tra_map = load_tra_files(mod_dir)
        per_item_tras = load_per_item_tras(mod_dir, [it["resref"] for it in scan_items])
        name_map, desc_map = build_name_map(all_files, scan_items, tra_map, per_item_tras)
        # Fallback: items created via COPY_EXISTING inherit name+desc from the
        # vanilla source unless overridden by a SAY in the mod's tp2.
        for dst, src in copy_existing_map.items():
            vsrc = vanilla_items.get(src)
            if not vsrc:
                continue
            if dst not in name_map and vsrc.get("n"):
                name_map[dst] = vsrc["n"]
            if dst not in desc_map and vsrc.get("desc"):
                desc_map[dst] = vsrc["desc"]

        mod_changed = False

        for ci_str, entry in mod["items"].items():
            if "new" not in entry:
                continue
            for arr in entry["new"]:
                resref = arr[0]
                total_items += 1

                # Ensure array has 4 elements
                while len(arr) < 4:
                    arr.append("")

                # Fix type from .itm binary
                itm_path = all_files.get(resref + ".ITM") or copy_map.get(resref)
                if itm_path:
                    real_type = read_item_type(itm_path)
                    if real_type and real_type != arr[1]:
                        arr[1] = real_type
                        types_fixed += 1
                        mod_changed = True

                # Fix name from TRA. Overwrite if missing, mojibaked, or a stale
                # unresolved WeiDU variable (e.g. "%blackbow_name%").
                # Mojibake pattern: any `Ã<X>` sequence (UTF-8 as cp1252) or the
                # `â€<X>` triplet for codepoints U+2000-U+27FF (en-dash etc).
                _MOJIBAKE_RX = re.compile(r"Ã[\x80-\xbf\u00a0-\u00bf]|â€[\x80-\xbf\u20ac\u201a-\u2122]|Â[\xa0-\xbf]")
                def _is_mojibaked(s):
                    return bool(s) and bool(_MOJIBAKE_RX.search(s))
                def _is_stale(s):
                    # Unresolved %var% or mojibake — either way, overwrite.
                    return _is_mojibaked(s) or (bool(s) and "%" in s)
                if resref in name_map and (not arr[2] or arr[2] == "" or _is_stale(arr[2])):
                    if arr[2] != name_map[resref]:
                        arr[2] = name_map[resref]
                        names_found += 1
                        mod_changed = True
                elif arr[2] and _is_stale(arr[2]):
                    # Stale value with no replacement available — clear it so the
                    # UI falls back to the resref and the empty-shell detector
                    # (which flags items lacking both name and desc as internal).
                    arr[2] = ""
                    mod_changed = True

                # Fix description from per-item TRA (same overwrite logic).
                if resref in desc_map and (not arr[3] or arr[3] == "" or _is_stale(arr[3])):
                    if arr[3] != desc_map[resref]:
                        arr[3] = desc_map[resref]
                        mod_changed = True
                elif arr[3] and _is_stale(arr[3]):
                    arr[3] = ""
                    mod_changed = True

                # Last-resort: read the .itm binary's strref fields and look
                # them up in the vanilla dialog.tlk. Mod-baked items (DGITEMS,
                # ruad, Derats) ship strrefs already pointing into vanilla TLK
                # for shared text like generic dart/sword descriptions.
                if itm_path and (not arr[2] or not arr[3]):
                    sr = read_item_strrefs(itm_path)
                    if sr:
                        tlk = load_vanilla_tlk()
                        if not arr[2] and sr["name2"] >= 0:
                            t = tlk.get(sr["name2"])
                            if t:
                                arr[2] = t
                                names_found += 1
                                mod_changed = True
                        if not arr[3] and sr["ident_desc"] >= 0:
                            t = tlk.get(sr["ident_desc"])
                            if t:
                                arr[3] = t
                                mod_changed = True
                        if not arr[3] and sr["unid_desc"] >= 0:
                            t = tlk.get(sr["unid_desc"])
                            if t:
                                arr[3] = t
                                mod_changed = True

            # Recalculate itC
            itC = {}
            for arr in entry["new"]:
                t = arr[1] if len(arr) > 1 else "misc"
                itC[t] = itC.get(t, 0) + 1

            # Update component itC
            co = mod.get("co", [])
            ci = int(ci_str) if ci_str.isdigit() else -1
            if 0 <= ci < len(co):
                if co[ci].get("itC") != itC:
                    co[ci]["itC"] = itC
                    mod_changed = True

        if mod_changed:
            mods_updated += 1
            if write_mode:
                with open(mod_path, "w", encoding="utf-8") as f:
                    json.dump(mod, f, indent=2, ensure_ascii=False)

    print(f"Results:")
    print(f"  Total items processed: {total_items}")
    print(f"  Types fixed: {types_fixed}")
    print(f"  Names resolved: {names_found}")
    print(f"  Still missing names: {total_items - names_found}")
    print(f"  Mods updated: {mods_updated}")

    # Item Revisions special handling
    print(f"\nItem Revisions modify tracking:")
    ir_count = enrich_item_revisions(write_mode)

    if not write_mode:
        print(f"\nDry run. Use --write to update mod files.")


if __name__ == "__main__":
    main()
