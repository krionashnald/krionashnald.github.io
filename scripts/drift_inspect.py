"""One-shot drift inspector for a given mod.

Usage:  python scripts/drift_inspect.py <mod_stem>
Prints:
  - tp2 path, tra dir
  - Full side-by-side cn comparison (db vs tp2)
  - Context (tp2 lines) for each new and ghost cn
  - Existing DB flags (dep, gone, g, tg, etc.)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
if "audit_tp2_drift" in sys.modules:
    del sys.modules["audit_tp2_drift"]
from audit_tp2_drift import find_tra_dir, load_tra_map, parse_tp2_components  # noqa

ROOT = Path(__file__).resolve().parents[1]
EXTRACTED = Path("F:/BGMods/Extracted")


def build_index():
    idx = {}
    for tp2 in EXTRACTED.rglob("*.tp2"):
        sp = str(tp2).replace("\\", "/").lower()
        if "patches/files" in sp or "fresh" in sp:
            continue
        stem = tp2.stem.lower()
        if stem.startswith("setup-"):
            stem = stem[6:]
        if stem not in idx:
            idx[stem] = tp2
    return idx


def main():
    if len(sys.argv) < 2:
        print("Usage: drift_inspect.py <mod_stem>", file=sys.stderr)
        sys.exit(1)
    stem = sys.argv[1]
    p = ROOT / "data/mods" / f"{stem}.json"
    if not p.exists():
        # Case-insensitive search
        for candidate in (ROOT / "data/mods").glob("*.json"):
            if candidate.stem.lower() == stem.lower():
                p = candidate
                break
    if not p.exists():
        print(f"Mod file not found: {stem}", file=sys.stderr)
        sys.exit(1)

    d = json.loads(p.read_text(encoding="utf-8"))
    co = d.get("co", [])
    wf = (co[0].get("wf") if co else None) or d.get("t") or p.stem

    idx = build_index()
    tp2 = idx.get(wf.lower()) or idx.get(p.stem.lower()) or idx.get(d.get("t", "").lower())
    if not tp2:
        print(f"No tp2 found for wf={wf!r} or stem={p.stem!r}", file=sys.stderr)
        sys.exit(2)

    tra_dir = find_tra_dir(tp2)
    tra = load_tra_map(tra_dir, tp2)
    tp2_comps = parse_tp2_components(tp2, tra)

    db_cns = {c["cn"] for c in co if c.get("cn") is not None}
    tp2_cns = set(tp2_comps.keys())
    new = sorted(tp2_cns - db_cns)
    ghost = sorted(db_cns - tp2_cns)

    print(f"=== {p.stem} ===")
    print(f"tp2: {tp2}")
    print(f"tra_dir: {tra_dir} ({len(tra)} entries)")
    print(f"DB: {len(db_cns)} comps | v18 tp2: {len(tp2_comps)} comps")
    print(f"New: {new}")
    print(f"Ghost: {ghost}\n")

    print(f"{'cn':>5}  {'DB name':45}  {'tp2 name':45}  {'flags'}")
    print("-" * 115)
    all_cns = sorted(tp2_cns | db_cns)
    for cn in all_cns:
        db_entry = next((c for c in co if c.get("cn") == cn), None)
        db_n = (db_entry.get("n", "") if db_entry else "").strip()[:45]
        tp2_n = tp2_comps.get(cn, "")[:45]
        flags = []
        if db_entry:
            if db_entry.get("dep"):
                flags.append("dep")
            if db_entry.get("gone"):
                flags.append("gone")
            if db_entry.get("g"):
                flags.append(f"g={db_entry['g']}")
            if db_entry.get("tg"):
                flags.append(f"tg={db_entry['tg']}")
        marker = "[NEW]" if cn in new else ("[GHOST]" if cn in ghost else "")
        print(f"{cn:>5}  {db_n:45}  {tp2_n:45}  {marker}{' ' + ' '.join(flags) if flags else ''}")

    # Context for each drift case
    lines = tp2.read_text(encoding="utf-8", errors="replace").split("\n")
    drift_cns = new + ghost
    for cn in drift_cns:
        if cn in new:
            # Find BEGIN in tp2
            for i, line in enumerate(lines):
                if re.search(rf"\bDESIGNATED\s+{cn}\b", line):
                    ctx = "\n".join(lines[max(0, i - 2): i + 10])
                    print(f"\n--- cn={cn} [NEW] context in tp2 (line {i+1}):")
                    print(ctx)
                    break
            else:
                # Maybe BEGIN-only-order cn
                print(f"\n--- cn={cn} [NEW]: no DESIGNATED found (BEGIN-order)")
        elif cn in ghost:
            db_entry = next((c for c in co if c.get("cn") == cn), None)
            if db_entry:
                print(f"\n--- cn={cn} [GHOST]: DB says:")
                for k, v in db_entry.items():
                    if k == "cn":
                        continue
                    s = json.dumps(v, ensure_ascii=False)[:120]
                    print(f"    {k}: {s}")


if __name__ == "__main__":
    main()
