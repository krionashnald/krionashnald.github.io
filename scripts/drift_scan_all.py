"""Drift audit across all mods — fast version.

Indexes ALL tp2 files in Extracted ONCE (single rglob), then looks up by
mod wf name. This avoids the O(mods * files) performance of per-mod rglob.

Uses the hardened parser from audit_tp2_drift.py for:
  - Block-comment stripping
  - Multi-line DESIGNATED
  - LANGUAGE-declared tra priority
  - Last-wins within tra file
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_tp2_drift import (  # noqa: E402
    find_tra_dir,
    load_tra_map,
    parse_tp2_components,
)

ROOT = Path(__file__).resolve().parents[1]
MODS_DIR = ROOT / "data" / "mods"
EXTRACTED = Path("F:/BGMods/Extracted")
CATALOG = json.loads((MODS_DIR / "_catalog.json").read_text(encoding="utf-8"))


def build_tp2_index():
    """Single pass to build {tp2_stem_lower → tp2_path}."""
    print("Building tp2 index...", file=sys.stderr, flush=True)
    t0 = time.time()
    idx = {}
    count = 0
    for tp2 in EXTRACTED.rglob("*.tp2"):
        count += 1
        # Skip patch files, nested compat folders that aren't the real mod
        sp = str(tp2).replace("\\", "/").lower()
        if "patches/files" in sp or "fresh" in sp:
            continue
        stem = tp2.stem.lower()
        if stem.startswith("setup-"):
            stem = stem[6:]
        # First-wins (prefer shallower paths via default rglob order)
        if stem not in idx:
            idx[stem] = tp2
    print(f"  indexed {count} tp2 files → {len(idx)} unique stems in {time.time()-t0:.1f}s",
          file=sys.stderr, flush=True)
    return idx


def main():
    tp2_idx = build_tp2_index()

    results = []
    missing_tp2 = []
    scanned = 0
    t0 = time.time()

    for mid_s, fn in CATALOG.items():
        p = MODS_DIR / fn
        if not p.exists():
            continue
        try:
            db = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        co = db.get("co", [])
        if not co:
            continue
        wf = co[0].get("wf") or db.get("t") or p.stem
        stem = db.get("t") or p.stem

        # Lookup tp2 via index
        tp2 = tp2_idx.get(wf.lower()) or tp2_idx.get(stem.lower())
        if tp2 is None:
            missing_tp2.append((stem, fn))
            continue

        tra_dir = find_tra_dir(tp2)
        tra_map = load_tra_map(tra_dir, tp2)
        try:
            tp2_comps = parse_tp2_components(tp2, tra_map)
        except Exception as e:
            print(f"  parse error on {stem}: {e}", file=sys.stderr)
            continue

        tp2_cns = set(tp2_comps.keys())
        db_cns = {c.get("cn") for c in co if c.get("cn") is not None}

        ghost = db_cns - tp2_cns
        new_cns = tp2_cns - db_cns

        ghost_by_cn = {c["cn"]: c for c in co if c.get("cn") in ghost}
        unmarked_ghost = {
            cn for cn in ghost
            if not ghost_by_cn[cn].get("gone") and not ghost_by_cn[cn].get("dep")
        }

        scanned += 1
        if new_cns or unmarked_ghost:
            results.append({
                "stem": stem,
                "fn": fn,
                "db_count": len(db_cns),
                "tp2_count": len(tp2_comps),
                "new": sorted(new_cns),
                "ghost_unmarked": sorted(unmarked_ghost),
                "ghost_marked": sorted(ghost - unmarked_ghost),
            })

        if scanned % 50 == 0:
            print(f"  {scanned} scanned ({time.time()-t0:.1f}s elapsed)",
                  file=sys.stderr, flush=True)

    print(f"\nScanned: {scanned} mods (of {len(CATALOG)} catalog entries)")
    print(f"Missing tp2 (can't verify): {len(missing_tp2)}")
    print(f"Drift detected: {len(results)} mods\n")

    results.sort(key=lambda r: -(len(r["new"]) + len(r["ghost_unmarked"])))

    print(f"{'Mod':32} {'DB':>5} {'TP2':>5} {'New':>5} {'Ghost!':>7} {'Ghost*':>7}")
    print("-" * 75)
    for r in results:
        print(f"{r['stem'][:32]:32} {r['db_count']:>5} {r['tp2_count']:>5} "
              f"{len(r['new']):>5} {len(r['ghost_unmarked']):>7} {len(r['ghost_marked']):>7}")

    out = ROOT / "scripts/drift_scan_all_report.json"
    out.write_text(json.dumps({
        "scanned": scanned,
        "missing_tp2_count": len(missing_tp2),
        "missing_tp2": [s for s, _ in missing_tp2[:100]],
        "drift_count": len(results),
        "results": results,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nFull report: {out}")


if __name__ == "__main__":
    main()
