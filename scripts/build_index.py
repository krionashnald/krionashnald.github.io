#!/usr/bin/env python3
"""
Build mods-index.json purely from per-mod detail files.

All fields (metadata, author, URL, summary, tags, etc.) live in the detail
files under data/mods/.  This script reads them and produces a lightweight
index for fast browser-side loading.

Usage:
    python scripts/build_index.py          # preview changes
    python scripts/build_index.py --write  # write mods-index.json
"""

import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
MODS_DIR = os.path.join(DATA_DIR, 'mods')
INDEX_PATH = os.path.join(DATA_DIR, 'mods-index.json')
CATALOG_PATH = os.path.join(MODS_DIR, '_catalog.json')

# Scalar fields copied verbatim from the detail file into the index entry.
# All are optional — only included if present and non-empty.
SCALAR_FIELDS = [
    'i', 't', 'n', 'c', 'cats', 'ord', 'lang', 'langs', 'pfx',
    'u', 'a', 'v', 'sum', 'tags', 'ph', 'ios', 's', 'gh',
]


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_index_entry(detail):
    """Build one index entry entirely from a detail file."""
    entry = {}

    for f in SCALAR_FIELDS:
        if f not in detail:
            continue
        val = detail[f]
        # Skip empty strings for 's' (stale subcategory)
        if f == 's' and val == '':
            continue
        entry[f] = val

    # Build component arrays from detail co[]
    co = detail.get('co', [])
    entry['cc'] = len(co)

    if co:
        entry['coNames'] = [c.get('n', '') for c in co]

        # Only include arrays that have non-default values
        g_arr = [c.get('g') for c in co]
        if any(g is not None for g in g_arr):
            entry['coG'] = g_arr

        x_arr = [c.get('x') for c in co]
        if any(x is not None for x in x_arr):
            entry['coX'] = x_arr

        tg_arr = [c.get('tg') for c in co]
        if any(tg is not None for tg in tg_arr):
            entry['coTG'] = tg_arr

        wc_arr = [c.get('cn') for c in co]
        entry['coWC'] = wc_arr

        wf_arr = [c.get('wf') for c in co]
        entry['coWF'] = wf_arr

        k_arr = [c.get('k', 0) for c in co]
        if any(k != 0 for k in k_arr):
            entry['coK'] = k_arr

        sp_arr = [c.get('sp', 0) for c in co]
        if any(sp != 0 for sp in sp_arr):
            entry['coSP'] = sp_arr

        spLv_arr = [c.get('spLv') for c in co]
        if any(lv is not None for lv in spLv_arr):
            entry['coSpLv'] = spLv_arr

        kC_arr = [c.get('kC') for c in co]
        if any(kc is not None for kc in kC_arr):
            entry['coKC'] = kC_arr

        ss_arr = [c.get('ss', 0) for c in co]
        if any(ss != 0 for ss in ss_arr):
            entry['coSS'] = ss_arr

        it_arr = [c.get('it', 0) for c in co]
        if any(it != 0 for it in it_arr):
            entry['coIT'] = it_arr

        itC_arr = [c.get('itC') for c in co]
        if any(itc is not None for itc in itC_arr):
            entry['coITC'] = itC_arr

        # Games: per-component array + mod-level union
        games_arr = [c.get('games') for c in co]
        if any(g is not None for g in games_arr):
            entry['coGames'] = games_arr
            # Mod-level union: only compute when every component has an
            # explicit games list. Any universal component makes the mod
            # universal (no mod-level games field).
            if all(g is not None for g in games_arr):
                union = set()
                for g in games_arr:
                    union.update(g)
                if union:
                    entry['games'] = sorted(union)

        # Subcomponent + Group headers: per-component parallel arrays
        scn_arr = [c.get('scn') for c in co]
        grn_arr = [c.get('grn') for c in co]
        if any(s is not None for s in scn_arr):
            entry['coScn'] = scn_arr
        if any(g is not None for g in grn_arr):
            entry['coGrn'] = grn_arr

        # Cats: auto-compute from mod.c + per-component cat overrides.
        # Only set when mod spans multiple categories.
        cats_set = set()
        if detail.get('c'):
            cats_set.add(detail['c'])
        for c in co:
            if c.get('cat'):
                cats_set.add(c['cat'])
        if len(cats_set) > 1:
            # Preserve mod.c as first, others sorted
            rest = sorted(x for x in cats_set if x != detail.get('c'))
            entry['cats'] = [detail['c']] + rest
        else:
            entry.pop('cats', None)

    return entry


def main():
    write_mode = '--write' in sys.argv

    catalog = load_json(CATALOG_PATH)

    # Load old index only for change reporting
    old_index = load_json(INDEX_PATH) if os.path.exists(INDEX_PATH) else []
    old_by_id = {m['i']: m for m in old_index}

    new_index = []
    changes = []
    errors = []
    seen_mod_ids = set()

    # Deduplicate: if multiple catalog IDs point to same file, use the one
    # whose ID matches the detail file's "i" field. Skip others.
    seen_files = {}
    for mod_id_str, filename in sorted(catalog.items(), key=lambda x: int(x[0])):
        if filename not in seen_files:
            seen_files[filename] = []
        seen_files[filename].append(int(mod_id_str))

    for mod_id_str, filename in sorted(catalog.items(), key=lambda x: int(x[0])):
        mod_id = int(mod_id_str)
        detail_path = os.path.join(MODS_DIR, filename)

        if not os.path.exists(detail_path):
            errors.append(f"  MISSING: {filename} (id={mod_id})")
            continue

        try:
            detail = load_json(detail_path)
        except Exception as e:
            errors.append(f"  ERROR: {filename}: {e}")
            continue

        # Skip duplicate catalog entries (multiple IDs -> same file)
        file_ids = seen_files.get(filename, [])
        if len(file_ids) > 1 and detail.get('i') != mod_id:
            continue

        # Skip if we've already processed this mod ID (dedup by final ID)
        detail_id = detail.get('i', mod_id)
        if detail_id in seen_mod_ids:
            continue
        seen_mod_ids.add(detail_id)

        entry = build_index_entry(detail)
        new_index.append(entry)

        # Report changes
        existing = old_by_id.get(detail_id) or old_by_id.get(mod_id)
        if existing:
            for field in ['c', 'ord', 'cc', 'n']:
                old_val = existing.get(field)
                new_val = entry.get(field)
                if old_val != new_val:
                    changes.append(f"  {detail.get('t','?')} (i={mod_id}): {field} {old_val!r} -> {new_val!r}")
        else:
            changes.append(f"  NEW: {detail.get('t','?')} (i={mod_id})")

    # Sort by category order then ord within category
    CL_ORDER = [
        'PRE EET BGEE MODS', 'EET STARTS HERE', 'ENGINE', 'INTERFACE',
        'GRAPHICS', 'RESTORATIONS',
        'QUEST MODS BG1', 'QUEST MODS BG2', 'QUEST MODS ToB',
        'NEW NPC MODS', 'NPC EXPANSIONS', 'NPC CROSSMOD', 'CREATURE MODS',
        'EXPERIENCE TWEAKS', 'ITEM ADDITION MODS', 'SPELL MODS',
        'KIT & CLASS MODS', 'PRE-TACTICAL TWEAKS', 'TACTICAL MODS',
        'POST-TACTICAL TWEAKS', 'NPC CUSTOMIZATION', 'POST-TACTICAL QUESTS',
        'MUSIC & AUDIO', 'PORTRAITS', 'EET FINALIZATION', 'POST EET'
    ]
    cat_idx = {c: i for i, c in enumerate(CL_ORDER)}
    new_index.sort(key=lambda m: (cat_idx.get(m.get('c', ''), 999), m.get('ord', 999), m.get('i', 0)))

    # Report
    print(f"Catalog entries: {len(catalog)}")
    print(f"Index entries: {len(new_index)} (was {len(old_index)})")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(e)

    if changes:
        print(f"\nChanges ({len(changes)}):")
        for c in changes:
            print(c)
    else:
        print("\nNo changes detected.")

    if write_mode:
        with open(INDEX_PATH, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(new_index, f, indent=2, ensure_ascii=False)
        print(f"\nWrote {INDEX_PATH}")
    else:
        print("\nDry run. Use --write to update mods-index.json")


if __name__ == '__main__':
    main()
