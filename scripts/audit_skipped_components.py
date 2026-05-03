#!/usr/bin/env python3
"""Audit skipped components against tp2 sources and find external conflicts."""
import json, os, re, sys, glob
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXTRACTED = Path(r"F:/BGMods/Extracted")

# Target mods to audit
TARGETS = {
    "dw_talents": {
        "json": REPO / "data/mods/dw_talents.json",
        "tp2": EXTRACTED / "Talents Of Faerun/dw_talents/dw_talents.tp2",
        "cns": [40000, 40100, 20000, 40190, 40160, 40150, 60100, 50600, 55000,
                80150, 80160, 80500, 81000, 81010, 81020, 81030, 81100, 81200,
                90000, 90100],
    },
    "a7-improved_shamanic_dance": {
        "json": REPO / "data/mods/a7-improved_shamanic_dance.json",
        "tp2": EXTRACTED / "A7 Improved Shamanic Dance/A7#ImprovedShamanicDance/A7#ImprovedShamanicDance.tp2",
        "cns": [0, 10, 20, 30, 40],
    },
    "cdtweaks": {
        "json": REPO / "data/mods/cdtweaks.json",
        "tp2": EXTRACTED / "Tweaks Anthology/cdtweaks/setup-cdtweaks.tp2",
        "cns": [30, 40, 60, 90, 110, 130, 150, 160, 181, 220, 240, 1020, 1030,
                1060, 1070, 1075, 1101, 1254, 1255, 1330, 1340, 1341, 1343,
                1344, 1345, 1354, 2010, 2020, 2035, 2080, 2120, 2140, 2164,
                2211, 2320, 2330, 2530, 2550, 2552, 2560, 2620, 2650, 2680,
                2693, 2750, 3013, 3040, 3071, 3081, 3090, 3103, 3111, 3141,
                3175, 3197, 3261, 3292, 3342, 3350, 3352, 3355, 3357, 3390,
                3410, 3411, 3430, 3500, 3520, 4020],
    },
    "ua": {
        "json": REPO / "data/mods/UA.json",
        "tp2": EXTRACTED / "Unique Artifacts/ua/ua.tp2",
        "cns": [0, 1, 2, 3],
    },
    "stratagems": {
        "json": REPO / "data/mods/stratagems.json",
        "tp2": EXTRACTED / "Sword Coast Stratagems/stratagems/setup-stratagems.tp2",
        "cns": [18, 23, 24, 4135, 4140, 4145, 4150, 4160, 4170],
    },
    "SkitiaRomanceTweak": {
        "json": REPO / "data/mods/SkitiaRomanceTweak.json",
        "tp2": EXTRACTED / "Skitia Romance Tweak/SkitiaRomanceTweak/Setup-SkitiaRomanceTweak.tp2",
        "cns": [0],
    },
}

# Mod prefix (tp2 filename without setup-/.tp2) → our DB mod key
PREFIX_TO_DB = {
    "dw_talents": "dw_talents",
    "a7#improvedshamanicdance": "a7-improved_shamanic_dance",
    "cdtweaks": "cdtweaks",
    "ua": "ua",
    "stratagems": "stratagems",
    "skitiaromancetweak": "SkitiaRomanceTweak",
}


def read_tp2(path):
    """Read tp2 file handling multiple encodings."""
    for enc in ["utf-8", "utf-16", "cp1252", "latin-1"]:
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, "rb") as f:
        return f.read().decode("latin-1", errors="replace")


def parse_tra_strings(tp2_path):
    """Parse tra files to resolve @N refs. Returns dict of {n: string}.

    Priority order:
    1. The first tra path declared in LANGUAGE directive of the tp2
    2. Fallback: only setup.tra in english/american/en_us dirs
    """
    mod_dir = tp2_path.parent
    tra = {}
    tp2_txt = read_tp2(tp2_path)

    # Extract LANGUAGE directives — find first tra path (english preferred)
    lang_block_re = re.compile(
        r'LANGUAGE\s+~?"?([^~"\n]+)"?~?\s*~?"?([^~"\n]+)"?~?\s*~([^~]+\.tra)~',
        re.IGNORECASE,
    )
    lang_paths = []
    for m in lang_block_re.finditer(tp2_txt):
        lang_name = m.group(1).strip().lower()
        tra_rel = m.group(3)
        if "english" in lang_name or "american" in lang_name:
            lang_paths.insert(0, tra_rel)
        else:
            lang_paths.append(tra_rel)

    # Substitute %MOD_FOLDER% with the mod folder name
    mod_folder_name = mod_dir.name
    resolved_paths = []
    for p in lang_paths:
        p2 = p.replace("%MOD_FOLDER%", mod_folder_name)
        # Try both relative to mod_dir.parent and mod_dir
        candidates = [
            mod_dir.parent / p2,
            mod_dir / p2,
        ]
        # Also, some tp2s use path starting with mod_folder, e.g. "dw_talents/lang/english/setup.tra"
        for c in candidates:
            if c.exists():
                resolved_paths.append(c)
                break

    # Prioritise canonical setup/weidu/game tra names (authoritative for component names)
    priority_names = ["weidu.tra", "setup.tra", "game.tra"]
    for pat in ["**/english/*.tra", "**/en_us/*.tra", "**/american/*.tra",
                "**/languages/english/*.tra", "**/lang/english/*.tra",
                "**/language/english/*.tra"]:
        for f in mod_dir.glob(pat):
            if f not in resolved_paths:
                resolved_paths.append(f)
    # Reorder: priority names first
    resolved_paths.sort(key=lambda p: (p.name.lower() not in priority_names, p.name.lower()))

    # If nothing found, fall back to a conservative glob for setup.tra only
    if not resolved_paths:
        for pat in ["**/english/setup.tra", "**/en_us/setup.tra",
                    "**/american/setup.tra", "**/english/*.tra"]:
            for f in mod_dir.glob(pat):
                resolved_paths.append(f)
                break
            if resolved_paths:
                break

    for f in resolved_paths:
        try:
            txt = read_tp2(f)
        except Exception:
            continue
        for m in re.finditer(r"@(\d+)\s*=\s*~([^~]*)~", txt):
            tra.setdefault(int(m.group(1)), m.group(2))
        for m in re.finditer(r'@(\d+)\s*=\s*"([^"]*)"', txt):
            tra.setdefault(int(m.group(1)), m.group(2))
    return tra


def parse_tp2_components(tp2_path):
    """Return dict {cn: designated_name}."""
    txt = read_tp2(tp2_path)
    tra = parse_tra_strings(tp2_path)
    components = {}

    # Remove /* */ block comments
    txt_clean = re.sub(r"/\*.*?\*/", "", txt, flags=re.DOTALL)
    # Remove //-line comments
    txt_clean = re.sub(r"//[^\n]*", "", txt_clean)

    # Match BEGIN followed by a designated string and optional DESIGNATED/NUMBER
    # Patterns:
    #   BEGIN ~Name~ DESIGNATED NNNN
    #   BEGIN @NNN DESIGNATED NNNN
    #   BEGIN ~Name~ NNNN    (legacy)
    # We iterate and track; also explicit DESIGNATED separately.

    # Approach: find each BEGIN + payload up to NUMBER/DESIGNATED or next BEGIN.
    # Simpler: find BEGIN ~...~ DESIGNATED N  OR  BEGIN @N DESIGNATED N
    # and also BEGIN ~...~ ... NUMBER N
    pat = re.compile(
        r"BEGIN\s+"
        r"(~(?P<str>[^~]*)~|@(?P<tra>\d+))"
        r"[^\n]*?"
        r"(?:DESIGNATED\s+(?P<des>\d+)|NUMBER\s+(?P<num>\d+))?",
        re.IGNORECASE | re.DOTALL,
    )

    # However, DESIGNATED/NUMBER may appear on a following line. Use line-level
    # extraction: iterate BEGIN statements, then look ahead within 20 lines.
    lines = txt_clean.splitlines()
    begin_re = re.compile(r"\bBEGIN\s+(?:~([^~]*)~|@(\d+))", re.IGNORECASE)
    des_re = re.compile(r"\bDESIGNATED\s+(\d+)", re.IGNORECASE)
    num_re = re.compile(r"\bNUMBER\s+(\d+)", re.IGNORECASE)
    group_re = re.compile(r"\bGROUP\b", re.IGNORECASE)

    auto_cn = 0  # for mods that omit DESIGNATED/NUMBER (implicit sequential)
    for i, line in enumerate(lines):
        bm = begin_re.search(line)
        if not bm:
            continue
        name_raw = bm.group(1)
        name_tra = bm.group(2)
        if name_raw is not None:
            name = name_raw
        else:
            name = tra.get(int(name_tra), f"@{name_tra}")
        # Look for DESIGNATED/NUMBER on current + next 20 lines (until next BEGIN)
        cn = None
        for j in range(i, min(i + 20, len(lines))):
            if j > i and begin_re.search(lines[j]):
                break
            dm = des_re.search(lines[j])
            if dm:
                cn = int(dm.group(1))
                break
            nm = num_re.search(lines[j])
            if nm:
                cn = int(nm.group(1))
                break
        if cn is None:
            cn = auto_cn
            auto_cn += 1
        else:
            auto_cn = cn + 1
        components[cn] = name
    return components, txt


def find_forbid_require_refs(tp2_path, target_prefix):
    """Search tp2 for FORBID_COMPONENT / REQUIRE_COMPONENT referencing target_prefix."""
    try:
        txt = read_tp2(tp2_path)
    except Exception:
        return []
    hits = []
    # Normalize prefix search (case insensitive, match tp2 filename without setup- or .tp2)
    # Look for patterns like: FORBID_COMPONENT ~<prefix>/...~ <cn> or FORBID_COMPONENT ~<prefix>.tp2~ <cn>
    # Also FORBID_FILE and REQUIRE_COMPONENT same format
    pat = re.compile(
        r"\b(FORBID_COMPONENT|REQUIRE_COMPONENT)\s+~([^~]+)~\s+(\d+)"
        r"(?:\s+(?:~([^~]*)~|@(\d+)))?",
        re.IGNORECASE,
    )
    target_lo = target_prefix.lower()
    # match <prefix>.tp2 or <prefix>/... (word boundary to avoid partial matches)
    target_re = re.compile(
        r"(?:^|[\\/])" + re.escape(target_lo) + r"(?:[\\/]|\.tp2$|\.tp2[\\/])",
        re.IGNORECASE,
    )
    # Simpler: check if basename without .tp2 == target_lo
    for m in pat.finditer(txt):
        kind = m.group(1).upper()
        path_str = m.group(2).lower()
        cn = int(m.group(3))
        # Normalise path
        base = path_str.replace("\\", "/").split("/")[-1]
        if base.endswith(".tp2"):
            base = base[:-4]
        if base == target_lo:
            hits.append({
                "kind": kind,
                "target_path": m.group(2),
                "target_cn": cn,
                "msg_raw": m.group(4) or (f"@{m.group(5)}" if m.group(5) else ""),
            })
    return hits


def main():
    print("=" * 80)
    print("STEP 1: Parse tp2 components for target mods")
    print("=" * 80)

    # First compute name mismatches
    mismatches = {}
    tp2_components = {}
    for key, info in TARGETS.items():
        json_path = info["json"]
        tp2_path = info["tp2"]
        if not tp2_path.exists():
            print(f"[MISSING TP2] {key}: {tp2_path}")
            continue
        comps, _ = parse_tp2_components(tp2_path)
        tp2_components[key] = comps
        with open(json_path, "r", encoding="utf-8") as f:
            db = json.load(f)
        db_co = db.get("co", [])
        db_map = {c.get("cn"): c.get("n", "") for c in db_co if "cn" in c}
        mis = []
        for cn in info["cns"]:
            tp2_name = comps.get(cn)
            db_name = db_map.get(cn)
            if tp2_name is None:
                mis.append((cn, db_name, None, "NOT_IN_TP2"))
            elif db_name is None:
                mis.append((cn, None, tp2_name, "NOT_IN_DB"))
            else:
                # Compare after normalization
                def norm(s):
                    return re.sub(r"\s+", " ", s.strip().lower())
                if norm(tp2_name) != norm(db_name):
                    mis.append((cn, db_name, tp2_name, "MISMATCH"))
        mismatches[key] = mis
        print(f"\n--- {key} ({len(info['cns'])} checked) ---")
        if not mis:
            print("  All names match tp2")
        else:
            for cn, dbn, tp2n, status in mis:
                print(f"  #{cn} [{status}]")
                print(f"    DB:  {dbn!r}")
                print(f"    TP2: {tp2n!r}")

    print("\n" + "=" * 80)
    print("STEP 2: Find #1 'Fee required' component")
    print("=" * 80)
    # Scan all extracted tp2s for cn:1 named like "Fee required"
    fee_hits = []
    for tp2 in EXTRACTED.rglob("*.tp2"):
        try:
            comps, _ = parse_tp2_components(tp2)
        except Exception:
            continue
        n1 = comps.get(1, "")
        if "fee" in n1.lower():
            fee_hits.append((tp2, n1))
    for tp2, n in fee_hits:
        print(f"  {tp2.parent.name}/{tp2.name}  #1={n!r}")

    print("\n" + "=" * 80)
    print("STEP 3: Find FORBID/REQUIRE refs to target mods")
    print("=" * 80)
    # Target prefix strings to search (tp2 filenames / mod dirs)
    target_prefixes = {
        "dw_talents": "dw_talents",
        "a7-improved_shamanic_dance": "a7#improvedshamanicdance",
        "cdtweaks": "cdtweaks",
        "ua": "ua",
        "stratagems": "stratagems",
        "SkitiaRomanceTweak": "skitiaromancetweak",
    }
    refs = {k: [] for k in target_prefixes}
    all_tp2s = list(EXTRACTED.rglob("*.tp2"))
    print(f"Scanning {len(all_tp2s)} tp2 files...")
    for tp2 in all_tp2s:
        for key, prefix in target_prefixes.items():
            hits = find_forbid_require_refs(tp2, prefix)
            if hits:
                # Record source mod
                refs[key].append((tp2, hits))
    for key, entries in refs.items():
        print(f"\n--- References to {key} ---")
        for tp2, hits in entries:
            src = tp2.stem
            # Skip self-references (mod forbidding its own components)
            if src.lower().replace("setup-", "") == target_prefixes[key]:
                continue
            print(f"  {tp2.relative_to(EXTRACTED)}  (from {src})")
            for h in hits:
                in_skipped = h["target_cn"] in TARGETS[key]["cns"]
                star = " *SKIPPED*" if in_skipped else ""
                print(f"    {h['kind']} target=#{h['target_cn']} ({h['target_path']}) msg={h['msg_raw']!r}{star}")

    # Save full ref dump for conflict-entry construction
    out = {}
    for key, entries in refs.items():
        out[key] = []
        for tp2, hits in entries:
            src = tp2.stem
            if src.lower().replace("setup-", "") == target_prefixes[key]:
                continue
            out[key].append({
                "src_tp2": str(tp2.relative_to(EXTRACTED)),
                "src_stem": src,
                "hits": hits,
            })
    with open(REPO / "scripts/audit_skipped_components.result.json", "w", encoding="utf-8") as f:
        json.dump({
            "mismatches": {k: [list(x) for x in v] for k, v in mismatches.items()},
            "fee_hits": [(str(p), n) for p, n in fee_hits],
            "refs": out,
        }, f, indent=2)
    print(f"\nResults saved to {REPO / 'scripts/audit_skipped_components.result.json'}")


if __name__ == "__main__":
    main()
