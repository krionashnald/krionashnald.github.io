"""Quick drift audit: compare DB co[] vs v18 tp2 for high-priority mods."""
import re
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cat = json.loads((ROOT / 'data/mods/_catalog.json').read_text(encoding='utf-8'))
EXTRACTED = Path('F:/BGMods/Extracted')

high_priority = [
    'stratagems', '1pp', 'item_rev', 'spell_rev', 'aTweaks', 'BG1NPC',
    'arestorationp', 'TomeAndBlood', 'Faiths_and_Powers', 'DeitiesOfFaerun',
    'themed_tweaks', 'tb#tweaks', 'ArtisansKitpack', 'bgqe', 'ub',
    'd5_random_tweaks', 'iwdification', 'Scales_of_Balance', 'might_and_guile',
    'ascension', 'RR', 'tnt', 'EET_Tweaks',
]


def find_tp2(mod_stem):
    for patt in [f'setup-{mod_stem}.tp2', f'{mod_stem}.tp2']:
        hits = list(EXTRACTED.rglob(patt))
        if hits:
            # Filter out fresh/patches dirs
            hits = [
                h for h in hits
                if 'fresh' not in str(h).lower()
                and '\\patches\\files' not in str(h).lower()
                and '/patches/files' not in str(h).lower()
            ]
            if hits:
                return hits[0]
    return None


def parse_tp2_components(tp2_path):
    """Only count component BEGINs: BEGIN at column 0 followed by @<num> or ~<name>~.
    Excludes bare BEGIN inside DECOMPILE_AND_PATCH / ACTION_IF / OUTER_FOR blocks."""
    txt = tp2_path.read_text(encoding='utf-8', errors='replace')
    lines = txt.split('\n')
    begin_re = re.compile(r'^\s*BEGIN\s+(?:@(\d+)|~([^~]+)~|"([^"]+)")')
    comps = []
    order = 0
    i = 0
    while i < len(lines):
        m = begin_re.match(lines[i])
        if not m:
            i += 1
            continue
        bid = int(m.group(1)) if m.group(1) else None
        name_inline = m.group(2)
        cn = None
        deprecated = 'DEPRECATED' in lines[i]
        for j in range(i, min(i + 16, len(lines))):
            if j > i and begin_re.match(lines[j]):
                break
            des_m = re.search(r'\bDESIGNATED\s+(\d+)', lines[j])
            if des_m and cn is None:
                cn = int(des_m.group(1))
            if 'DEPRECATED' in lines[j]:
                deprecated = True
        if cn is None:
            cn = order
        comps.append({'cn': cn, 'begin_id': bid, 'name_inline': name_inline, 'deprecated': deprecated})
        order += 1
        i += 1
    return comps


def find_mod_file(stem):
    for mid, fn in cat.items():
        if fn.lower().replace('.json', '') == stem.lower():
            return mid, fn
    return None, None


drift_by_mod = {}
for stem in high_priority:
    mid, fn = find_mod_file(stem)
    if not mid:
        continue
    db = json.loads((ROOT / f'data/mods/{fn}').read_text(encoding='utf-8'))
    wf = db.get('co', [{}])[0].get('wf', stem) if db.get('co') else stem
    tp2 = find_tp2(stem) or find_tp2(wf)
    if not tp2:
        continue
    tp2_comps = parse_tp2_components(tp2)
    tp2_cns = {c['cn'] for c in tp2_comps}
    db_cns = {c.get('cn') for c in db.get('co', [])}
    ghost = db_cns - tp2_cns
    new = tp2_cns - db_cns
    if ghost or new:
        drift_by_mod[stem] = {
            'db_total': len(db.get('co', [])),
            'tp2_total': len(tp2_comps),
            'ghost': sorted(ghost)[:15],
            'new_in_tp2': sorted(new)[:15],
            'tp2_path': str(tp2),
        }

print(f"\n=== DRIFT SUMMARY ({len(drift_by_mod)}/{len(high_priority)} mods with issues) ===\n")
for stem, info in drift_by_mod.items():
    print(f"{stem}: db={info['db_total']} comps, tp2={info['tp2_total']} comps")
    if info['ghost']:
        print(f"  ghost (in DB, not in v18 tp2): {info['ghost']}")
    if info['new_in_tp2']:
        print(f"  new (in tp2, not in DB): {info['new_in_tp2']}")
    print()
