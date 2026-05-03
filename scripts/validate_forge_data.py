#!/usr/bin/env python3
"""validate_forge_data.py — CI guard for the Forge internal data corpus.

Enforces the evidence-grading rules introduced by Phase 1-2 of the 2026-04
conflict-audit plan. Exits non-zero if any violation is found, with a
per-violation message suitable for CI annotation.

## Enforced rules (each is a numbered VLT_NN code)

- **VLT_01** — every `conflicts[]` entry MUST carry `evidenceLevel`.
  Rationale: the whole point of evidence grading is that readers can tell at
  a glance whether an entry is observed or speculative. Ungraded entries
  defeat the purpose. Setting one is cheap; run `scripts/grade_conflicts.py`
  + `scripts/apply_conflict_grades.py` to auto-grade.

- **VLT_02** — a conflicts[] entry MUST NOT have `evidenceLevel: "speculative"`.
  Rationale: speculative entries belong in `advisories[]`. The Forge UI
  renders `conflicts[]` with red/amber urgency — putting unverified claims
  there misleads users and (worse) mod authors, as the 2026-04 Stormlord↔EPS
  case demonstrated.

- **VLT_03** — any entry with `evidenceLevel: "observed"` MUST cite evidence
  via either `sessionId` (non-empty) or `source` (non-empty). The whole
  claim of "observed" means SOMEONE saw the failure fire; the citation is
  how a reviewer verifies the claim. Unverifiable "observed" entries are
  indistinguishable from speculative ones.

- **VLT_04** — `evidenceLevel` value (if present) MUST be one of the three
  enum values. Catches typos like `"mechanism_verified"` (underscore).

- **VLT_05** — `advisories[]` entries MUST carry `evidenceLevel`. Same
  rationale as VLT_01, but advisories legitimately DO include `speculative`
  entries — that's their point.

- **VLT_06** — `ki[]` entries (known-issue patterns) MAY carry
  `evidenceLevel`, and if they do it must be a valid enum value. Not
  currently required since ki entries have a different semantics (they're
  detector patterns, not claims about specific mod pairs).

## Exit codes

- 0 = clean (all rules pass)
- 1 = violations found; stderr has per-violation detail
- 2 = tool-internal error (bad JSON file, etc.)

## Usage

```
python scripts/validate_forge_data.py                 # full corpus scan
python scripts/validate_forge_data.py --only data/mods/Aurora.json
python scripts/validate_forge_data.py --grace-period  # warn on VLT_01 instead
                                                       # of failing; useful
                                                       # during Phase 2 rollout
                                                       # before the corpus is
                                                       # fully graded.
```

## Integration

Hook into `.github/workflows/*.yml` as a required check on PRs:

```yaml
- name: Validate Forge data
  run: python scripts/validate_forge_data.py
```

## Related

- `scripts/grade_conflicts.py` — proposes grades.
- `scripts/apply_conflict_grades.py` — writes them.
- `schemas/forge-internal.schema.json` — structural schema (Phase 1.1).
- `scripts/audit_same_author_conflicts.py` — orthogonal audit for the
  same-author case that kicked off this whole workstream.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(os.environ.get("FORGE_ROOT", "F:/BGMods/eet-mod-forge"))
MODS_DIR = REPO_ROOT / "data" / "mods"

VALID_EVIDENCE_LEVELS = {"observed", "mechanism-verified", "speculative"}


class Violation:
    """One rule failure. Carries the code, path, and message."""

    __slots__ = ("code", "file", "locator", "message")

    def __init__(self, code: str, file: str, locator: str, message: str):
        self.code = code
        self.file = file
        self.locator = locator
        self.message = message

    def __str__(self) -> str:
        return f"{self.code} {self.file}:{self.locator} — {self.message}"


def validate_entry(
    entry: dict,
    file: str,
    array_name: str,
    index: int,
    *,
    grace_period: bool,
) -> list[Violation]:
    """Return zero or more Violations for a single conflict/advisory/ki entry."""
    vs: list[Violation] = []
    loc = f"{array_name}[{index}]"

    grade = entry.get("evidenceLevel")

    # VLT_04 — enum typo guard (applies to any array).
    if grade is not None and grade not in VALID_EVIDENCE_LEVELS:
        vs.append(Violation(
            "VLT_04", file, loc,
            f"evidenceLevel {grade!r} not in enum "
            f"{sorted(VALID_EVIDENCE_LEVELS)}"
        ))
        return vs  # bail early; further rules depend on a valid grade

    if array_name == "conflicts":
        # VLT_01 — must carry evidenceLevel.
        if grade is None:
            severity = "warning" if grace_period else "error"
            vs.append(Violation(
                "VLT_01", file, loc,
                f"[{severity}] conflicts[] entry has no evidenceLevel. "
                f"Run scripts/grade_conflicts.py + apply_conflict_grades.py "
                f"or set manually."
            ))
        # VLT_02 — no speculative entries in conflicts[].
        if grade == "speculative":
            vs.append(Violation(
                "VLT_02", file, loc,
                "evidenceLevel=speculative entries must live in advisories[], "
                "not conflicts[]. Move the entry or upgrade its grade."
            ))

    elif array_name == "advisories":
        # VLT_05 — advisories must also carry evidenceLevel.
        if grade is None:
            severity = "warning" if grace_period else "error"
            vs.append(Violation(
                "VLT_05", file, loc,
                f"[{severity}] advisories[] entry has no evidenceLevel."
            ))

    # VLT_03 — observed entries must cite evidence, regardless of array.
    if grade == "observed":
        has_session = bool((entry.get("sessionId") or "").strip())
        has_source = bool(str(entry.get("source") or "").strip())
        if not (has_session or has_source):
            vs.append(Violation(
                "VLT_03", file, loc,
                "evidenceLevel=observed requires sessionId or source to be "
                "non-empty. An unverifiable 'observed' claim is "
                "indistinguishable from speculation."
            ))

    return vs


def validate_file(path: Path, *, grace_period: bool) -> list[Violation]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [Violation("VLT_00", path.name, "file",
                          f"invalid JSON: {e}")]
    except Exception as e:
        return [Violation("VLT_00", path.name, "file",
                          f"read error: {e}")]

    vs: list[Violation] = []
    for array_name in ("conflicts", "advisories", "ki"):
        for idx, entry in enumerate(data.get(array_name, []) or []):
            if not isinstance(entry, dict):
                continue
            vs.extend(validate_entry(
                entry, path.name, array_name, idx,
                grace_period=grace_period,
            ))
    return vs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", action="append", default=[],
                        help="Only scan this file (repeatable). Path may be "
                             "absolute or relative to repo root.")
    parser.add_argument("--grace-period", action="store_true",
                        help="Emit VLT_01/VLT_05 (missing evidenceLevel) as "
                             "warnings rather than errors. Lets us land the "
                             "CI guard before the corpus is fully graded; "
                             "remove the flag once Phase 2 is complete.")
    args = parser.parse_args()

    if args.only:
        paths = [Path(p) if Path(p).is_absolute() else (REPO_ROOT / p) for p in args.only]
    else:
        paths = sorted(MODS_DIR.glob("*.json"))

    all_vs: list[Violation] = []
    for p in paths:
        all_vs.extend(validate_file(p, grace_period=args.grace_period))

    # Split warnings (grace-period-only) from hard errors so CI can still
    # merge during the rollout window.
    warnings = [v for v in all_vs if "[warning]" in v.message]
    errors = [v for v in all_vs if v not in warnings]

    for v in warnings:
        print(f"::warning file={v.file}::{v}", file=sys.stderr)
    for v in errors:
        print(f"::error file={v.file}::{v}", file=sys.stderr)

    # Counts by code for the summary line.
    counts: dict[str, int] = {}
    for v in all_vs:
        counts[v.code] = counts.get(v.code, 0) + 1

    if all_vs:
        print(f"# {len(all_vs)} violations ({len(errors)} error, "
              f"{len(warnings)} warning) across {len({v.file for v in all_vs})} "
              f"files: {counts}", file=sys.stderr)
    else:
        print(f"# clean: {len(paths)} files scanned, no violations",
              file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
