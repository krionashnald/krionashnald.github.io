#!/usr/bin/env python3
"""reorder_co_from_tp2.py - Re-sort each mod's co[] array to match tp2 BEGIN order.

Problem: per-mod detail files have a co[] array listing components. Over years
of hand-editing, the array order drifts from the canonical tp2 BEGIN order.
Users expect the browse list to show components in install-prompt order, not
in whatever order we happened to edit them.

Fix: for each mod with a tp2 on disk at F:/BGMods/Extracted/, parse the tp2's
BEGIN blocks to get canonical cn ordering, then sort mod['co'] to match.

Rules:
  - Components with a cn present in the tp2 are sorted by tp2 position.
  - Components with cn NOT in the tp2 (phantom/deprecated entries) keep their
    current relative position, appended after the tp2-ordered block.
  - Components with cn == 0 / missing are treated as phantom and land at the end.
  - Mods without a findable tp2 are skipped with a warning.
  - Files are only rewritten when the order actually changes.

Usage:
    python scripts/reorder_co_from_tp2.py                 # dry run (default)
    python scripts/reorder_co_from_tp2.py --apply         # write changes
    python scripts/reorder_co_from_tp2.py --only <stem>   # single mod
    python scripts/reorder_co_from_tp2.py --verbose       # show per-mod diffs

Exit codes:
    0 - dry-run complete or --apply succeeded
    1 - missing-tp2 warnings present; apply still ran on mods that had tp2s

Reuses parse_tp2_components() from audit_tp2_drift.py for the BEGIN parser.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODS_DIR = ROOT / "data" / "mods"

# Reuse the hardened tp2 parser from audit_tp2_drift (handles block comments,
# heredocs, LABELs, DESIGNATED, bare identifiers, multi-line BEGIN, etc.)
sys.path.insert(0, str(ROOT / "scripts"))
from audit_tp2_drift import EXTRACTED, find_tra_dir, load_tra_map, parse_tp2_components  # noqa: E402


_TP2_INDEX: dict[str, Path] | None = None


def build_tp2_index() -> dict[str, Path]:
    """Walk Extracted/ ONCE to build {wf_lower: tp2_path}. O(tree) not O(mods*tree).

    Populates keys for both 'setup-<wf>' and '<wf>' lookups by indexing each
    tp2 by its stem, with preference for 'setup-*' (WeiDU convention) when
    both exist for the same base name.
    """
    global _TP2_INDEX
    if _TP2_INDEX is not None:
        return _TP2_INDEX
    idx: dict[str, Path] = {}
    if EXTRACTED.exists():
        for tp2 in EXTRACTED.rglob("*.tp2"):
            stem = tp2.stem.lower()
            # setup-foo.tp2 → also register 'foo' (foldername-style key)
            if stem.startswith("setup-"):
                base = stem[len("setup-"):]
                # Prefer setup-* over bare tp2 (WeiDU convention)
                idx[base] = tp2
                idx[stem] = tp2
            else:
                idx.setdefault(stem, tp2)
    _TP2_INDEX = idx
    return idx


def resolve_tp2(wf: str) -> Path | None:
    """O(1) lookup from precomputed index."""
    if not wf:
        return None
    idx = build_tp2_index()
    return idx.get(wf.lower())


def tp2_cn_order(tp2_path: Path) -> list[int]:
    """Return [cn, ...] in BEGIN order from the given tp2.

    parse_tp2_components returns dict[int, str] keyed by cn with insertion
    order == BEGIN order. We only need keys.
    """
    tra_dir = find_tra_dir(tp2_path)
    tra_map = load_tra_map(tra_dir) if tra_dir else {}
    comp_map = parse_tp2_components(tp2_path, tra_map)
    return list(comp_map.keys())


def reorder_co(co: list[dict], tp2_order: list[int]) -> tuple[list[dict], bool]:
    """Sort co to match tp2_order. Returns (new_co, changed)."""
    pos_in_tp2 = {cn: i for i, cn in enumerate(tp2_order)}

    def sort_key(item: dict):
        cn = item.get("cn")
        # Fallback: use wc if cn isn't set. Some mods use wc as the only
        # identifier. cn is preferred because it's the DESIGNATED value.
        if cn is None:
            cn = item.get("wc")
        pos = pos_in_tp2.get(cn) if cn is not None else None
        # None-in-tp2 items sort AFTER everything in tp2, preserving relative
        # order by keeping their original index as tiebreaker.
        if pos is None:
            return (1, 0)
        return (0, pos)

    indexed = list(enumerate(co))
    new_sorted = sorted(indexed, key=lambda pair: (*sort_key(pair[1]), pair[0]))
    new_co = [item for _, item in new_sorted]
    old_cns = [c.get("cn") for c in co]
    new_cns = [c.get("cn") for c in new_co]
    return new_co, old_cns != new_cns


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write changes")
    ap.add_argument("--only", metavar="STEM", help="Process only this mod file (stem, no .json)")
    ap.add_argument("--verbose", "-v", action="store_true", help="Per-mod diffs")
    args = ap.parse_args()

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== reorder_co_from_tp2.py ({mode}) ===")

    mods = sorted(MODS_DIR.glob("*.json"))
    if args.only:
        mods = [p for p in mods if p.stem == args.only]
        if not mods:
            print(f"No mod found matching stem '{args.only}'", file=sys.stderr)
            return 1

    reordered = []
    missing_tp2 = []
    already_ordered = 0
    no_co = 0
    skipped_catalog = 0

    for path in mods:
        if path.name == "_catalog.json":
            skipped_catalog += 1
            continue
        try:
            mod = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [parse-error] {path.name}: {e}", file=sys.stderr)
            continue

        co = mod.get("co")
        if not co or not isinstance(co, list):
            no_co += 1
            continue

        # Find the tp2 via the precomputed Extracted index. Try wf on first
        # component, mod['t'], then the file stem — whichever matches first.
        wf_candidates = []
        if co and co[0].get("wf"):
            wf_candidates.append(co[0]["wf"])
        if mod.get("t"):
            wf_candidates.append(mod["t"])
        wf_candidates.append(path.stem)
        tp2 = None
        matched_wf = None
        for cand in wf_candidates:
            tp2 = resolve_tp2(cand)
            if tp2:
                matched_wf = cand
                break
        if tp2 is None:
            missing_tp2.append((path.name, wf_candidates[0] if wf_candidates else "?"))
            continue
        wf = matched_wf

        tp2_order = tp2_cn_order(tp2)
        if not tp2_order:
            missing_tp2.append((path.name, f"{wf} (tp2 found but no BEGINs parsed: {tp2})"))
            continue

        new_co, changed = reorder_co(co, tp2_order)
        if not changed:
            already_ordered += 1
            continue

        reordered.append((path.name, len(co), sum(1 for a, b in zip(co, new_co) if a.get("cn") != b.get("cn"))))

        if args.verbose:
            old_cns = [c.get("cn") for c in co][:15]
            new_cns = [c.get("cn") for c in new_co][:15]
            print(f"  {path.name}: reordered {len(co)} components")
            print(f"    old cn order (head 15): {old_cns}")
            print(f"    new cn order (head 15): {new_cns}")

        if args.apply:
            mod["co"] = new_co
            path.write_text(
                json.dumps(mod, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    print(f"\nTotal mod files examined:        {len(mods) - skipped_catalog}")
    print(f"Already in tp2 order:            {already_ordered}")
    print(f"Missing co[] entirely:           {no_co}")
    print(f"Missing tp2 (skipped):           {len(missing_tp2)}")
    print(f"Reordered (would reorder):       {len(reordered)}")

    if reordered and not args.verbose:
        print(f"\n--- Reorders ({min(20, len(reordered))} shown of {len(reordered)}) ---")
        for name, total, moved in reordered[:20]:
            print(f"  {name:40s}  {moved}/{total} moved")
        if len(reordered) > 20:
            print(f"  ... plus {len(reordered) - 20} more")

    if missing_tp2:
        print(f"\n--- Missing tp2s ({min(10, len(missing_tp2))} shown of {len(missing_tp2)}) ---")
        for name, wf in missing_tp2[:10]:
            print(f"  {name}  (wf={wf})")

    if not args.apply:
        print(f"\nDry run. Rerun with --apply to write changes.")
    else:
        print(f"\nApplied. Rerun `python scripts/build_index.py --write` to refresh the index.")

    return 1 if missing_tp2 else 0


if __name__ == "__main__":
    sys.exit(main())
