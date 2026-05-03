#!/usr/bin/env python3
"""audit_same_author_conflicts.py — surface conflict entries where both sides
are authored by the same person.

Motivation: the 2026-04-21 Stormlord↔EPS audit revealed that morpheus562's
`enhanced-powergaming-scripts.json` listed a soft-severity conflict with
`morpheus562-s-kitpack` — both mods are his own work. Same-author entries have
a much higher false-positive rate than cross-author ones: authors don't
typically ship self-conflicting mods, and the "conflict" is usually an artifact
of a third mod's intermediation (like mih_metamod cn:4 cleanup) combined with
speculative reasoning.

This script walks `data/mods/*.json`, builds an (tp2 → author) index, and for
every `conflicts[]` entry it checks whether the target mod shares the parent's
primary author. Output is a tab-separated list ready for manual review.

Usage
-----
    python scripts/audit_same_author_conflicts.py > audit_report.tsv

Columns
-------
    parent_mod  parent_author  other_mod  other_author  severity  evidence  reason_excerpt

Fields `evidence` reflects the new `evidenceLevel` property added in the
Phase 1.1 schema update. Missing values show as "-".

Exit status
-----------
    0 — no same-author conflicts found
    N — number of same-author conflicts found (surface-level; manual review
        decides per-entry fate)
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

# Forge repo root; overridable via env so the script can run from any cwd
# (e.g. from a worktree).
REPO_ROOT = Path(os.environ.get("FORGE_ROOT", "F:/BGMods/eet-mod-forge"))
MODS_DIR = REPO_ROOT / "data" / "mods"


def norm_author(au: str | None) -> str:
    """Normalise an author handle for comparison.

    Authors are sometimes "morpheus562", sometimes "Morpheus562" or
    "morpheus562 <email>". We lowercase and strip surrounding whitespace so
    minor formatting drift doesn't hide matches.
    """
    if not au:
        return ""
    return au.strip().lower()


def load_mods() -> dict[int, dict]:
    """Load every data/mods/*.json keyed by Forge ID.

    Silently skips non-mod index files (anything without a numeric `i`).
    """
    mods = {}
    for path in sorted(glob.glob(str(MODS_DIR / "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception as e:
            print(f"# parse-fail {path}: {e}", file=sys.stderr)
            continue
        mid = d.get("i")
        if isinstance(mid, int):
            mods[mid] = d
    return mods


def main() -> int:
    mods = load_mods()

    # Index: Forge ID → author handle (normalised). Used to look up the author
    # of a conflict target. Falls back to `a` (full attribution) when `au`
    # (handle) is missing — some older mod entries only carry `a`.
    author_index: dict[int, str] = {}
    for mid, d in mods.items():
        au = norm_author(d.get("au") or d.get("a"))
        if au:
            author_index[mid] = au

    hits = []
    for mid, d in mods.items():
        my_author = norm_author(d.get("au") or d.get("a"))
        if not my_author:
            continue
        for c in d.get("conflicts", []):
            other_id = c.get("withId")
            if not isinstance(other_id, int):
                continue
            other_author = author_index.get(other_id, "")
            if not other_author or other_author != my_author:
                continue
            hits.append({
                "parent_mod": d.get("t", f"id{mid}"),
                "parent_author": my_author,
                "other_mod": c.get("with", f"id{other_id}"),
                "other_author": other_author,
                "severity": c.get("severity", "?"),
                "evidence": c.get("evidenceLevel", "-"),
                "reason": (c.get("reason") or "")[:120].replace("\t", " ").replace("\n", " "),
            })

    # Emit TSV. Print a header so humans can read it at a glance; downstream
    # tooling can parse the fixed column order.
    print("parent_mod\tparent_author\tother_mod\tother_author\tseverity\tevidence\treason_excerpt")
    for h in hits:
        print(
            f"{h['parent_mod']}\t{h['parent_author']}\t{h['other_mod']}\t"
            f"{h['other_author']}\t{h['severity']}\t{h['evidence']}\t{h['reason']}"
        )

    # Summary to stderr so stdout stays machine-readable.
    print(f"# scanned {len(mods)} mod JSON files", file=sys.stderr)
    print(f"# same-author conflict entries: {len(hits)}", file=sys.stderr)

    return len(hits)


if __name__ == "__main__":
    sys.exit(main())
