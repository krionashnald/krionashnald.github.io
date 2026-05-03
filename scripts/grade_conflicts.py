#!/usr/bin/env python3
"""grade_conflicts.py — automated evidence-grading for every conflict /
advisory / known-issue entry in `data/mods/*.json`.

Goal: scan every entry, score it against a set of heuristics, and emit a
`conflict_audit_report.json` that lists each entry's current grade (if any)
alongside a **recommended** grade. A follow-up tool (`apply_conflict_grades.py`)
reads the report and applies the recommendations at scale; reviewers can
inspect the report's `notes` field to sanity-check any edge cases before
committing.

## Grading heuristics

For each entry the script evaluates these signals in order and picks the
highest-confidence grade supported by the evidence:

1. **`observed`** — the entry already carries either:
   - `sessionId`, OR
   - `source` containing a session-ish token (8+ hex chars, `test #N`, `session`,
     `observed`, `WSETUP.DEBUG`, `Test #`).
   These are the gold-standard entries; keep as-is.

2. **`mechanism-verified`** — the entry has:
   - A `source` field with technical detail (file names, tp2 line numbers,
     FORBID_COMPONENT / REQUIRE_PREDICATE / COPY_EXISTING citations), OR
   - A `reason` that names specific file paths or engine symbols
     (e.g. "STATS.IDS", "DDEFAI.BCS", "cn:60200") and does NOT use speculation
     markers, OR
   - `severity == "hard"` AND the reason cites FORBID_COMPONENT / mutual
     detection (author-managed conflicts are almost always real).

3. **`speculative`** — the `reason` contains any of:
   - Hedging words: `may`, `might`, `maybe`, `could`, `possibly`, `likely`,
     `probably`, `seems to`, `should`, `would`, `unexpected`.
   - Anti-claim patterns: `likely not a real conflict`, `not actually`,
     `untested`, `unverified`.

4. **`unclassified`** — the entry doesn't trigger any of the above. These
   need human review; default to leaving the existing grade alone.

## Action codes on each report entry

- `keep` — existing grade matches recommendation; do nothing.
- `upgrade` — recommended grade is higher-confidence than current; apply.
- `downgrade` — recommended grade is lower-confidence than current; apply
  (usually involves moving from `conflicts[]` to `advisories[]`).
- `set` — no current grade; apply recommendation.
- `review` — recommendation is `unclassified`; skip automatic action.

## Output

Writes `scripts/grade_conflicts.result.json` with:
- `summary`: counts of each action and grade
- `entries`: per-entry records for manual review / scripted application

Also prints a short human-readable summary to stderr.

## Usage

```
python scripts/grade_conflicts.py
python scripts/grade_conflicts.py --apply   # not yet implemented here;
                                            # apply_conflict_grades.py does it
```

The `--apply` flag is reserved so the same invocation can later be used as a
one-shot pipeline; for now, use `apply_conflict_grades.py` separately so the
review step is enforced.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(os.environ.get("FORGE_ROOT", "F:/BGMods/eet-mod-forge"))
MODS_DIR = REPO_ROOT / "data" / "mods"
OUTPUT_PATH = REPO_ROOT / "scripts" / "grade_conflicts.result.json"

# ── Heuristic regexes ────────────────────────────────────────────────────────

# Session/test references — the concrete evidence marker. Only positive
# claims count: `observed in session X`, `Test #26`, or a bare 8+ hex session
# id next to the word `session`. We deliberately do NOT match bare
# "WSETUP.DEBUG" or bare "observed" — those can appear in phrases like
# "No WSETUP.DEBUG match" or "failure NOT observed" which are anti-claims.
RE_SESSION = re.compile(
    r"(?:session[=: ]+[0-9a-f]{8,}"                # session=aa9f014c
    r"|\bsession\s+[0-9a-f]{8,}"                   # session aa9f014c
    r"|\btest\s*#\s*\d+"                           # Test #26
    r"|\bobserved\s+(?:in|during|at|on)\b"         # observed in session X
    r"|\bmatched\s+in\s+(?:WSETUP|install\.log)"   # matched in WSETUP...
    r"|\bfired\s+in\s+session)",                   # fired in session ...
    re.IGNORECASE,
)

# Anti-claims containing session-shaped phrasing — these cancel out a
# would-be RE_SESSION match. Example: "failure NOT observed in any preserved
# WSETUP.DEBUG". Whitelist a few explicit negations; a cleaner future
# implementation would parse sentences, but this is the 90% shape.
RE_SESSION_NEGATION = re.compile(
    r"(?:\bnot\s+observed\b"
    r"|\bnever\s+observed\b"
    r"|\bno\s+(?:wsetup\.debug\s+)?match\b"
    r"|\bhas\s+not\s+(?:yet\s+)?been\s+seen\b"
    r"|\bhas\s+never\s+appeared\b"
    r"|\bnot\s+(?:yet\s+)?fired\b)",
    re.IGNORECASE,
)

# Speculative hedging — strong signal to downgrade.
RE_SPECULATION = re.compile(
    r"\b(may|might|maybe|could|possibly|likely|probably|seems to|"
    r"unexpected|should work|should resolve|may interact|may conflict|"
    r"may produce|may break|may be|could interact|could conflict)\b",
    re.IGNORECASE,
)

# Explicit anti-claims (someone already flagged this in the original reason —
# these are authors/curators who themselves said "this isn't a real conflict").
# We keep this narrow to avoid tripping on curator notes that honestly describe
# an entry as "mechanism-verified but not observed" (which is a LEGITIMATE
# use of `mechanism-verified` grade, NOT a speculative downgrade signal).
RE_ANTI = re.compile(
    r"(likely not a real conflict"
    r"|not actually a conflict"
    r"|not a real conflict"
    r"|is untested"
    r"|unverified conflict"
    r"|reported incompat.*but.*not verified)",
    re.IGNORECASE,
)

# Mechanism markers — specific filenames, tp2 line numbers, WeiDU constructs.
# These signal the reason is technically detailed enough to grade as
# mechanism-verified even without session evidence.
RE_MECHANISM = re.compile(
    r"(FORBID_COMPONENT|REQUIRE_PREDICATE|COPY_EXISTING|MOD_IS_INSTALLED|"
    r"DECOMPILE_AND_PATCH|MAKE_BIFF|ACTION_IF|LPF\s+\w+|"
    r"\.(?:spl|itm|cre|bcs|dlg|2da|ids|are|wed|tp2|tph|tpa)\b|"
    r"\bcn:\d+|#\d{3,}|"
    r"cn:\d+|\bSPPR\d+|\bSPWI\d+|\bSPIN\d+|\bSPCL\d+|"
    r"\b[A-Z]{2,5}\d+\.(?:SPL|ITM|CRE|BCS|DLG|2DA|IDS|ARE|WED)\b|"
    r"\btp2 line \d+|\binitialize\.tpa|\balways\.tph)",
    re.IGNORECASE,
)


def grade_entry(entry: dict, kind: str) -> tuple[str, list[str]]:
    """Return (recommended_grade, notes) for one conflict/advisory/ki entry.

    `kind` is "conflict" | "advisory" | "ki" — affects how we evaluate a few
    fields (e.g. ki entries carry `description` instead of `reason`).
    """
    notes: list[str] = []

    # Consolidate the text we search across — most signals could appear in
    # either `reason` (conflict/advisory) or `description` (ki), and sources
    # commonly get attached to either.
    reason_text = entry.get("reason") or entry.get("description") or ""
    source_text = str(entry.get("source") or "")
    combined = f"{reason_text}\n{source_text}"
    severity = (entry.get("severity") or "").lower()
    session_id = entry.get("sessionId")

    # ── Signal extraction ────────────────────────────────────────────────
    has_session_id = bool(session_id and str(session_id).strip())
    # A session-ref is only "observed"-grade if it's a positive claim; an
    # anti-claim in the same text (`NOT observed in session X`) cancels it.
    raw_session_ref = bool(RE_SESSION.search(combined))
    session_negated = bool(RE_SESSION_NEGATION.search(combined))
    has_session_ref = raw_session_ref and not session_negated
    has_speculation = bool(RE_SPECULATION.search(reason_text))
    has_anti = bool(RE_ANTI.search(combined))
    has_mechanism = bool(RE_MECHANISM.search(combined))
    has_source = bool(source_text.strip())

    # ── Grading ladder ───────────────────────────────────────────────────
    if has_session_id:
        notes.append(f"sessionId present: {session_id}")
        return "observed", notes
    if has_session_ref:
        notes.append("session-ref matched in source/reason")
        return "observed", notes
    if has_anti:
        notes.append("anti-claim language present ('likely not a real conflict', etc.)")
        return "speculative", notes
    if has_speculation:
        notes.append("speculation markers: " + ", ".join(sorted({m.lower() for m in RE_SPECULATION.findall(reason_text)})[:5]))
        return "speculative", notes
    if severity == "hard" and has_mechanism:
        notes.append("hard severity + FORBID_COMPONENT/mutex mechanism citation")
        return "mechanism-verified", notes
    if has_mechanism and has_source:
        notes.append("mechanism citation + source attribution")
        return "mechanism-verified", notes
    if has_mechanism:
        notes.append("mechanism citation without explicit source")
        return "mechanism-verified", notes
    if severity == "hard":
        notes.append("hard severity without mechanism citation — likely real but verify")
        return "mechanism-verified", notes
    if reason_text.strip() == "" and not has_source:
        notes.append("empty reason + no source — likely stub")
        return "speculative", notes

    notes.append("no strong signals; needs human review")
    return "unclassified", notes


def decide_action(current: str | None, recommended: str) -> str:
    """Map (current, recommended) to one of keep/upgrade/downgrade/set/review."""
    if recommended == "unclassified":
        return "review"
    if not current:
        return "set"
    # Confidence ladder — higher index = higher confidence.
    order = {"speculative": 0, "mechanism-verified": 1, "observed": 2}
    cur_rank = order.get(current, 0)
    rec_rank = order.get(recommended, 0)
    if cur_rank == rec_rank:
        return "keep"
    return "upgrade" if rec_rank > cur_rank else "downgrade"


def process_mod(path: Path) -> list[dict]:
    """Grade every conflict/advisory/ki entry in one mod file. Returns one
    record per entry (with mod + index + location for later application)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"# parse-fail {path.name}: {e}", file=sys.stderr)
        return []

    mod_id = data.get("i")
    mod_tp2 = data.get("t", path.stem)
    mod_name = data.get("n", mod_tp2)
    records: list[dict] = []

    # Iterate all three arrays under consistent semantics so downstream tools
    # can apply to any of them without special-casing.
    for array_name, kind in [
        ("conflicts",  "conflict"),
        ("advisories", "advisory"),
        ("ki",         "ki"),
    ]:
        for idx, entry in enumerate(data.get(array_name, []) or []):
            current = entry.get("evidenceLevel")
            recommended, notes = grade_entry(entry, kind)
            action = decide_action(current, recommended)
            # Extra suggestion: if the final grade is "speculative" and the
            # entry lives in `conflicts[]`, flag for move to `advisories[]` —
            # that's the structural correction, not just a field update.
            move_suggestion = None
            if array_name == "conflicts" and recommended == "speculative":
                move_suggestion = "advisories"

            records.append({
                "file": path.name,
                "mod_id": mod_id,
                "mod_tp2": mod_tp2,
                "mod_name": mod_name,
                "array": array_name,
                "index": idx,
                "kind": kind,
                "with": entry.get("with") or entry.get("pattern"),
                "severity": entry.get("severity"),
                "orderOnly": bool(entry.get("orderOnly")),
                "currentEvidenceLevel": current,
                "recommendedEvidenceLevel": recommended,
                "action": action,
                "moveToArray": move_suggestion,
                "reasonExcerpt": (entry.get("reason") or entry.get("description") or "")[:180],
                "notes": notes,
            })
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true",
                        help="Reserved for future use; currently a no-op. "
                             "Use apply_conflict_grades.py to apply.")
    args = parser.parse_args()

    records: list[dict] = []
    for path in sorted(MODS_DIR.glob("*.json")):
        records.extend(process_mod(path))

    # ── Summary aggregates ───────────────────────────────────────────────
    by_action: dict[str, int] = {}
    by_recommended: dict[str, int] = {}
    by_array_recommended: dict[str, dict[str, int]] = {}
    to_move: list[dict] = []
    for r in records:
        by_action[r["action"]] = by_action.get(r["action"], 0) + 1
        by_recommended[r["recommendedEvidenceLevel"]] = (
            by_recommended.get(r["recommendedEvidenceLevel"], 0) + 1)
        arr = r["array"]
        by_array_recommended.setdefault(arr, {})
        by_array_recommended[arr][r["recommendedEvidenceLevel"]] = (
            by_array_recommended[arr].get(r["recommendedEvidenceLevel"], 0) + 1)
        if r.get("moveToArray"):
            to_move.append(r)

    summary = {
        "total_entries": len(records),
        "by_action": by_action,
        "by_recommended": by_recommended,
        "by_array_recommended": by_array_recommended,
        "entries_recommended_for_array_move": len(to_move),
    }

    output = {"summary": summary, "entries": records}
    # Force UTF-8 on write — Python's default on Windows is cp1252, which
    # chokes on U+2192 (→) and similar characters that appear liberally in
    # mod reason-texts. Pathlib.write_text honors `encoding=`.
    OUTPUT_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── Human-readable stderr dump ───────────────────────────────────────
    print(f"# scanned {len({r['file'] for r in records})} mod files, "
          f"{len(records)} total entries", file=sys.stderr)
    print(f"# output: {OUTPUT_PATH}", file=sys.stderr)
    print(f"# by action: {by_action}", file=sys.stderr)
    print(f"# by recommended grade: {by_recommended}", file=sys.stderr)
    print(f"# by array & grade: {json.dumps(by_array_recommended)}", file=sys.stderr)
    print(f"# entries flagged to move out of conflicts[]: {len(to_move)}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
