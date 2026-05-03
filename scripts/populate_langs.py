#!/usr/bin/env python3
"""
Parse WeiDU TP2 LANGUAGE directives from extracted mods and populate
'langs' field in mod JSON files.

Usage:
    python scripts/populate_langs.py --dry-run    # preview changes
    python scripts/populate_langs.py --write      # write changes
"""

import re
import json
import sys
import argparse
from pathlib import Path

EXTRACTED_DIR = Path("F:/BGMods/Extracted")
MODS_DIR = Path(__file__).resolve().parents[1] / "data" / "mods"

# Map WeiDU language folder names to ISO 639-1 codes
FOLDER_TO_ISO = {
    "english": "en", "american": "en", "enus": "en",
    "englishrevision": "en", "englishoriginal": "en",
    "french": "fr", "francais": "fr", "frfr": "fr",
    "german": "de", "deutsch": "de", "dede": "de",
    "shgerman": "de", "germansh": "de",
    "spanish": "es", "espanol": "es", "eses": "es",
    "castilian": "es", "castellano": "es",
    "italian": "it", "italiano": "it",
    "polish": "pl", "polski": "pl", "plpl": "pl",
    "russian": "ru", "ruru": "ru",
    "czech": "cs", "cscz": "cs", "cesky": "cs",
    "korean": "ko",
    "japanese": "ja", "japan": "ja",
    "portuguese": "pt", "brazilian": "pt-br",
    "brazilian_portuguese": "pt-br", "brazilianportuguese": "pt-br",
    "ptbr": "pt-br",
    "chinese": "zh-cn", "schinese": "zh-cn", "simplifiedchinese": "zh-cn",
    "chinesesimplified": "zh-cn", "chinese(simplified)": "zh-cn",
    "chs": "zh-cn", "zhcn": "zh-cn",
    "tchinese": "zh-tw", "traditionalchinese": "zh-tw", "chineset": "zh-tw",
    "hungarian": "hu", "romanian": "ro",
    "turkish": "tr", "turkce": "tr",
    "dutch": "nl", "swedish": "sv", "norwegian": "no",
    "danish": "da", "finnish": "fi", "ukrainian": "uk",
    "catalan": "ca", "galician": "gl", "basque": "eu",
}


def normalize_folder(folder):
    """Map a WeiDU language folder name to an ISO code."""
    f = folder.lower().strip().replace(" ", "").replace("-", "").replace("_", "")
    # Strip path prefixes like "lang/en", "modname/tra/english", etc.
    parts = f.replace("\\", "/").split("/")
    # Try the last meaningful part first
    for part in reversed(parts):
        if part in FOLDER_TO_ISO:
            return FOLDER_TO_ISO[part]
        # Try two-letter codes directly
        if len(part) == 2 and part.isalpha():
            # Map common short codes
            short_map = {
                "en": "en", "fr": "fr", "de": "de", "es": "es",
                "it": "it", "pl": "pl", "ru": "ru", "cs": "cs",
                "ko": "ko", "ja": "ja", "pt": "pt", "nl": "nl",
                "sv": "sv", "no": "no", "da": "da", "fi": "fi",
                "uk": "uk", "hu": "hu", "ro": "ro", "tr": "tr",
                "sp": "es", "jp": "ja", "po": "pl",
            }
            if part in short_map:
                return short_map[part]
    # Try the full string
    if f in FOLDER_TO_ISO:
        return FOLDER_TO_ISO[f]
    return None  # Unrecognized


def parse_tp2_languages(filepath):
    """Extract LANGUAGE entries from a WeiDU TP2 file.
    Returns list of (display_name, folder_name) tuples in order."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        return []

    # WeiDU LANGUAGE syntax: LANGUAGE <display_name> <folder_name> [tra_files...]
    # Strings can be ~delimited~ or "delimited"
    delim = r'(?:~([^~]*)~|"([^"]*)")'
    pattern = rf"^\s*LANGUAGE\s+{delim}\s+{delim}"

    langs = []
    for m in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
        display = (m.group(1) or m.group(2)).strip()
        folder = (m.group(3) or m.group(4)).strip()
        langs.append((display, folder))
    return langs


# Manual mapping: tp2 folder name (lowercase) -> mod JSON 't' value (lowercase)
# For cases where the extracted folder name doesn't match the mod 't' field
TP2_TO_MOD_T = {
    "a7#improvedshamanicdance": "a7-improved_shamanic_dance",
    "a7-leveluptweaks": None,
    "bgspawn": "bgeespawn",
    "bloodandfaith": "bloodfaith",
    "c#brandock": "brandockthemage",
    "c#solaufein": "jasteys_solaufein",
    "djinnicompanion": "a7-djinnicompanion",
    "forgotten-armament": "forgottenarmament",
    "hiddengameplayoptions": "a7-hiddengameplayoptions",
    "indinpc": "indiranpc",
    "isnf": "l#isnf",
    "iwditempack": "malek-iwditempack",
    "juniperandthestoneleech": "l#juniperstone",
    "morpheus562-s-kitpack": "morpheus562skitpack",
    "plasmoportraits": "plasmobg1bg2",
    "refinements": "d5_refinements",
    "renal": "sir_renal",
    "revisedbattles": "butchery",
    "secret of bone hill": "bonehilleet",
    "sheena_v2.5": "sheena",
    "skills-and-abilities": "skills_and_abilities",
    "tactics-remix": "tacticsremix",
    "the darkest day": "tdd",
    "varshoon": "l#varshoon",
    "verrbg2": "l#verrszabg2",
    "xulaye": "xulaye_eet",
    "xzarandmontaron": "xzarmont",
    "yvette": "l#coi-yvette",
    "roorenart_bg2": "r1_roorenart",
    "totemiccernd": "cernd",
    "questpack": "d0questpack",
    "derat's absolute wacky adventurers pack": "derats_dawap",
    "5e_spellcasting": "d5_5e_casting",
    "bgeearv": "bgeearwe",
    "bgeewmart3": "wmart",
    "c#sb_silber": "c#sodboabri",  # Silver Blade = SoD Boabri
    "wilsonchronicles": "l#wilson",
    "wizard slayer rebalancing": None,  # not in mod list
    "tdd_hall-of-knowledge": "tddz",
    "spstuff": "stuffofthemagi",
    "pofquestpack": None,  # Pillars of Flame not in mod list
    "revisitoldhaunt": None,  # not in mod list
}


def build_tp2_index():
    """Find all TP2 files and parse their languages.
    Returns dict keyed by lowercase tp2 folder name (or remapped mod 't')."""
    tp2_files = list(EXTRACTED_DIR.rglob("*.tp2"))
    index = {}  # key (lowercase) -> {langs, tp2_path, ...}

    for tp2 in tp2_files:
        langs = parse_tp2_languages(str(tp2))
        if len(langs) < 2:
            continue  # Skip single-language and no-language mods

        folder = tp2.parent.name.lower()
        lang_map = {}
        for i, (display, wfolder) in enumerate(langs):
            iso = normalize_folder(wfolder)
            if iso:
                lang_map[iso] = i
            # else: skip unrecognizable folder names

        if lang_map:
            # Remap folder name if there's a manual mapping
            key = TP2_TO_MOD_T.get(folder, folder)
            if key is None:
                continue  # Explicitly excluded mod

            # If key already in index, keep the one with more languages
            if key not in index or len(lang_map) > len(index[key]["langs"]):
                index[key] = {
                    "langs": lang_map,
                    "tp2": str(tp2),
                    "raw": langs,
                }
    return index


def build_mod_index():
    """Load all mod JSON files. Returns dict keyed by lowercase 't' value."""
    mods = {}
    for f in MODS_DIR.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as jf:
                data = json.load(jf)
            if "t" in data:
                mods[data["t"].lower()] = {"path": f, "data": data}
        except Exception:
            pass
    return mods


def match_mods(tp2_index, mod_index):
    """Match TP2 entries to mod JSON files. Returns list of (mod_path, mod_data, langs_map)."""
    matches = []
    unmatched = []

    for tp2_folder, tp2_info in tp2_index.items():
        if tp2_folder in mod_index:
            m = mod_index[tp2_folder]
            matches.append((m["path"], m["data"], tp2_info["langs"]))
        else:
            unmatched.append((tp2_folder, tp2_info))

    return matches, unmatched


def main():
    parser = argparse.ArgumentParser(description="Populate langs in mod JSONs from TP2 files")
    parser.add_argument("--write", action="store_true", help="Write changes to files")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes only")
    args = parser.parse_args()

    if not args.write and not args.dry_run:
        print("Usage: python populate_langs.py --dry-run | --write")
        sys.exit(1)

    print("Scanning TP2 files...")
    tp2_index = build_tp2_index()
    print(f"  Found {len(tp2_index)} multi-language TP2 mods")

    print("Loading mod JSON files...")
    mod_index = build_mod_index()
    print(f"  Found {len(mod_index)} mod JSON files")

    matches, unmatched = match_mods(tp2_index, mod_index)
    print(f"  Matched: {len(matches)}")
    print(f"  Unmatched TP2 folders: {len(unmatched)}")

    # Process matches
    written = 0
    skipped = 0
    removed_old_lang = 0

    for mod_path, mod_data, langs_map in matches:
        # Skip if only English (no point in storing {"en": 0})
        if len(langs_map) == 1 and "en" in langs_map and langs_map["en"] == 0:
            skipped += 1
            continue

        # Check if langs already exists and is identical
        if mod_data.get("langs") == langs_map:
            skipped += 1
            continue

        old_lang = mod_data.get("lang")
        mod_data["langs"] = langs_map

        # Remove old 'lang' field if it's now redundant
        if "lang" in mod_data:
            # Verify the old lang value is consistent with new langs
            en_idx = langs_map.get("en", 0)
            if old_lang == en_idx or old_lang is None:
                del mod_data["lang"]
                removed_old_lang += 1
            else:
                # Old lang doesn't match English index - keep it as a safety net
                # but print a warning
                print(f"  WARNING: {mod_path.name} has lang={old_lang} but langs.en={en_idx}")
                del mod_data["lang"]
                removed_old_lang += 1

        # Also remove component-level 'l' fields if they match the mod's English index
        en_idx = langs_map.get("en", 0)
        for comp in mod_data.get("co", []):
            if "l" in comp and comp["l"] == en_idx:
                del comp["l"]

        if args.write:
            with open(mod_path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(mod_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            written += 1
        else:
            print(f"  Would update: {mod_path.name} -> {langs_map}")
            written += 1

    print(f"\n=== RESULTS ===")
    print(f"{'Updated' if args.write else 'Would update'}: {written} files")
    print(f"Skipped (no change needed): {skipped}")
    print(f"Removed old 'lang' field from: {removed_old_lang} files")

    if unmatched:
        print(f"\n=== UNMATCHED TP2 FOLDERS ({len(unmatched)}) ===")
        for folder, info in sorted(unmatched):
            iso_list = list(info["langs"].keys())
            print(f"  {folder} ({len(iso_list)} langs): {iso_list}")


if __name__ == "__main__":
    main()
