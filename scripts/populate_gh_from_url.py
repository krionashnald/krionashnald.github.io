#!/usr/bin/env python3
"""
Populate gh.o (owner) and gh.r (repo) on per-mod detail files by parsing
github.com URLs from the existing `u` / `dl` / `hm` fields.

Motivation: scripts/scan_versions.py only probes the GitHub API for mods
that have both `gh.o` and `gh.r` set. Many mods have their GitHub URL
recorded in `u` (homepage) or `dl` (download URL) but were never given
an explicit `gh` block, so the weekly version scan skipped them.

This script bridges the gap. Safe to rerun — only touches mods missing
either `gh.o` or `gh.r`, and preserves any pre-existing fields under `gh`.

Usage:
    python scripts/populate_gh_from_url.py            # dry run (default)
    python scripts/populate_gh_from_url.py --write    # apply changes

Skips (reports as unreachable):
  - mods whose only URL host is gitlab.com or another non-GitHub forge
  - mods whose GitHub URL points at a user page (no repo segment)
  - mods where both gh.o and gh.r are already populated

Priority of fields scanned: u > dl > hm (first match wins).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODS_DIR = ROOT / "data" / "mods"

# Match github.com/<owner>/<repo>, stopping at /, ?, #, or end. Captures
# owner and repo. Tolerates trailing .git and .git/ suffixes.
GITHUB_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([^/\s?#]+)/([^/\s?#]+?)(?:\.git)?/?(?:[?#].*)?$",
    re.IGNORECASE,
)
# Fallback for URLs like github.com/owner/repo/releases/download/v1/file.zip
# where the path continues past the repo segment.
GITHUB_RE_EMBEDDED = re.compile(
    r"github\.com/([^/\s?#]+)/([^/\s?#]+?)(?:\.git)?(?:/|$|[?#])",
    re.IGNORECASE,
)


def extract_owner_repo(url: str) -> tuple[str, str] | None:
    if not url or not isinstance(url, str):
        return None
    m = GITHUB_RE.match(url.strip())
    if m:
        return m.group(1), m.group(2).rstrip(".")
    m = GITHUB_RE_EMBEDDED.search(url)
    if m:
        return m.group(1), m.group(2).rstrip(".")
    return None


def find_github_url(mod: dict) -> tuple[str, str, str] | None:
    """Return (field, url, matched) or None. Fields checked in priority order."""
    for field in ("u", "dl", "hm"):
        v = mod.get(field)
        if isinstance(v, str) and "github.com/" in v.lower():
            result = extract_owner_repo(v)
            if result:
                owner, repo = result
                return field, v, f"{owner}/{repo}"
    return None


def main() -> int:
    write = "--write" in sys.argv
    mode = "WRITE" if write else "DRY RUN"
    print(f"=== populate_gh_from_url.py ({mode}) ===")

    updated = []
    already_complete = 0
    no_github_url = []
    weird = []

    mod_files = sorted(p for p in MODS_DIR.glob("*.json") if p.name != "_catalog.json")
    for path in mod_files:
        with path.open(encoding="utf-8") as f:
            mod = json.load(f)

        gh = mod.get("gh") if isinstance(mod.get("gh"), dict) else None
        has_o = bool(gh and gh.get("o"))
        has_r = bool(gh and gh.get("r"))

        if has_o and has_r:
            already_complete += 1
            continue

        found = find_github_url(mod)
        if found is None:
            # Only report if there's no other host-based source either —
            # weaselmods/G3/etc. mods are expected to lack gh.
            if not any(isinstance(mod.get(k), str) and mod.get(k) for k in ("u", "dl", "hm")):
                weird.append(path.name)
            else:
                no_github_url.append(path.name)
            continue

        field, url, match = found
        owner, repo = match.split("/", 1)

        # Preserve any pre-existing gh fields; only fill gaps.
        new_gh = dict(gh) if gh else {}
        if not has_o:
            new_gh["o"] = owner
        if not has_r:
            new_gh["r"] = repo

        mod["gh"] = new_gh
        updated.append((path.name, field, url, f"{new_gh['o']}/{new_gh['r']}"))

        if write:
            with path.open("w", encoding="utf-8", newline="\n") as f:
                json.dump(mod, f, indent=2, ensure_ascii=False)
                f.write("\n")

    print(f"\nTotal mod files:                 {len(mod_files)}")
    print(f"Already had gh.o + gh.r:         {already_complete}")
    print(f"Would update (will update):      {len(updated)}")
    print(f"Have URL but no github.com URL:  {len(no_github_url)}")
    print(f"No URL fields at all:            {len(weird)}")

    if updated:
        print(f"\n--- Updates ({min(len(updated), 20)} shown of {len(updated)}) ---")
        for fname, field, url, match in updated[:20]:
            print(f"  {fname:38s}  from {field:>2}  ->  {match}")
        if len(updated) > 20:
            print(f"  ... plus {len(updated) - 20} more")

    if weird:
        print(f"\n--- Mods with no URL fields (verify manually) ---")
        for n in weird[:10]:
            print(f"  {n}")

    if not write:
        print(f"\nDry run complete. Rerun with --write to apply.")
    else:
        print(f"\nApplied. Rerun `python scripts/build_index.py --write` to refresh the index.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
