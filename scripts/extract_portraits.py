#!/usr/bin/env python3
"""
Extract portrait BMP files from mods in F:/BGMods/Extracted/ and convert
them to PNG for use in infinity-mod-forge's portrait system.

Usage:
    python scripts/extract_portraits.py --dry-run    # preview what would be extracted
    python scripts/extract_portraits.py --write       # extract and convert portraits
    python scripts/extract_portraits.py --write --mod Kelsey  # single mod only
"""

import json
import argparse
import struct
from pathlib import Path

EXTRACTED_DIR = Path("F:/BGMods/Extracted")
ROOT = Path(__file__).resolve().parents[1]
MODS_DIR = ROOT / "data" / "mods"
PORTRAITS_DIR = ROOT / "portraits"
NPCS_FILE = ROOT / "data" / "npcs.json"

# Try to use Pillow for BMP->PNG conversion
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def load_npcs():
    """Load NPC definitions for ID matching."""
    with open(NPCS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_mod_index():
    """Build a mapping of tp2 folder name -> mod JSON data."""
    mods = {}
    for p in MODS_DIR.glob("*.json"):
        if p.name in ("_catalog.json",):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        # Get tp2 folder name from first component's wf field
        tp2 = data.get("t", "")
        if not tp2:
            continue
        mods[tp2.lower()] = {
            "file": p,
            "data": data,
            "has_pt": "pt" in data,
        }
        # Also index by wf from components
        for comp in data.get("co", []):
            wf = comp.get("wf", "").lower()
            if wf and wf not in mods:
                mods[wf] = mods[tp2.lower()]
    return mods


def find_extracted_dir_for_mod(mod_data, extracted_dirs):
    """Try to match a mod JSON entry to an extracted directory."""
    tp2 = mod_data.get("t", "").lower()
    name = mod_data.get("n", "").lower()

    # Check component wf fields for folder names
    wf_names = set()
    for comp in mod_data.get("co", []):
        wf = comp.get("wf", "")
        if wf:
            wf_names.add(wf.lower())

    for edir in extracted_dirs:
        edir_lower = edir.name.lower()
        # Direct name match
        if edir_lower == tp2:
            return edir
        # Check if any subdirectory matches tp2 or wf
        for sub in edir.iterdir():
            if sub.is_dir():
                sub_lower = sub.name.lower()
                if sub_lower == tp2 or sub_lower in wf_names:
                    return edir
        # Fuzzy: check if extracted dir name contains the mod name
        if tp2 in edir_lower.replace(" ", "").replace("-", "").replace("_", ""):
            return edir

    return None


def find_portrait_bmps(mod_dir):
    """Find all portrait BMP files in a mod directory.
    Returns dict of {base_name: {size: bmp_path}}.
    Portraits follow IE conventions: *L.bmp (large), *M.bmp (medium), *S.bmp (small).
    Only looks in portrait-likely directories, skipping items/creatures/etc.
    """
    # Directories that commonly contain portraits
    PORTRAIT_DIRS = {"portraits", "portrait", "images", "bmp"}
    # Directories to skip
    SKIP_DIRS = {"backup", "items", "creatures", "spells", "store",
                 "scripts", "dialogue", "tra", "lang", "audio", "sounds",
                 "areas", "worldmap", "gui", "movies", "music", "override",
                 ".git", "baf", "d", "tph", "lib"}

    portraits = {}

    for bmp in mod_dir.rglob("*.bmp"):
        name = bmp.stem
        if len(name) < 2:
            continue

        # Skip files in non-portrait directories
        rel_parts = set(p.lower() for p in bmp.relative_to(mod_dir).parts[:-1])
        if rel_parts & SKIP_DIRS:
            continue

        # Prefer files in portrait-named directories
        in_portrait_dir = bool(rel_parts & PORTRAIT_DIRS)

        suffix = name[-1].upper()
        if suffix in ("L", "M", "S"):
            base = name[:-1]
            # IE portrait names are typically 2-8 chars (before L/M/S suffix)
            if len(base) < 2 or len(base) > 12:
                continue
            if base not in portraits:
                portraits[base] = {}
            portraits[base][suffix] = bmp

        # Also check for EE-style naming (_330, _266, etc.)
        for ee_suffix, ee_type in [("_330", "L"), ("_266", "M"), ("_170", "M"),
                                     ("_84", "S"), ("_60", "S")]:
            if name.endswith(ee_suffix):
                base = name[: -len(ee_suffix)]
                # Strip trailing L/M/S if present (EE files keep the IE suffix)
                if base and base[-1].upper() in ("L", "M", "S") and len(base) > 2:
                    base = base[:-1]
                if len(base) < 2 or len(base) > 12:
                    continue
                if base not in portraits:
                    portraits[base] = {}
                if ee_type not in portraits[base]:
                    portraits[base][ee_type] = bmp

    # Filter: only keep portraits that have at least L (large) size
    # or are in a portrait directory
    filtered = {}
    for base, sizes in portraits.items():
        if "L" in sizes:
            filtered[base] = sizes
    return filtered


def sanitize_portrait_name(name):
    """Convert a BMP portrait name to a clean PNG filename."""
    # Replace special chars used in IE filenames
    clean = name.lower().replace("#", "_").replace("!", "_").replace("@", "_")
    return clean


def convert_bmp_to_png(bmp_path, png_path):
    """Convert a BMP file to PNG using Pillow."""
    if not HAS_PIL:
        return False
    try:
        img = Image.open(bmp_path)
        img.save(png_path, "PNG")
        return True
    except Exception as e:
        print(f"  WARNING: Failed to convert {bmp_path}: {e}")
        return False


def guess_npc_id(portrait_name, npcs, mod_tp2):
    """Try to guess the NPC ID from a portrait filename."""
    clean = portrait_name.lower().replace("#", "_").replace("!", "_")

    # Direct match in npcs.json
    for npc_id, npc_data in npcs.items():
        default = npc_data.get("default", "")
        # Check if the portrait filename matches the default portrait filename
        if default:
            default_stem = Path(default).stem.lower()
            if clean == default_stem:
                return npc_id

    # Common prefixes that indicate the mod's custom NPC
    # e.g., rh#adrl -> rh_adr -> adrian_npc
    # This is hard to automate, so we flag for manual review
    return None


def guess_phase(mod_data):
    """Guess the game phase from mod category."""
    cat = mod_data.get("c", "").upper()
    cats = [c.upper() for c in mod_data.get("cats", []) if c]
    all_cats = [cat] + cats

    for c in all_cats:
        if "BG1" in c:
            return "bg1"
        if "SOD" in c:
            return "sod"
        if "TOB" in c:
            return "tob"
    return "bg2"  # default


def main():
    parser = argparse.ArgumentParser(description="Extract portraits from mods")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    parser.add_argument("--write", action="store_true", help="Write files")
    parser.add_argument("--mod", type=str, help="Process single mod by extracted dir name")
    parser.add_argument("--skip-existing", action="store_true", default=True,
                        help="Skip mods that already have pt data (default: true)")
    args = parser.parse_args()

    if not args.dry_run and not args.write:
        print("Specify --dry-run or --write")
        return

    if not HAS_PIL and args.write:
        print("ERROR: Pillow (PIL) required for --write mode. Install with: pip install Pillow")
        return

    npcs = load_npcs()
    mod_index = load_mod_index()

    # Get all extracted directories
    extracted_dirs = sorted([d for d in EXTRACTED_DIR.iterdir() if d.is_dir()])
    if args.mod:
        extracted_dirs = [d for d in extracted_dirs if args.mod.lower() in d.name.lower()]

    stats = {"processed": 0, "skipped_has_pt": 0, "skipped_no_portraits": 0,
             "extracted": 0, "manual_review": 0, "no_mod_match": 0}

    results = []

    for edir in extracted_dirs:
        # Find portrait BMPs
        portraits = find_portrait_bmps(edir)
        if not portraits:
            continue

        # Try to match to a mod in our database
        matched_mod = None
        matched_key = None
        for key, mod_info in mod_index.items():
            test_dir = find_extracted_dir_for_mod(mod_info["data"], [edir])
            if test_dir:
                matched_mod = mod_info
                matched_key = key
                break

        if not matched_mod:
            stats["no_mod_match"] += 1
            if len(portraits) > 0:
                print(f"\n  NO MOD MATCH: {edir.name} ({len(portraits)} portraits)")
                for pname in sorted(portraits.keys())[:5]:
                    print(f"    - {pname}")
                if len(portraits) > 5:
                    print(f"    ... and {len(portraits) - 5} more")
            continue

        # Skip if mod already has pt data
        if args.skip_existing and matched_mod["has_pt"]:
            stats["skipped_has_pt"] += 1
            continue

        stats["processed"] += 1
        mod_data = matched_mod["data"]
        mod_file = matched_mod["file"]
        tp2 = mod_data.get("t", "")
        phase = guess_phase(mod_data)

        # Determine output directory name
        out_dir_name = tp2.lower().replace("-", "_").replace(" ", "_")
        out_dir = PORTRAITS_DIR / out_dir_name

        print(f"\n{'='*60}")
        print(f"MOD: {mod_data.get('n', tp2)} (tp2: {tp2})")
        print(f"  Source: {edir.name}")
        print(f"  Category: {mod_data.get('c', '?')} -> Phase: {phase}")
        print(f"  Output dir: portraits/{out_dir_name}/")
        print(f"  Portraits found: {len(portraits)}")

        # Check if output dir already exists with files
        existing_pngs = set()
        if out_dir.exists():
            existing_pngs = {p.stem for p in out_dir.glob("*.png")}
            if existing_pngs:
                print(f"  Existing PNGs in output dir: {len(existing_pngs)}")

        # For results tracking, don't skip existing files
        skip_existing_for_results = False

        pt_entries = []
        needs_review = []

        for pname, sizes in sorted(portraits.items()):
            # Use large portrait if available, else medium
            bmp_path = sizes.get("L") or sizes.get("M")
            if not bmp_path:
                continue

            clean_name = sanitize_portrait_name(pname)
            png_name = f"{clean_name}.png"

            # Track whether this is a new extraction or existing
            already_exists = clean_name in existing_pngs

            # Try to guess NPC ID
            npc_id = guess_npc_id(pname, npcs, tp2)

            if npc_id:
                pt_entries.append({
                    "npc_id": npc_id,
                    "path": f"portraits/{out_dir_name}/{png_name}",
                    "phase": phase,
                    "auto": True,
                })
            else:
                needs_review.append({
                    "portrait_name": pname,
                    "clean_name": clean_name,
                    "path": f"portraits/{out_dir_name}/{png_name}",
                    "phase": phase,
                    "bmp": str(bmp_path),
                })

            if args.write and not already_exists:
                out_dir.mkdir(parents=True, exist_ok=True)
                png_path = out_dir / png_name
                if not png_path.exists():
                    if convert_bmp_to_png(bmp_path, png_path):
                        stats["extracted"] += 1

        # Print results
        if pt_entries:
            print(f"  Auto-matched NPC portraits: {len(pt_entries)}")
            for entry in pt_entries:
                print(f"    [{entry['npc_id']}] -> {entry['path']} ({entry['phase']})")

        if needs_review:
            stats["manual_review"] += len(needs_review)
            print(f"  NEEDS MANUAL NPC ID ASSIGNMENT: {len(needs_review)}")
            for entry in needs_review:
                print(f"    {entry['portrait_name']} -> {entry['path']}")

        results.append({
            "mod": tp2,
            "mod_name": mod_data.get("n", ""),
            "mod_file": str(mod_file),
            "out_dir": out_dir_name,
            "phase": phase,
            "auto_matched": pt_entries,
            "needs_review": needs_review,
        })

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"  Mods processed: {stats['processed']}")
    print(f"  Skipped (already has pt): {stats['skipped_has_pt']}")
    print(f"  No mod match in database: {stats['no_mod_match']}")
    print(f"  Portraits extracted: {stats['extracted']}")
    print(f"  Portraits needing manual review: {stats['manual_review']}")

    # Write results JSON for reference
    if args.write and results:
        results_file = MODS_DIR.parent / "portrait_extraction_results.json"
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n  Results saved to: {results_file}")


if __name__ == "__main__":
    main()
