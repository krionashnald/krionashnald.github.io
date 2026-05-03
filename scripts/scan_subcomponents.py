"""scan_subcomponents.py - Extract per-component SUBCOMPONENT + GROUP headers.

Populates the `scn` (subcomponent name) and `grn` (group name) fields from
tp2 `SUBCOMPONENT @ref` and `GROUP @ref` clauses. The @refs are resolved
against the mod's TRA files to get human-readable display headers.

Forms handled per BEGIN block:
  SUBCOMPONENT @123           -> @ref, resolved via TRA
  SUBCOMPONENT ~Some header~  -> string literal (used directly)
  SUBCOMPONENT "Some header"
  FORCED_SUBCOMPONENT @123    -> same semantics as SUBCOMPONENT for our purposes
  SUBCOMPONENT @123 (PREDICATE)  -> strip predicate, keep the @ref
  GROUP @456                  -> analogous resolution into `grn`

Produces:
  - scripts/subcomponents_report.json: dry-run analysis
  - scripts/subcomponents_changelog.json: --apply changelog
  - stdout: summary + distribution

Apply semantics (mirrors tp2n_backfill + scan_game_targets):
  - ONLY writes when scanner yields a resolved header
  - NEVER overwrites existing `scn` or `grn`
  - NEVER touches other fields
  - Idempotent

Usage:
  python scripts/scan_subcomponents.py                   # dry-run report
  python scripts/scan_subcomponents.py --apply           # write changes
  python scripts/scan_subcomponents.py --only <stem>     # single mod
  python scripts/scan_subcomponents.py --json            # machine output
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_tp2_drift import (  # noqa
    find_tra_dir,
    load_tra_map,
    _strip_block_comments,
    _strip_heredocs,
)

ROOT = Path(__file__).resolve().parents[1]
MODS_DIR = ROOT / "data" / "mods"
EXTRACTED = Path("F:/BGMods/Extracted")


# --- Regexes ---

BEGIN_RX = re.compile(
    r'^\s*BEGIN\s+(?:@(\d+)|~([^~]+)~|"([^"]+)"|([A-Za-z_][\w#-]*))',
    re.M,
)
DESIGNATED_RX = re.compile(r'\bDESIGNATED\s+(\d+)')

# SUBCOMPONENT / FORCED_SUBCOMPONENT with @ref, ~~, or ""
# Optional parenthesized predicate after is not captured here — we just grab
# the immediate @ref/literal.
SUBCOMPONENT_RX = re.compile(
    r'\b(?:FORCED_)?SUBCOMPONENT\s+(?:@(\d+)|~([^~]*)~|"([^"]*)")',
    re.I,
)

# GROUP with @ref or literal
GROUP_RX = re.compile(
    r'\bGROUP\s+(?:@(\d+)|~([^~]*)~|"([^"]*)")',
    re.I,
)


def build_tp2_index():
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


def resolve_ref(m_groups: tuple, tra_map: dict[int, str]) -> str | None:
    """Given a regex match tuple (id, tilde_literal, quote_literal),
    return the resolved string or None if it can't be resolved.
    """
    ref_id, tilde, quoted = m_groups
    if ref_id is not None:
        return tra_map.get(int(ref_id))
    if tilde is not None:
        return tilde.strip() or None
    if quoted is not None:
        return quoted.strip() or None
    return None


def scan_tp2_components(tp2_path: Path, tra_map: dict[int, str]) -> dict[int, dict]:
    """Return {cn: {scn, grn}} per component from a single tp2.

    Walks top-level BEGIN blocks (same approach as scan_game_targets). For
    each block, extracts SUBCOMPONENT/GROUP refs and resolves via TRA.
    """
    try:
        txt = tp2_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    txt = _strip_heredocs(txt)
    txt = _strip_block_comments(txt)

    begins = [m.start() for m in BEGIN_RX.finditer(txt)]
    begins.append(len(txt))

    comps: dict[int, dict] = {}
    order = 0
    for i in range(len(begins) - 1):
        block = txt[begins[i]:begins[i + 1]]
        d = DESIGNATED_RX.search(block)
        cn = int(d.group(1)) if d else order
        order += 1

        scn = None
        grn = None
        sub_m = SUBCOMPONENT_RX.search(block)
        if sub_m:
            scn = resolve_ref(sub_m.groups(), tra_map)
            # Reject if resolution produced a game-target-style literal
            # (e.g., "bgee bg2ee eet") or a TRA-key placeholder
            if scn and _looks_like_header(scn):
                pass
            else:
                scn = None
        grp_m = GROUP_RX.search(block)
        if grp_m:
            grn = resolve_ref(grp_m.groups(), tra_map)
            if grn and _looks_like_header(grn):
                pass
            else:
                grn = None

        if scn or grn:
            comps[cn] = {"scn": scn, "grn": grn}
    return comps


# Filter out resolved strings that look like predicate clauses or
# obviously wrong content (e.g., game tokens that WeiDU authors sometimes
# use as group names by mistake). Keeps readable headers.
GAME_TOKEN_ONLY_RX = re.compile(
    r'^\s*(?:bgee|bg2ee|eet|iwdee|pstee|sod|bg1|bg2|tob|soa|totsc|bgt|tutu|tutu_totsc|iwd|iwd2|how|totlm|pst|ca|iwd_in_bg2|\s)+\s*$',
    re.I,
)


def _looks_like_header(s: str) -> bool:
    """Heuristic: is this resolved string a human-readable header, not a
    fragment of tp2 syntax that accidentally matched our regex?
    """
    if not s:
        return False
    s = s.strip()
    if len(s) < 1 or len(s) > 200:
        return False
    # Reject game-token-only strings (scanner falsely picked up a
    # GAME_IS-token string, not a header)
    if GAME_TOKEN_ONLY_RX.match(s):
        return False
    # Reject strings that are obviously WeiDU keywords
    BAD_KEYWORDS = {"BEGIN", "END", "INCLUDE", "COPY", "PATCH"}
    if s.upper() in BAD_KEYWORDS:
        return False
    return True


def insert_after_g(comp: dict, scn: str | None, grn: str | None) -> dict:
    """Insert scn/grn right after `g` (or after `pi` if `g` absent).
    Preserves existing key order.
    """
    inserted = False
    out = {}
    for k, v in comp.items():
        out[k] = v
        if not inserted and k in ("g", "pi"):
            if scn is not None and "scn" not in comp:
                out["scn"] = scn
            if grn is not None and "grn" not in comp:
                out["grn"] = grn
            inserted = True
    if not inserted:
        if scn is not None and "scn" not in comp:
            out["scn"] = scn
        if grn is not None and "grn" not in comp:
            out["grn"] = grn
    return out


def main():
    ap = argparse.ArgumentParser(description="Extract SUBCOMPONENT/GROUP headers from tp2s")
    ap.add_argument("--apply", action="store_true", help="Write scn/grn fields to component JSONs")
    ap.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    ap.add_argument("--only", metavar="STEM", action="append",
                    help="Limit scan to one or more mod stems (repeatable)")
    args = ap.parse_args()
    only_set = {s.lower() for s in (args.only or [])}

    print("Indexing tp2 files...", file=sys.stderr, flush=True)
    t0 = time.time()
    tp2_idx = build_tp2_index()
    print(f"  indexed {len(tp2_idx)} tp2 stems in {time.time()-t0:.1f}s\n",
          file=sys.stderr, flush=True)

    catalog = json.loads((MODS_DIR / "_catalog.json").read_text(encoding="utf-8"))

    counts = Counter()
    top_scn: Counter = Counter()
    top_grn: Counter = Counter()
    mod_results = []

    for mid_s, fn in catalog.items():
        p = MODS_DIR / fn
        if not p.exists():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        co = d.get("co", [])
        if not co:
            continue

        wf = (co[0].get("wf") if co else None) or d.get("t") or p.stem
        stem = d.get("t") or p.stem

        if only_set and stem.lower() not in only_set and p.stem.lower() not in only_set:
            continue

        tp2 = tp2_idx.get((wf or "").lower()) or tp2_idx.get(stem.lower())
        if tp2 is None:
            counts["mods_no_tp2"] += 1
            continue

        try:
            tra_dir = find_tra_dir(tp2)
            tra_map = load_tra_map(tra_dir, tp2)
            parsed = scan_tp2_components(tp2, tra_map)
        except Exception as e:
            print(f"  parse_err on {stem}: {e}", file=sys.stderr)
            counts["mods_parse_err"] += 1
            continue

        counts["mods_scanned"] += 1

        mod_record = {"stem": stem, "fn": fn, "components": []}
        mod_any = False
        mod_any_written = False
        new_co = list(co)

        for idx, c in enumerate(co):
            cn = c.get("cn")
            if cn is None or cn not in parsed:
                continue
            info = parsed[cn]
            scn = info.get("scn")
            grn = info.get("grn")
            if not scn and not grn:
                continue

            has_scn = "scn" in c
            has_grn = "grn" in c
            # Only fill where field is absent
            scn_to_write = scn if (scn and not has_scn) else None
            grn_to_write = grn if (grn and not has_grn) else None
            if not scn_to_write and not grn_to_write:
                # Already populated
                if scn: counts["comp_scn_existing"] += 1
                if grn: counts["comp_grn_existing"] += 1
                continue

            if scn_to_write:
                counts["comp_scn_new"] += 1
                top_scn[scn] += 1
            if grn_to_write:
                counts["comp_grn_new"] += 1
                top_grn[grn] += 1

            mod_record["components"].append({
                "cn": cn,
                "scn": scn,
                "grn": grn,
                "writing": {"scn": bool(scn_to_write), "grn": bool(grn_to_write)},
            })
            mod_any = True

            if args.apply:
                new_co[idx] = insert_after_g(c, scn_to_write, grn_to_write)
                mod_any_written = True

        if mod_any:
            mod_results.append(mod_record)

        if args.apply and mod_any_written:
            d_new = dict(d)
            d_new["co"] = new_co
            p.write_text(json.dumps(d_new, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Report ---
    report = {
        "counts": dict(counts),
        "mod_count_with_changes": len(mod_results),
        "per_mod": mod_results,
        "top_scn_headers": top_scn.most_common(30),
        "top_grn_headers": top_grn.most_common(30),
    }
    out_file = ROOT / "scripts/subcomponents_report.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.apply:
        out_changelog = ROOT / "scripts/subcomponents_changelog.json"
        out_changelog.write_text(json.dumps({
            "mode": "apply",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "counts": dict(counts),
            "changes": mod_results,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print("=" * 72)
    print("SUBCOMPONENT / GROUP SCAN " + ("[APPLIED]" if args.apply else "[DRY-RUN]"))
    print("=" * 72)
    print(f"Mods scanned              : {counts.get('mods_scanned', 0)}")
    print(f"Mods with no tp2          : {counts.get('mods_no_tp2', 0)}")
    print(f"Mods with parse error     : {counts.get('mods_parse_err', 0)}")
    print()
    print(f"NEW scn fills             : {counts.get('comp_scn_new', 0)}")
    print(f"NEW grn fills             : {counts.get('comp_grn_new', 0)}")
    print(f"Existing scn (untouched)  : {counts.get('comp_scn_existing', 0)}")
    print(f"Existing grn (untouched)  : {counts.get('comp_grn_existing', 0)}")
    print(f"Mods gaining fields       : {len(mod_results)}")
    print()
    if top_scn:
        print("Top 15 most-used SUBCOMPONENT headers:")
        for h, n in top_scn.most_common(15):
            print(f"  ({n:>4})  {h[:70]}")
        print()
    if top_grn:
        print("Top 15 GROUP headers:")
        for h, n in top_grn.most_common(15):
            print(f"  ({n:>4})  {h[:70]}")
    print(f"\nFull report: {out_file}")


if __name__ == "__main__":
    main()
