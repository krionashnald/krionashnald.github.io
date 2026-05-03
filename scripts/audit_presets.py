#!/usr/bin/env python3
"""
audit_presets.py - Report-only audit of data/presets.json against data/mods/*.json.

DOES NOT MODIFY ANY FILES. Per user preference: "I wouldn't want anything
automatic, I've had too many cases of things being updated that overwrote
things that were actually correct, it would need to surface it in a report."

Surfaces:
  - invalid_mod_id    : key references a modId not in the catalog (ERR)
  - cn_not_in_mod     : key references a cn not in that mod's co[] (ERR)
  - points_to_gone    : key references a `gone: true` component (WARN)
  - points_to_dep     : key references a `dep`-flagged component (INFO)
  - duplicate_keys    : same key appears twice in one preset's keys[] (WARN)
  - suspicious_format : the `cn` looks like it could be a `co[]` index
                        instead of a real cn (INFO heuristic)
  - missing_essentials: essential mods (DLC Merger=3, EEFixpack=4, EET=12,
                        EET_End=449) absent from a preset (INFO)

Exit code: always 0. This is a report, not a gate.

Usage:
  python scripts/audit_presets.py          # human-readable report
  python scripts/audit_presets.py --json   # machine-readable JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESETS_PATH = ROOT / "data" / "presets.json"
MODS_INDEX_PATH = ROOT / "data" / "mods-index.json"
MODS_DIR = ROOT / "data" / "mods"

ESSENTIAL_MOD_IDS = {
    3: "DLC Merger",
    4: "EEFixpack",
    12: "EET",
    449: "EET_End",
}


def load_mods():
    """Load per-mod JSONs keyed by `i`. Falls back to index if details missing."""
    mods = {}
    for f in sorted(MODS_DIR.glob("*.json")):
        if f.name.startswith("_") or f.name == "mods-index.json":
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if "i" in d:
                mods[d["i"]] = d
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARN: failed to read {f.name}: {e}", file=sys.stderr)
    return mods


def audit_preset(preset: dict, mods: dict) -> dict:
    """Analyze one preset, return a report dict."""
    keys = preset.get("keys", []) or []
    report = {
        "id": preset.get("id"),
        "name": preset.get("name"),
        "total_keys": len(keys),
        "invalid_mod_id": [],
        "cn_not_in_mod": [],
        "points_to_gone": [],
        "points_to_dep": [],
        "duplicate_keys": [],
        "suspicious_format": [],
        "missing_essentials": [],
        "unparseable_keys": [],
    }

    # --- duplicate detection ---
    counts = Counter(keys)
    for k, n in counts.items():
        if n > 1:
            report["duplicate_keys"].append({"key": k, "count": n})

    # --- per-key validation ---
    mod_ids_in_preset = set()
    for k in keys:
        parts = str(k).split("-")
        if len(parts) < 2:
            report["unparseable_keys"].append(k)
            continue
        try:
            mi = int(parts[0])
            cn = int(parts[1])
        except ValueError:
            report["unparseable_keys"].append(k)
            continue

        mod_ids_in_preset.add(mi)

        mod = mods.get(mi)
        if mod is None:
            report["invalid_mod_id"].append({"key": k, "mod_id": mi})
            continue

        comps = mod.get("co", []) or []
        comp = next((c for c in comps if c.get("cn") == cn), None)
        if comp is None:
            # Heuristic: does `cn` look like an index into co[]?
            #   - cn must be within [0, len(comps))
            #   - AND the actual cn at that position differs from `cn` itself
            # Both satisfied → suspicious; probably someone wrote modId-idx.
            suspicious = False
            if 0 <= cn < len(comps) and comps[cn].get("cn") != cn:
                suspicious = True
                report["suspicious_format"].append({
                    "key": k, "mod_id": mi, "bad_cn": cn,
                    "mod_name": mod.get("n"),
                    "would_be_idx_points_to_cn": comps[cn].get("cn"),
                    "would_be_idx_points_to_name": comps[cn].get("n"),
                })
            report["cn_not_in_mod"].append({
                "key": k, "mod_id": mi, "cn": cn,
                "mod_name": mod.get("n"),
                "mod_co_count": len(comps),
                "also_flagged_suspicious": suspicious,
            })
            continue

        if comp.get("gone"):
            report["points_to_gone"].append({
                "key": k, "mod_id": mi, "cn": cn,
                "mod_name": mod.get("n"),
                "comp_name": comp.get("n"),
            })
        if comp.get("dep"):
            report["points_to_dep"].append({
                "key": k, "mod_id": mi, "cn": cn,
                "mod_name": mod.get("n"),
                "comp_name": comp.get("n"),
                "dep_reason": comp.get("dep") if isinstance(comp.get("dep"), str) else True,
            })

    # --- essentials coverage ---
    for eid, ename in ESSENTIAL_MOD_IDS.items():
        if eid not in mod_ids_in_preset:
            report["missing_essentials"].append({"mod_id": eid, "mod_name": ename})

    return report


def format_human(reports: list, mods: dict) -> str:
    """Render the report as human-readable text."""
    out = []
    out.append("=" * 72)
    out.append("PRESET AUDIT REPORT (report-only; no files modified)")
    out.append("=" * 72)
    out.append(f"Catalog: {len(mods)} mods")
    out.append(f"Presets: {len(reports)}")
    out.append("")

    grand = {
        "errors": 0, "warnings": 0, "infos": 0,
    }

    for r in reports:
        out.append(f"--- Preset: {r['name']} (id={r['id']}, keys={r['total_keys']}) ---")
        err = len(r["invalid_mod_id"]) + len(r["cn_not_in_mod"]) + len(r["unparseable_keys"])
        warn = len(r["points_to_gone"]) + len(r["duplicate_keys"])
        info = len(r["points_to_dep"]) + len(r["suspicious_format"]) + len(r["missing_essentials"])
        grand["errors"] += err
        grand["warnings"] += warn
        grand["infos"] += info

        if err == 0 and warn == 0 and info == 0:
            out.append("  OK - no issues")
            out.append("")
            continue

        if r["unparseable_keys"]:
            out.append(f"  [ERR] unparseable_keys ({len(r['unparseable_keys'])}):")
            for k in r["unparseable_keys"][:10]:
                out.append(f"    {k}")

        if r["invalid_mod_id"]:
            out.append(f"  [ERR] invalid_mod_id ({len(r['invalid_mod_id'])}):")
            for e in r["invalid_mod_id"][:10]:
                out.append(f"    {e['key']}  (mod i={e['mod_id']} not in catalog)")

        if r["cn_not_in_mod"]:
            out.append(f"  [ERR] cn_not_in_mod ({len(r['cn_not_in_mod'])}):")
            for e in r["cn_not_in_mod"][:10]:
                tail = ""
                if e["also_flagged_suspicious"]:
                    tail = " -- SEE suspicious_format below"
                out.append(f"    {e['key']}  mod=\"{e['mod_name']}\" (co has {e['mod_co_count']} comps){tail}")

        if r["points_to_gone"]:
            out.append(f"  [WARN] points_to_gone ({len(r['points_to_gone'])}):")
            for e in r["points_to_gone"][:10]:
                out.append(f"    {e['key']}  {e['mod_name']} / \"{e['comp_name']}\"")

        if r["duplicate_keys"]:
            out.append(f"  [WARN] duplicate_keys ({len(r['duplicate_keys'])}):")
            for e in r["duplicate_keys"][:10]:
                out.append(f"    {e['key']}  (x{e['count']})")

        if r["points_to_dep"]:
            out.append(f"  [INFO] points_to_dep ({len(r['points_to_dep'])}):")
            for e in r["points_to_dep"][:10]:
                reason = e["dep_reason"] if isinstance(e["dep_reason"], str) else "(flagged)"
                out.append(f"    {e['key']}  {e['mod_name']} / \"{e['comp_name']}\" -- {reason}")

        if r["suspicious_format"]:
            out.append(f"  [INFO] suspicious_format ({len(r['suspicious_format'])}):")
            out.append(f"    (these look like `modId-idx` instead of `modId-cn` - verify manually)")
            for e in r["suspicious_format"][:10]:
                out.append(
                    f"    {e['key']}  mod=\"{e['mod_name']}\"  "
                    f"if idx -> cn={e['would_be_idx_points_to_cn']} "
                    f"(\"{e['would_be_idx_points_to_name']}\")"
                )

        if r["missing_essentials"]:
            out.append(f"  [INFO] missing_essentials ({len(r['missing_essentials'])}):")
            for e in r["missing_essentials"]:
                out.append(f"    mod i={e['mod_id']} \"{e['mod_name']}\" has no key in this preset")

        out.append("")

    out.append("=" * 72)
    out.append("SUMMARY")
    out.append(f"  Errors   : {grand['errors']}  (invalid_mod_id, cn_not_in_mod, unparseable_keys)")
    out.append(f"  Warnings : {grand['warnings']}  (points_to_gone, duplicate_keys)")
    out.append(f"  Info     : {grand['infos']}  (points_to_dep, suspicious_format, missing_essentials)")
    out.append("=" * 72)
    out.append("This audit is report-only; no files were modified.")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Audit data/presets.json (report-only)")
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = ap.parse_args()

    if not PRESETS_PATH.exists():
        print(f"ERR: presets file not found: {PRESETS_PATH}", file=sys.stderr)
        sys.exit(2)

    presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    mods = load_mods()

    reports = [audit_preset(p, mods) for p in presets]

    if args.json:
        print(json.dumps({
            "catalog_size": len(mods),
            "presets": reports,
        }, indent=2))
    else:
        print(format_human(reports, mods))

    # Always exit 0 - this is a report, not a gate.
    sys.exit(0)


if __name__ == "__main__":
    main()
