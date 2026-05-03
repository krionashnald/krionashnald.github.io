#!/usr/bin/env python3
"""
Populate 'pt' field in mod JSON files using extracted portrait data.

For NPC mods with a single portrait, auto-assigns the portrait to
component 0 using the mod's tp2 name as the NPC ID base.

Usage:
    python scripts/populate_portraits.py --dry-run    # preview changes
    python scripts/populate_portraits.py --write      # write changes
"""

import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODS_DIR = ROOT / "data" / "mods"
PORTRAITS_DIR = ROOT / "portraits"
RESULTS_FILE = ROOT / "data" / "portrait_extraction_results.json"

# Manual NPC ID overrides for known mods
# Maps (mod_tp2, portrait_name) -> npc_id
NPC_ID_MAP = {
    # NPC companion mods - map portrait to NPC ID
    ("alassa", "d0alas"): "alassa",
    ("ARIENA", "Ariena"): "ariena",
    ("Aura_BG1_2_EET", "C0Aura"): "aura",
    ("BAEBG2", "zdbae"): "baeloth",
    ("Blackhearts", "Neris"): "neris",
    ("BrandockTheMage", "C#Brand"): "brandock",
    ("BrandockTheMage", "c#brand"): "brandock",
    ("calin", "kkcalin"): "calin",
    ("c#brage", "C#Brage"): "brage",
    ("c#greythedog", "c#greyp"): "grey_dog",
    ("Darian", "t1dar"): "darian",
    ("evandra", "rh#eva"): "evandra",
    ("FAREN", "fhf"): "faren",
    ("GAHESH", "G1Gahe"): "gahesh",
    ("gorgon", "h_liede"): "gorgon",
    ("Helga", "AHelga"): "helga",
    ("Helga", "Helga"): "helga",
    ("Kale", "Kale"): "kale",
    ("Kale", "X3Kale"): "kale",
    ("KIARA-ZAIYA", "kiara"): "kiara",
    ("KIARA-ZAIYA", "zaiya"): "zaiya",
    ("KIDO", "Kido"): "kido",
    ("kimnpc", "Kim"): "kim",
    ("kimnpc", "Barbe"): "barbe",
    ("LENA", "EU#LENA"): "lena",
    ("l#dvaradime", "L#DVA"): "dvaradime",
    ("l#fhaugy", "L#FHA"): "fhaugy",
    ("l#hephernaanbg2", "l#hph"): "hephernaan",
    ("l#juniperstone", "L#JN"): "juniper",
    ("l#varshoon", "VxV"): "varshoon",
    ("l#varshoon", "VxV2"): "varshoon",
    ("l#walahnanbg1ee", "L#CHR"): "walahnan",
    ("l#walahnanbg2", "L#CHR"): "walahnan",
    ("Mazzy", "tb#mazp"): "mazzy",
    ("navarra", "kknav"): "navarra",
    ("Neera", "ay#ne1"): "neera",
    ("Neera", "ay#ne2"): "neera",
    ("NEPHELE", "lk#nep"): "nephele",
    ("ORELIOS", "PM_Orel"): "orelios",
    ("paina", "paina"): "paina",
    ("paina", "C0ICPA"): "paina",
    ("ROSERE", "k-rose"): "rose",
    ("STAR", "malefi6"): "silver_star",
    ("tashia", "tashia"): "tashia",
    ("TOD", "va#tian"): "tod_tian",
    ("Valkrana", "vvVALK"): "valkrana",
    ("xulaye_eet", "lk#xul"): "xulaye",
    ("jasteys_solaufein", "C#Solau"): "solaufein",
    ("ASKARIA", "zyaska"): "askaria",
    ("ASKARIA", "zychaos"): "chaos_knight",
    ("Ooze", "L#NSNym"): "ooze_nym",
    ("Neh'taniel", "SK#Neh"): "nehtaniel",
    ("Neh'taniel", "SK#Neht"): "nehtaniel",
    # Portrait packs - ajantis
    ("ajantisportraitpack", "C#AJAN"): "ajantis",
    ("ajantisportraitpack", "c#ajan"): "ajantis",
    # Zakrion
    ("Zakrion_BG1", "QI#ZA1"): "zakrion",
    ("Zakrion_BG1", "QI#Zak"): "zakrion",
    # Verr'sza
    ("l#verrszabg2", "L#VRZA"): "verrsza",
    # Newly downloaded NPC mods
    ("Cassius", "lrM65"): "cassius",
    ("Chiara", "V#Chia"): "chiara",
    ("Chiara", "V#Wolf"): "chiara_wolf",
    ("Hendak", "HB#Hend"): "hendak",
    ("Horace", "Horace"): "horace",
    ("Larsha", "Larsha"): "larsha",
    ("Malthis", "Werwolf"): "malthis",
    ("MawgulNPC", "Mauro"): "mawgul",
    ("Nina", "Nina"): "nina",
    ("Thael", "Thael"): "thael",
    ("Thael", "Sindel"): "thael_sindel",
    ("Thael", "Zaki"): "thael_zaki",
    ("Xardas", "xmage"): "xardas",
    ("FoxMonster", "Z_MODDY"): "moddie",
    ("mhoram", "mhoram2"): "mhoram",
    ("NikitaRedux", "CMNIKI"): "nikita",
    ("NikitaRedux", "CMNIK2"): "nikita",
    ("Severian", "#Sever"): "severian",
    ("Severian", "#Sev25"): "severian",
    ("CompassOfWomanhood", "6Wshith"): "shithri",
    ("Deepgnomes", "aurora"): "deepgnome_aurora",
    ("kitanya", "r!kitan"): "kitanya",
    ("kitanya", "r!kitud"): "kitanya",
    ("mkhiinbg2", "Mkhiin"): "mkhiin",
    ("TS_Sime", "vpsime1"): "ts_sime",
    ("TS_Sime", "vpsime2"): "ts_sime",
    ("7C-Yoshi", "7C#Dem"): "yc_demogorgon",
    ("7C-Yoshi", "7C#Tor"): "yc_tortured",
    ("sbs", "sandra"): "sandra",
    ("sbs", "sbsmess"): "sbs_messenger",
    ("sbs", "sellthf"): "sbs_sellthief",
    ("SandrahPort", "CVsand"): "sandrah",
    ("SandrahPort", "Jenlig"): "jenlig",
    # Blonde Imoen
    ("blondeimmy", "nimoen1"): "imoen",
    ("blondeimmy", "nimoen2"): "imoen",
    # Consistent Portraits (bmpp) - vanilla NPC replacements
    ("bmpp", "Ajantis"): "ajantis",
    ("bmpp", "Alora"): "alora",
    ("bmpp", "Baeloth"): "baeloth",
    ("bmpp", "Branwen"): "branwen",
    ("bmpp", "Coran"): "coran",
    ("bmpp", "Dynaheir"): "dynaheir",
    ("bmpp", "Edwin"): "edwin",
    ("bmpp", "Eldoth"): "eldoth",
    ("bmpp", "Faldorn"): "faldorn",
    ("bmpp", "Garrick"): "garrick",
    ("bmpp", "Imoen"): "imoen",
    ("bmpp", "Jaheira"): "jaheira",
    ("bmpp", "Kagain"): "kagain",
    ("bmpp", "Khalid"): "khalid",
    ("bmpp", "Kivan"): "kivan",
    ("bmpp", "Minsc"): "minsc",
    ("bmpp", "Montaron"): "montaron",
    ("bmpp", "Quayle"): "quayle",
    ("bmpp", "Safana"): "safana",
    ("bmpp", "Skie"): "skie",
    ("bmpp", "Tiax"): "tiax",
    ("bmpp", "Viconia"): "viconia",
    ("bmpp", "Xan"): "xan",
    ("bmpp", "Xzar"): "xzar",
    ("bmpp", "Yeslick"): "yeslick",
    ("bmpp", "sharteel"): "sharteel",
    ("bmpp", "Dorn"): "dorn",
    ("bmpp", "Neera"): "neera",
    ("bmpp", "Rasaad"): "rasaad",
}

# Phase overrides
PHASE_MAP = {
    "Blackhearts": "bg1",
    "c#brage": "bg1",
    "gorgon": "bg1",
    "l#walahnanbg1ee": "bg1",
    "Zakrion_BG1": "bg1",
    "l#juniperstone": "tob",
}

# Mods to skip (already have pt, or not NPC mods)
SKIP_MODS = {
    "RE",         # romantic encounters - too many components
    "da_portraits",  # massive pack, handle separately
    "cd_icpp",    # massive pack, handle separately
    "mercenaries", # not in database properly
    "picks_of_the_litter",  # PC portrait pack, handle separately
    "golden_horse",  # no mod entry yet
    "cdportraits",  # handle separately
    "NWNForBG",   # handle separately
    "Travellers",  # false positive (LAUREL.bmp is not a portrait)
    "DC",  # Dungeon Crawl portraits, handle separately
    "DarkHorizons",  # handle separately
    "Dorn",  # romance expansion, not portrait provider (L#FAL is Faldorn)
    "cliffhistory",  # not a portrait mod
    "A7-WaresOfThePlanes",  # item mod
    "ArtisansKitpack",  # kit mod
    "npcflirt",  # not a portrait mod
    "eefixpack",  # not a portrait mod
    "RR",  # not a portrait mod
    "mih_sp",  # spell pack
    "saradas_magic_2",  # spell pack
    "BoM",  # item pack
    "yoshimo",  # friendship, not portrait
    "mih_ip",  # item pack
    "cdtweaks",  # tweak mod
}


def guess_phase(mod_data, tp2):
    """Determine game phase from mod category."""
    if tp2 in PHASE_MAP:
        return PHASE_MAP[tp2]
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
    return "bg2"


def main():
    parser = argparse.ArgumentParser(description="Populate pt fields in mod JSONs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.write:
        print("Specify --dry-run or --write")
        return

    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        results = json.load(f)

    stats = {"updated": 0, "skipped": 0, "manual": 0}

    for result in sorted(results, key=lambda x: x["mod_name"]):
        tp2 = result["mod"]
        mod_name = result["mod_name"]
        mod_file = Path(result["mod_file"])
        needs_review = result["needs_review"]

        if not needs_review:
            continue
        if tp2 in SKIP_MODS:
            stats["skipped"] += 1
            continue

        # Load the mod file
        with open(mod_file, "r", encoding="utf-8") as f:
            mod_data = json.load(f)

        # Skip if already has pt data
        if "pt" in mod_data:
            stats["skipped"] += 1
            continue

        phase = guess_phase(mod_data, tp2)
        out_dir = result["out_dir"]

        # Build pt entries
        pt_npc = {}
        unresolved = []

        for portrait in needs_review:
            pname = portrait["portrait_name"]
            path = portrait["path"]
            p_phase = portrait.get("phase", phase)

            # Look up NPC ID
            npc_id = NPC_ID_MAP.get((tp2, pname))
            if not npc_id:
                # Try auto-deriving for single-portrait NPC mods
                if len(needs_review) == 1:
                    # Use mod tp2 name as NPC ID for single-portrait mods
                    npc_id = tp2.lower().replace("-", "_")
                else:
                    unresolved.append(portrait)
                    continue

            # Find which component this portrait belongs to
            # Default to component 0 (main component)
            comp_idx = "0"

            if comp_idx not in pt_npc:
                pt_npc[comp_idx] = []
            pt_npc[comp_idx].append([npc_id, path, p_phase])

        if not pt_npc and not unresolved:
            continue

        if pt_npc:
            print(f"\n{mod_name} ({tp2}):")
            for cidx, entries in sorted(pt_npc.items()):
                for entry in entries:
                    print(f"  co[{cidx}]: [{entry[0]}] -> {entry[1]} ({entry[2]})")

            if args.write:
                # Insert pt field before co
                mod_data["pt"] = {"npc": pt_npc}
                with open(mod_file, "w", encoding="utf-8") as f:
                    json.dump(mod_data, f, indent=2, ensure_ascii=False)
                stats["updated"] += 1

        if unresolved:
            stats["manual"] += len(unresolved)
            if not pt_npc:
                print(f"\n{mod_name} ({tp2}): MANUAL REVIEW NEEDED")
            for p in unresolved:
                print(f"  ?? {p['portrait_name']} -> {p['path']}")

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"  Mods updated: {stats['updated']}")
    print(f"  Mods skipped: {stats['skipped']}")
    print(f"  Portraits needing manual review: {stats['manual']}")


if __name__ == "__main__":
    main()
