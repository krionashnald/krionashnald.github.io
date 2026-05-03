#!/usr/bin/env python3
"""apply_conflict_grades.py — write `evidenceLevel` onto conflict/advisory/ki
entries based on the report produced by `scripts/grade_conflicts.py`.

## Workflow

1. Run `python scripts/grade_conflicts.py` to regenerate
   `scripts/grade_conflicts.result.json`.
2. Run `python scripts/apply_conflict_grades.py --dry-run` to preview.
3. Spot-check the dry-run output against a handful of entries.
4. Run `python scripts/apply_conflict_grades.py --apply` to write changes.

## What gets applied

By default this tool applies these actions from the report:

- **`set`**: entry has no `evidenceLevel`; write the recommended value.
- **`upgrade`**: entry's grade is lower-confidence than the recommendation;
  overwrite it.
- **`downgrade`**: entry's grade is higher-confidence than recommended;
  overwrite it. Optionally also moves the entry from `conflicts[]` to
  `advisories[]` when the report flagged `moveToArray: "advisories"` (this is
  the structural fix the Stormlord↔EPS case demonstrated).

It does NOT touch:

- `keep`: grade already matches recommendation.
- `review`: recommendation is `unclassified`; skip — needs human eyes.

Filters are available to scope the run (e.g. `--only-action downgrade`,
`--only-array conflicts`) so reviewers can apply piecemeal with confidence.

## Safety

- Dry-run is the default when `--apply` is not set.
- Every mutation is preceded by a backup write to `{filename}.grade-backup`
  (unless `--no-backup`). The backup is a single file, overwritten on each
  run, so reviewers can always `git diff` against HEAD if they've lost the
  previous backup.
- No entries are deleted. The only structural change is moving from one
  array to another (`conflicts[] → advisories[]`).
- Arrays are created on-demand if missing.

## Usage

```
python scripts/apply_conflict_grades.py --dry-run
python scripts/apply_conflict_grades.py --apply
python scripts/apply_conflict_grades.py --apply --only-action set
python scripts/apply_conflict_grades.py --apply --only-action downgrade \
    --only-array conflicts
```
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(os.environ.get("FORGE_ROOT", "F:/BGMods/eet-mod-forge"))
MODS_DIR = REPO_ROOT / "data" / "mods"
REPORT_PATH = REPO_ROOT / "scripts" / "grade_conflicts.result.json"


def load_report() -> dict:
    if not REPORT_PATH.exists():
        sys.exit(f"report not found at {REPORT_PATH} — run grade_conflicts.py first")
    with open(REPORT_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_mod_file(name: str) -> dict:
    with open(MODS_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def save_mod_file(name: str, data: dict, *, backup: bool) -> None:
    path = MODS_DIR / name
    if backup:
        bk = path.with_suffix(path.suffix + ".grade-backup")
        # Preserve pre-change content so reviewers can diff/restore.
        # Overwriting the backup on each run is intentional — git is the
        # source of truth for long-term history.
        if path.exists():
            with open(path, encoding="utf-8") as src, open(bk, "w", encoding="utf-8") as dst:
                dst.write(src.read())
    with open(path, "w", encoding="utf-8") as f:
        # Preserve existing formatting conventions: 2-space indent,
        # ensure_ascii=False so non-ASCII mod strings round-trip.
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def apply_entry(
    mod_data: dict,
    rec: dict,
    *,
    do_move: bool,
) -> tuple[bool, str]:
    """Apply one recommendation to `mod_data` (in-place). Returns
    (changed, description).

    The report identifies entries by (array, index); we validate the array
    still exists and the index still points to the same `with`/`pattern`
    target before mutating, to catch any stale-report scenarios.
    """
    arr_name = rec["array"]
    idx = rec["index"]
    array = mod_data.get(arr_name) or []
    if idx >= len(array):
        return False, f"skip (index {idx} out of range on {arr_name}[])"

    entry = array[idx]
    # Sanity check — make sure the entry is still the one the report graded.
    report_target = rec.get("with")
    entry_target = entry.get("with") or entry.get("pattern")
    if report_target and entry_target and report_target != entry_target:
        return False, (
            f"skip (target drift: report said {report_target!r}, "
            f"entry has {entry_target!r})"
        )

    recommended = rec["recommendedEvidenceLevel"]
    current = entry.get("evidenceLevel")

    changed = False
    actions: list[str] = []

    # Write evidenceLevel if different.
    if current != recommended:
        entry["evidenceLevel"] = recommended
        changed = True
        actions.append(f"evidenceLevel: {current!r} -> {recommended!r}")

    # Move to `advisories[]` when the grader flagged it and the caller opted
    # in. Never move ki entries or already-advisory entries.
    if (do_move
        and rec.get("moveToArray") == "advisories"
        and arr_name == "conflicts"):
        # Pop from conflicts[], append to advisories[] (create if absent).
        popped = array.pop(idx)
        mod_data.setdefault("advisories", []).append(popped)
        # Clean up an empty conflicts[] to avoid churn but keep it present
        # (it's structurally expected by consumers).
        actions.append("moved conflicts[] -> advisories[]")
        changed = True

    if not changed:
        return False, "no-op (already matches recommendation)"
    return True, ", ".join(actions)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Preview without writing (default).")
    parser.add_argument("--apply", action="store_true",
                        help="Write changes to disk. Overrides --dry-run.")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip writing .grade-backup files when applying.")
    parser.add_argument("--only-action", action="append", default=[],
                        choices=["set", "upgrade", "downgrade", "keep", "review"],
                        help="Only apply entries with these actions. Repeatable.")
    parser.add_argument("--only-array", action="append", default=[],
                        choices=["conflicts", "advisories", "ki"],
                        help="Only apply entries in these arrays. Repeatable.")
    parser.add_argument("--move-to-advisories", action="store_true", default=True,
                        help="When a conflicts[] entry is recommended as speculative, "
                             "also move it to advisories[] (default). Disable with "
                             "--no-move.")
    parser.add_argument("--no-move", dest="move_to_advisories", action="store_false",
                        help="Skip the conflicts[] -> advisories[] structural move. "
                             "Only update evidenceLevel in place.")
    args = parser.parse_args()

    dry_run = not args.apply
    only_action = set(args.only_action) if args.only_action else None
    only_array = set(args.only_array) if args.only_array else None

    report = load_report()
    records = report["entries"]

    # Default filter: apply set/upgrade/downgrade, skip keep/review. When the
    # user passes --only-action explicitly that overrides this default.
    if only_action is None:
        only_action = {"set", "upgrade", "downgrade"}

    # Group recommendations by file so we open each file once.
    by_file: dict[str, list[dict]] = {}
    for r in records:
        if r["action"] not in only_action:
            continue
        if only_array is not None and r["array"] not in only_array:
            continue
        by_file.setdefault(r["file"], []).append(r)

    # Within each file, apply in descending array index order so that popping
    # entries from conflicts[] doesn't shift indices for later ops.
    total_changed = 0
    total_files = 0
    for fname, recs in sorted(by_file.items()):
        mod_data = load_mod_file(fname)
        recs_sorted = sorted(recs, key=lambda r: (r["array"], -r["index"]))
        file_changes: list[str] = []
        for rec in recs_sorted:
            changed, desc = apply_entry(
                mod_data, rec, do_move=args.move_to_advisories
            )
            tag = "  [CHANGE]" if changed else "  [skip]  "
            file_changes.append(
                f"{tag} {rec['array']}[{rec['index']}] with={rec.get('with')!r}: "
                f"{desc} (action={rec['action']}, current={rec['currentEvidenceLevel']}, "
                f"rec={rec['recommendedEvidenceLevel']})"
            )
            if changed:
                total_changed += 1

        if any(ln.startswith("  [CHANGE]") for ln in file_changes):
            total_files += 1
            print(f"{fname}:")
            for ln in file_changes:
                print(ln)
            if not dry_run:
                save_mod_file(fname, mod_data, backup=not args.no_backup)

    verb = "would apply" if dry_run else "applied"
    print(f"\n# {verb} {total_changed} changes across {total_files} files",
          file=sys.stderr)
    if dry_run:
        print("# dry-run: no files written. Re-run with --apply to commit.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
