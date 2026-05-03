"""scan_game_targets.py - Extract per-component `games` tags from tp2 files.

Scanner scope (v1 per schema doc):
  - Direct per-BEGIN `REQUIRE_PREDICATE GAME_IS ~...~`
  - Direct per-BEGIN `REQUIRE_PREDICATE NOT GAME_IS ~...~` (expanded to positive)
  - Does NOT parse `ACTION_IF GAME_IS` wrappers or `ALWAYS`-block predicates.
    Components under those fall through as universal (no `games` field).

Produces:
  - scripts/game_targets_report.json: full per-component classification
  - scripts/game_targets_changelog.json: changes applied (in --apply mode)
  - stdout: summary + distribution

Apply semantics (mirrors tp2n_backfill — strictly additive):
  - ONLY writes to components where scanner yielded a non-empty games list
  - NEVER overwrites an existing `games` field
  - NEVER touches other fields
  - Idempotent (re-running = 0 writes)

Usage:
  python scripts/scan_game_targets.py              # dry-run, report only
  python scripts/scan_game_targets.py --apply      # write changes
  python scripts/scan_game_targets.py --json       # machine-readable JSON to stdout
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
from audit_tp2_drift import _strip_block_comments, _strip_heredocs  # noqa

ROOT = Path(__file__).resolve().parents[1]
MODS_DIR = ROOT / "data" / "mods"
EXTRACTED = Path("F:/BGMods/Extracted")

# --- Token whitelist (per schema doc) ---
# EE family — install targets the app supports
EE_GAMES = {"eet", "bgee", "bg2ee", "iwdee", "pstee", "sod"}
# Classic / legacy — tagged for data fidelity, not installable
CLASSIC_GAMES = {
    "bg1", "bg2", "soa", "tob", "totsc",
    "bgt", "tutu", "tutu_totsc",
    "iwd", "iwd2", "pst",
    "how", "totlm",                  # IWD expansions (Heart of Winter, Trials of Luremaster)
    "ca",                             # Classic Adventures (BG2 classic-tree expansion)
    "iwd_in_bg2",                     # IWD-in-BG2 conversion (analog of tutu)
}
ALL_GAMES = EE_GAMES | CLASSIC_GAMES


def normalize_token(t: str) -> str:
    """Lowercase + hyphen->underscore (handles `iwd-in-bg2` == `iwd_in_bg2`)."""
    return t.strip().lower().replace("-", "_")


# --- Regexes ---
# Captures both BEGIN @nn/~name~/"name"/bare and multi-line BEGIN that lands
# DESIGNATED/LABEL on next lines. Use the same style as audit_tp2_drift parser.
BEGIN_RX = re.compile(
    r'^\s*BEGIN\s+(?:@(\d+)|~([^~]+)~|"([^"]+)"|([A-Za-z_][\w#-]*))',
    re.M,
)
DESIGNATED_RX = re.compile(r'\bDESIGNATED\s+(\d+)')

# Matches all forms: positive, NOT-prefixed, or !-prefixed
#   REQUIRE_PREDICATE GAME_IS ~...~
#   REQUIRE_PREDICATE NOT GAME_IS ~...~
#   REQUIRE_PREDICATE !GAME_IS ~...~         (exclamation negation; WeiDU accepts both)
#   REQUIRE_PREDICATE (NOT GAME_IS ~...~)    (parenthesized forms)
#   REQUIRE_PREDICATE (!GAME_IS ~...~)
GAME_IS_RX = re.compile(
    r'REQUIRE_PREDICATE\s*(?:\(\s*)?(NOT\s+|!\s*)?GAME_IS\s+~([^~]+)~',
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


def tokenize_games(clause: str) -> list[str]:
    """Split WeiDU GAME_IS clause into individual tokens, normalized."""
    return [normalize_token(t) for t in clause.split() if t.strip()]


def expand_negative(excluded: list[str]) -> list[str]:
    """NOT GAME_IS ~a b c~ -> full whitelist minus {a,b,c}."""
    return sorted(ALL_GAMES - set(excluded))


def classify_games(tokens: list[str]) -> str:
    """Return a one-line classification of a games list for reporting."""
    s = set(tokens)
    ee_overlap = s & EE_GAMES
    classic_overlap = s & CLASSIC_GAMES
    unknown = s - ALL_GAMES
    if unknown:
        return f"unknown_tokens:{sorted(unknown)}"
    if not s:
        return "empty"
    if s <= CLASSIC_GAMES:
        return "classic_only"
    if s <= EE_GAMES:
        return "ee_only"
    if ee_overlap and classic_overlap:
        return "mixed"
    return "other"


def scan_tp2_components(tp2_path: Path) -> dict[int, dict]:
    """Parse a tp2 and return {cn: {games:[...], neg:bool, clause:str, order:int}}.

    Per v1 scope, we walk top-level BEGIN blocks only. For each BEGIN, we read
    forward up to the next BEGIN (or EOF) and look for REQUIRE_PREDICATE
    GAME_IS inside that block. DESIGNATED (or BEGIN order) gives the cn.
    """
    try:
        txt = tp2_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}

    txt = _strip_heredocs(txt)
    txt = _strip_block_comments(txt)

    # Find all BEGIN positions
    begins: list[int] = []
    for m in BEGIN_RX.finditer(txt):
        begins.append(m.start())
    begins.append(len(txt))  # sentinel

    comps: dict[int, dict] = {}
    order = 0
    for i in range(len(begins) - 1):
        block = txt[begins[i]:begins[i + 1]]
        # Resolve cn
        d = DESIGNATED_RX.search(block)
        cn = int(d.group(1)) if d else order
        order += 1
        # Find GAME_IS clause in this block
        game_is_match = GAME_IS_RX.search(block)
        if not game_is_match:
            continue  # omit -> universal
        negated = bool(game_is_match.group(1))
        raw_clause = game_is_match.group(2).strip()
        tokens = tokenize_games(raw_clause)
        if negated:
            games = expand_negative(tokens)
        else:
            games = sorted(set(tokens))
        comps[cn] = {
            "games": games,
            "negated": negated,
            "clause": raw_clause,
        }
    return comps


def insert_games(comp: dict, games: list[str]) -> dict:
    """Return a new component dict with `games` inserted right after `wq`
    (logical install-metadata neighborhood). Falls back to end if `wq` absent.
    Preserves all other fields and their order.
    """
    if "games" in comp:
        return comp  # caller gates on absence
    out = {}
    inserted = False
    for k, v in comp.items():
        out[k] = v
        if k == "wq" and not inserted:
            out["games"] = games
            inserted = True
    if not inserted:
        out["games"] = games
    return out


def main():
    ap = argparse.ArgumentParser(description="Extract game-target tags from tp2s")
    ap.add_argument("--apply", action="store_true", help="Write `games` field to component JSONs")
    ap.add_argument("--json", action="store_true", help="Emit JSON to stdout (dry-run only)")
    ap.add_argument("--only", metavar="STEM", action="append",
                    help="Limit scan to one or more mod stems (repeatable). Useful for pre-commit or manual rescans.")
    args = ap.parse_args()
    only_set = {s.lower() for s in (args.only or [])}

    print("Indexing tp2 files...", file=sys.stderr, flush=True)
    t0 = time.time()
    tp2_idx = build_tp2_index()
    print(f"  indexed {len(tp2_idx)} tp2 stems in {time.time()-t0:.1f}s\n",
          file=sys.stderr, flush=True)

    catalog = json.loads((MODS_DIR / "_catalog.json").read_text(encoding="utf-8"))

    # Per-component tally
    per_mod: list[dict] = []
    tally = Counter()
    unknown_tokens: Counter = Counter()
    total_components = 0
    total_tagged = 0
    mods_with_tp2 = 0
    mods_skipped = 0
    mods_parse_err = 0
    per_classification: dict[str, list] = {
        "ee_only": [], "classic_only": [], "mixed": [],
        "other": [], "unknown_tokens": [],
    }

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

        # --only filter
        if only_set:
            if stem.lower() not in only_set and p.stem.lower() not in only_set:
                continue
        tp2 = tp2_idx.get((wf or "").lower()) or tp2_idx.get(stem.lower())
        if tp2 is None:
            mods_skipped += 1
            total_components += len(co)
            continue

        try:
            parsed = scan_tp2_components(tp2)
        except Exception as e:
            print(f"  parse_err on {stem}: {e}", file=sys.stderr)
            mods_parse_err += 1
            continue
        mods_with_tp2 += 1

        mod_record = {"stem": stem, "fn": fn, "components": []}
        mod_any_tagged = False
        mod_any_written = False
        new_co = list(co)  # shallow copy for rewrite
        for idx, c in enumerate(co):
            cn = c.get("cn")
            total_components += 1
            if cn is None or cn not in parsed:
                continue
            info = parsed[cn]
            games = info["games"]
            if not games:
                continue
            cls = classify_games(games)
            total_tagged += 1
            tally[cls] += 1
            if cls.startswith("unknown_tokens"):
                for t in set(games) - ALL_GAMES:
                    unknown_tokens[t] += 1
            mod_record["components"].append({
                "cn": cn,
                "games": games,
                "clause": info["clause"],
                "negated": info["negated"],
                "classification": cls,
            })
            per_classification[cls.split(":")[0]].append({
                "mod": stem, "cn": cn, "games": games, "clause": info["clause"],
            })
            mod_any_tagged = True

            # Apply: only if field absent (never overwrite)
            if args.apply and "games" not in c:
                new_co[idx] = insert_games(c, games)
                mod_any_written = True

        if mod_any_tagged:
            per_mod.append(mod_record)

        if args.apply and mod_any_written:
            d_new = dict(d)
            d_new["co"] = new_co
            p.write_text(json.dumps(d_new, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Summary output ---
    report = {
        "counts": {
            "catalog_total": len(catalog),
            "mods_with_tp2": mods_with_tp2,
            "mods_skipped_no_tp2": mods_skipped,
            "mods_parse_err": mods_parse_err,
            "total_components": total_components,
            "total_tagged": total_tagged,
            "total_universal": total_components - total_tagged,  # incl. skipped
            "classification": dict(tally),
            "unknown_tokens": dict(unknown_tokens),
        },
        "per_mod": per_mod,
        "samples": {
            k: v[:10] for k, v in per_classification.items()
        },
    }

    out_file = ROOT / "scripts/game_targets_report.json"
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Changelog for apply runs
    if args.apply:
        changelog_file = ROOT / "scripts/game_targets_changelog.json"
        changelog_file.write_text(json.dumps({
            "mode": "apply",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "counts": report["counts"],
            "changes_per_mod": per_mod,
        }, indent=2, ensure_ascii=False), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print("=" * 72)
    print("GAME TARGETS — " + ("APPLIED" if args.apply else "DRY-RUN") + " SCAN REPORT")
    print("=" * 72)
    print(f"Catalog entries        : {report['counts']['catalog_total']}")
    print(f"Mods scanned (w/ tp2)  : {report['counts']['mods_with_tp2']}")
    print(f"Mods skipped (no tp2)  : {report['counts']['mods_skipped_no_tp2']}")
    print(f"Mods parse error       : {report['counts']['mods_parse_err']}")
    print()
    print(f"Total components       : {report['counts']['total_components']}")
    print(f"  tagged (`games` set) : {report['counts']['total_tagged']}")
    print(f"  universal/omitted    : {report['counts']['total_universal']}")
    print()
    print("Tag classification:")
    for cls, n in tally.most_common():
        print(f"  {cls:20} : {n}")
    if unknown_tokens:
        print()
        print("UNKNOWN tokens encountered (NOT in whitelist — needs triage):")
        for tok, n in unknown_tokens.most_common():
            print(f"  {tok!r} : {n}")
    print()
    print(f"Mods that will gain `games` tags: {len(per_mod)}")
    print(f"Full report: {out_file}")


if __name__ == "__main__":
    main()
