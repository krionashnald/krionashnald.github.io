#!/usr/bin/env python3
"""
Audit `wp` (WeiDU path) values in data/mods/*.json against the extracted mod directory.

Catches the class of bug where a component's `wp` points to a tp2 that doesn't
actually exist in the mod — e.g. `"wp": "klatu\\klatu.tp2"` when the actual
filename is `klatu\\setup-klatu.tp2`. WeiDU FATAL-errors on those (Sys_error:
No such file or directory) but exits 0 on the mod_installer runner, so the
failure looks like a silent skip rather than a fatal error.

Usage:
    python audit_wp_paths.py [extracted_dir]
    python audit_wp_paths.py F:/BGMods/Extracted --fix    # rewrite with the correct setup-*.tp2 name

Output: one line per bad `wp` with suggested replacement. Exit code 1 if any
found (so this can gate CI).
"""
import json
import os
import sys
import argparse
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "mods"


def find_tp2s(mod_root: Path, mod_folder: str):
    """Return list of tp2 Paths belonging to a given mod_folder. Searches:
      1. extracted/<mod_folder>/*.tp2         (direct: e.g. iwdification)
      2. extracted/*/<mod_folder>/*.tp2       (nested: e.g. Klatu*/klatu)
      3. extracted/*/*.tp2 where tp2 name matches <mod_folder>
         (top-of-parent: e.g. IWDification/setup-iwdification.tp2)

    All filesystem matches are case-insensitive on Windows.
    """
    mf_lower = mod_folder.lower()
    matches = []
    try:
        # 1. Direct child directory match.
        for child in mod_root.iterdir():
            if not child.is_dir() or child.name.lower() != mf_lower:
                continue
            for p in child.glob("*.tp2"):
                matches.append(p)
            # 2. Nested: extracted/<mod_folder>/... may still have tp2 deeper,
            #    but that's unusual — skip.

        # 3. Nested namespaced: extracted/<ParentDir>/<mod_folder>/*.tp2
        # 4. Top-of-parent: extracted/<ParentDir>/*.tp2 where the basename
        #    (minus setup- prefix) matches mod_folder.
        for parent in mod_root.iterdir():
            if not parent.is_dir():
                continue
            # Skip if this parent IS the mod_folder (already handled in #1).
            if parent.name.lower() == mf_lower:
                continue
            # Nested case
            for child in parent.iterdir():
                if not child.is_dir():
                    continue
                if child.name.lower() == mf_lower:
                    for p in child.glob("*.tp2"):
                        matches.append(p)
            # Top-of-parent case: parent/*.tp2 where tp2 filename's mod-name
            # (after stripping setup- prefix, before .tp2) matches mod_folder.
            for p in parent.glob("*.tp2"):
                bn = p.stem.lower()  # filename without extension
                # Strip setup- prefix if present
                if bn.startswith("setup-"):
                    bn = bn[len("setup-"):]
                elif bn.startswith("setup_"):
                    bn = bn[len("setup_"):]
                if bn == mf_lower:
                    matches.append(p)
    except (OSError, PermissionError):
        pass
    # Dedupe by absolute path (case-insensitive on Windows)
    seen = set()
    out = []
    for p in matches:
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def audit_file(path: Path, mod_root: Path):
    """Return list of (component_index, current_wp, suggested_wp) for bad wp
    entries in `path`. Empty list means clean."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return [(None, None, f"ERROR reading {path}: {e}")]

    mod_folder = data.get("t")
    if not mod_folder:
        return []

    tp2_files = find_tp2s(mod_root, mod_folder)
    if not tp2_files:
        # No tp2 on disk — can't validate. Not an error per se; the mod may
        # just not be extracted yet.
        return []

    # Build set of valid basename (lowercase, no path) → actual on-disk name
    # (preserving whatever case convention the on-disk file uses).
    valid_basenames = {p.name.lower(): p.name for p in tp2_files}

    components = data.get("co") or []
    bad = []
    for i, comp in enumerate(components):
        wp = comp.get("wp")
        if not isinstance(wp, str):
            continue
        bn = wp.replace("\\", "/").split("/")[-1]
        if bn.lower() not in valid_basenames:
            # Suggest the setup-*.tp2 if present, else the first tp2 found.
            setup = next((n for n in valid_basenames.values()
                          if n.lower().startswith("setup-")), None)
            suggested_name = setup or next(iter(valid_basenames.values()))
            suggested_wp = f"{mod_folder}\\{suggested_name}"
            bad.append((i, wp, suggested_wp))
    return bad


def main():
    parser = argparse.ArgumentParser(description="Audit wp paths in mod data")
    parser.add_argument("extracted_dir", nargs="?",
                        default="F:/BGMods/Extracted",
                        help="Extracted mod root (default F:/BGMods/Extracted)")
    parser.add_argument("--fix", action="store_true",
                        help="Rewrite bad wp entries with the suggested value")
    parser.add_argument("--only", metavar="MOD",
                        help="Audit only this mod (by tp2 folder name)")
    args = parser.parse_args()

    mod_root = Path(args.extracted_dir)
    if not mod_root.is_dir():
        print(f"Error: extracted dir not found: {mod_root}", file=sys.stderr)
        return 2

    any_bad = False
    for json_path in sorted(DATA_DIR.glob("*.json")):
        if args.only and json_path.stem != args.only:
            continue
        bad = audit_file(json_path, mod_root)
        if not bad:
            continue
        print(f"\n{json_path.name}:")
        for idx, current, suggested in bad:
            any_bad = True
            if idx is None:
                print(f"  {suggested}")
                continue
            print(f"  [co #{idx}] current={current!r} suggested={suggested!r}")

        if args.fix:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            for idx, current, suggested in bad:
                if idx is None:
                    continue
                data["co"][idx]["wp"] = suggested
            json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"  -> rewrote {json_path.name} with {len(bad)} fixes")

    if any_bad and not args.fix:
        print("\nRun with --fix to apply suggestions.", file=sys.stderr)
        return 1
    if not any_bad:
        print("All wp paths audit-clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
