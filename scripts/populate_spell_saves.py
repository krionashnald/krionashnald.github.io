"""Phase 4: heuristic fallback `sv` (save type) for spells NOT covered by the
SPL extractor (extract_vanilla_spells_spl.py). This script is SAFE to re-run
after extraction — it only touches spells that lack authoritative SPL data.

Pipeline order:
  Phase 4 (this) -> Phase 5 heuristic misc -> Phase 6 SPL extraction (--write)

After running the SPL extractor, ct/rng/aoe/sv are authoritative for 284/302
spells; the remaining 18 (EE-only: Identify, Sunscorch, Limited Wish variants,
Meteor Swarm, Power Word Kill, etc.) keep this phase's heuristic sv data.

Save types: none | spell | breath | death | wand | polymorph | petrification
"""
import json
import os
import re
from collections import OrderedDict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPELLS_PATH = os.path.join(ROOT, "data", "spells-vanilla.json")

# Per-spell overrides where desc is ambiguous or incomplete.
# Refs verified against data/spells-vanilla.json names; BG2 vanilla.
OVERRIDES = {
    # --- Wizard: damage with save for half (vs spell) ---
    "SPWI103": "spell",      # Burning Hands
    "SPWI304": "spell",      # Fireball
    "SPWI308": "spell",      # Lightning Bolt
    "SPWI313": "spell",      # Skull Trap
    "SPWI503": "spell",      # Cone of Cold
    "SPWI508": "spell",      # Chaos
    "SPWI519": "spell",      # Sunfire
    "SPWI704": "spell",      # Delayed Blast Fireball
    "SPWI709": "spell",      # Khelben Warding Whip
    "SPWI712": "spell",      # Sphere of Chaos
    "SPWI713": "spell",      # Prismatic Spray (dominant effect)
    "SPWI801": "spell",      # Abi-Dalzim Horrid Wilting
    "SPWI802": "spell",      # Incendiary Cloud
    "SPWI810": "spell",      # Symbol Stun
    "SPWI811": "spell",      # Symbol Fear
    "SPWI901": "spell",      # Meteor Swarm
    "SPWI919": "spell",      # Comet

    # --- Wizard: death saves ---
    "SPWI116": "death",      # Sleep
    "SPWI502": "death",      # Cloudkill
    "SPWI613": "death",      # Death Spell
    "SPWI614": "death",      # Death Fog (poison)
    "SPWI615": "death",      # Disintegrate
    "SPWI701": "death",      # Finger of Death
    "SPWI803": "death",      # Symbol Death
    "SPWI906": "death",      # Wail of the Banshee

    # --- Wizard: breath saves ---
    "SPWI920": "breath",     # Dragon Breath

    # --- Wizard: petrification ---
    "SPWI611": "petrification",  # Flesh to Stone

    # --- Wizard: no save (touches, self-only, HP-gated, Imprisonment) ---
    "SPWI112": "none",       # Magic Missile
    "SPWI220": "none",       # Ray of Enfeeblement
    "SPWI314": "none",       # Vampiric Touch
    "SPWI404": "none",       # Ice Storm
    "SPWI607": "none",       # Mislead
    "SPWI703": "none",       # Mordenkainen Sword
    "SPWI716": "none",       # Limited Wish
    "SPWI809": "none",       # Bigby Clenched Fist
    "SPWI903": "none",       # Imprisonment
    "SPWI904": "none",       # Power Word Kill (HP-gated, no save)
    "SPWI910": "none",       # Wish
    "SPWI912": "none",       # Shapechange
    "SPWI921": "none",       # Energy Drain

    # --- Priest: death saves ---
    "SPPR512": "death",      # Slay Living
    "SPPR717": "death",      # Finger of Death (priest version)

    # --- Priest: spell saves for damage AoE ---
    "SPPR302": "spell",      # Call Lightning
    "SPPR315": "spell",      # Summon Insects
    "SPPR504": "spell",      # Flame Strike
    "SPPR506": "spell",      # Insect Plague
    "SPPR604": "spell",      # Bolt of Glory
    "SPPR609": "spell",      # Fire Seeds
    "SPPR703": "spell",      # Creeping Doom
    "SPPR704": "spell",      # Earthquake
    "SPPR705": "spell",      # Fire Storm
    "SPPR708": "spell",      # Holy Word
    "SPPR713": "spell",      # Sunray
    "SPPR719": "spell",      # Unholy Word

    # --- Priest: no save ---
    "SPPR603": "none",       # Blade Barrier (passive aura)
    "SPPR610": "none",       # Harm (touch attack in BG2 EE)
    "SPPR718": "none",       # Energy Drain (priest)
}


def parse_save(desc: str) -> str:
    if not desc:
        return "none"
    d = desc.lower()

    # Check for explicit "no save"
    if re.search(r"\bno\s+save\b", d):
        return "none"

    # Explicit save-vs-X patterns (most specific first)
    patterns = [
        (r"\bsave\s+(?:vs\.?\s+)?breath", "breath"),
        (r"\bsave\s+(?:vs\.?\s+)?death", "death"),
        (r"\bsave\s+(?:vs\.?\s+)?poison", "death"),
        (r"\bsave\s+(?:vs\.?\s+)?paralysis", "petrification"),
        (r"\bsave\s+(?:vs\.?\s+)?petrification", "petrification"),
        (r"\bsave\s+(?:vs\.?\s+)?polymorph", "polymorph"),
        (r"\bsave\s+(?:vs\.?\s+)?wand", "wand"),
        (r"\bsave\s+(?:vs\.?\s+)?spell", "spell"),
    ]
    for pat, save_type in patterns:
        if re.search(pat, d):
            return save_type

    # Generic save patterns (default to vs spell in AD&D 2e)
    if re.search(r"\bsave\b", d):
        return "spell"

    # No save mentioned = passive or no save
    return "none"


def load_spl_refs():
    """Read chitin.key to find which refs the SPL extractor would cover.
    Returns a set; if the backup path isn't available, returns an empty set
    (in which case this script fills sv on every spell — its original behavior)."""
    import struct
    KEY = r"F:\BGMods\Backups\Baldur's Gate II Enhanced Edition\chitin.key"
    if not os.path.exists(KEY):
        return set()
    refs = set()
    with open(KEY, "rb") as f:
        f.seek(8)
        bif_count, res_count, bif_off, res_off = struct.unpack("<IIII", f.read(16))
        f.seek(res_off)
        for _ in range(res_count):
            name = f.read(8).rstrip(b"\x00").decode("latin-1").upper()
            rtype = struct.unpack("<H", f.read(2))[0]
            f.read(4)  # skip locator
            if rtype == 0x3EE:
                refs.add(name)
    return refs


def main():
    with open(SPELLS_PATH, "r", encoding="utf-8") as f:
        spells = json.load(f, object_pairs_hook=OrderedDict)

    # Refs that the SPL extractor will provide authoritatively. Skip them here
    # so re-running this script after --write doesn't clobber extracted data.
    spl_refs = load_spl_refs()

    stats = Counter()
    applied = 0
    skipped = 0
    for ref, entry in spells.items():
        # Skip non-spell metadata entries (e.g. _slotBaseline)
        if not isinstance(entry, dict) or entry.get("type") not in ("wizard","priest","innate","hla"):
            continue
        if ref.upper() in spl_refs:
            skipped += 1
            continue
        if ref in OVERRIDES:
            sv = OVERRIDES[ref]
        else:
            sv = parse_save(entry.get("desc", ""))
        entry["sv"] = sv
        stats[sv] += 1
        applied += 1

    with open(SPELLS_PATH, "w", encoding="utf-8") as f:
        json.dump(spells, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Applied sv to {applied} spells (skipped {skipped} covered by SPL extractor)")
    for t, c in stats.most_common():
        print(f"  {t}: {c}")


if __name__ == "__main__":
    main()
