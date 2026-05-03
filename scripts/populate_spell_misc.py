"""Phase 5: populate `ct` (casting time), `rng` (range), `aoe` (area of effect),
and `dur` (duration) on all spells.

Strategy:
- `dur`: parse from desc text (43% have explicit durations); else "instant".
- `aoe`: parse from desc; else heuristic from spell type.
- `rng`: heuristic — touch / self / sight / 30 ft based on text patterns.
- `ct`:  default = spell level (covers ~85% of BG2 vanilla); overrides for known
         exceptions (Magic Missile=1, Fireball=3, etc.).

This is best-effort. Authoritative casting time would need SPL-byte extraction
from a game install. Where the parser/heuristic is uncertain, the field is
still set (closest match) — a future SPL pass can refine.
"""
import json
import os
import re
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPELLS_PATH = os.path.join(ROOT, "data", "spells-vanilla.json")

# Casting time overrides (BG2 vanilla, where ct != spell level).
CT_OVERRIDES = {
    "SPWI112": 1,    # Magic Missile
    "SPWI114": 1,    # Shield
    "SPWI116": 1,    # Sleep
    "SPWI120": 1,    # Reflected Image
    "SPWI212": 2,    # Mirror Image
    "SPWI220": 2,    # Ray of Enfeeblement
    "SPWI221": 1,    # Chaos Shield (instant defensive)
    "SPWI304": 3,    # Fireball
    "SPWI308": 3,    # Lightning Bolt
    "SPWI403": 4,    # Fireshield Blue
    "SPWI417": 4,    # Fireshield Red
    "SPWI420": 1,    # Teleport Field (FAST)
    "SPWI603": 9,    # Contingency
    "SPWI609": 1,    # Improved Haste
    "SPWI702": 1,    # Power Word Stun
    "SPWI805": 1,    # Power Word Blind
    "SPWI904": 1,    # Power Word Kill
    "SPWI907": 3,    # Time Stop (FAST)
    "SPWI909": 9,    # Chain Contingency
    "SPPR104": 5,    # Cure Light Wounds (BG2 EE: ct 5)
    "SPPR110": 4,    # Sanctuary (cleric standard 4)
    "SPPR503": 5,    # Cure Critical Wounds
    "SPPR509": 8,    # Mass Cure
    "SPPR611": 1,    # Heal (instant)
    "SPPR707": 1,    # Greater Restoration
    "SPPR710": 1,    # Regeneration
}

# AoE overrides for orphan spells (not in BG2EE backup) whose descriptions
# don't explicitly mention radius/cone but are known AoEs in vanilla BG2.
AOE_OVERRIDES = {
    "SPWI801": "area",   # Abi-Dalzim Horrid Wilting
    "SPWI901": "area",   # Meteor Swarm
    "SPWI906": "area",   # Wail of the Banshee
    "SPPR714": "area",   # Symbol Death
    "SPPR716": "area",   # Symbol Stun
}

# Range overrides for orphan spells
RNG_OVERRIDES = {
    "SPWI109": "touch",  # Identify (used on item in inventory)
    "SPWI801": "visual", # Horrid Wilting
    "SPWI901": "visual", # Meteor Swarm
    "SPWI906": "visual", # Wail of the Banshee
    "SPWI904": "60 ft",  # Power Word Kill
    "SPPR714": "visual", # Symbol Death
    "SPPR716": "visual", # Symbol Stun
}

# Wholesale dur overrides for spells whose desc gives no duration but
# have well-known durations.
DUR_OVERRIDES = {
    "SPWI109": "instant",        # Identify
    "SPWI207": "instant",        # Knock
    "SPWI208": "instant",        # Know Alignment
    "SPWI318": "1 round",        # Detect Illusion
    "SPWI320": "instant",        # Remove Magic
    "SPWI121": "instant",        # Nahal Reckless Dweomer (cast)
    "SPPR604": "instant",        # Bolt of Glory
    "SPPR611": "instant",        # Heal
    "SPPR703": "1 round/level",  # Creeping Doom
    "SPPR704": "1 round",        # Earthquake
    "SPPR706": "instant",        # Gate (summon then permanent until killed)
    "SPPR708": "instant",        # Holy Word
    "SPPR713": "instant",        # Sunray
    "SPPR719": "instant",        # Unholy Word
    "SPPR717": "instant",        # Finger of Death
    "SPPR718": "permanent",      # Energy Drain
}


DUR_PATTERNS = [
    # Most specific first
    (re.compile(r"\bpermanent\b", re.I), lambda m: "permanent"),
    (re.compile(r"\binstant(?:aneous)?\b", re.I), lambda m: "instant"),
    (re.compile(r"\b(\d+)\s*\+\s*(\d+)\s*/\s*level\s+rounds?\b", re.I),
        lambda m: f"{m.group(1)}+{m.group(2)}/level rounds"),
    (re.compile(r"\b(\d+)\s+rounds?\s*/\s*level\b", re.I),
        lambda m: f"{m.group(1)} round/level" if m.group(1) == "1" else f"{m.group(1)} rounds/level"),
    (re.compile(r"\b(\d+)\s+turns?\s*/\s*level\b", re.I),
        lambda m: f"{m.group(1)} turn/level" if m.group(1) == "1" else f"{m.group(1)} turns/level"),
    (re.compile(r"\b(\d+)\s+hours?\s*/\s*level\b", re.I),
        lambda m: f"{m.group(1)} hour/level" if m.group(1) == "1" else f"{m.group(1)} hours/level"),
    (re.compile(r"\b(\d+)\s+rounds?\b", re.I),
        lambda m: f"{m.group(1)} round" if m.group(1) == "1" else f"{m.group(1)} rounds"),
    (re.compile(r"\b(\d+)\s+turns?\b", re.I),
        lambda m: f"{m.group(1)} turn" if m.group(1) == "1" else f"{m.group(1)} turns"),
    (re.compile(r"\b(\d+)\s+hours?\b", re.I),
        lambda m: f"{m.group(1)} hour" if m.group(1) == "1" else f"{m.group(1)} hours"),
]

AOE_PATTERNS = [
    (re.compile(r"(\d+)\s*(?:ft|foot|-foot|')\s*radius", re.I),
        lambda m: f"{m.group(1)}ft radius"),
    (re.compile(r"(\d+)\s*(?:ft|foot|-foot|')\s*cone", re.I),
        lambda m: f"{m.group(1)}ft cone"),
    (re.compile(r"\b(\d+)\s*ft\s*radius", re.I),
        lambda m: f"{m.group(1)}ft radius"),
    (re.compile(r"\bcentered on caster\b", re.I),
        lambda m: "caster radius"),
    (re.compile(r"\bin\s+(\d+)\s*['ft]+\s*area\b", re.I),
        lambda m: f"{m.group(1)}ft area"),
    (re.compile(r"\bcone\b", re.I), lambda m: "cone"),
    (re.compile(r"\bin\s+area\b", re.I), lambda m: "area"),
]

RNG_KEYWORDS = [
    (re.compile(r"\btouch\b", re.I), "touch"),
    (re.compile(r"\bcaster\b|\bself\b", re.I), "self"),
]


def parse_dur(desc: str) -> str:
    if not desc:
        return "instant"
    for pat, fn in DUR_PATTERNS:
        m = pat.search(desc)
        if m:
            return fn(m)
    return "instant"


def parse_aoe(desc: str, school: str = "") -> str:
    if not desc:
        return "single"
    for pat, fn in AOE_PATTERNS:
        m = pat.search(desc)
        if m:
            return fn(m)
    return "single"


def parse_rng(desc: str, aoe: str) -> str:
    if not desc:
        return "visual"
    for pat, val in RNG_KEYWORDS:
        if pat.search(desc):
            return val
    if "radius" in aoe or "cone" in aoe or "area" in aoe:
        return "visual"
    return "30 ft"


def load_spl_refs():
    """Refs that the SPL extractor covers. Skip them here to avoid clobbering."""
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
            f.read(4)
            if rtype == 0x3EE:
                refs.add(name)
    return refs


def main():
    with open(SPELLS_PATH, "r", encoding="utf-8") as f:
        spells = json.load(f, object_pairs_hook=OrderedDict)

    # Skip ct/rng/aoe on spells covered by SPL extractor (they're authoritative).
    # Dur still comes from desc since SPL doesn't carry it portably.
    spl_refs = load_spl_refs()

    counts = {"ct": 0, "rng": 0, "aoe": 0, "dur": 0}
    skipped = 0

    for ref, entry in spells.items():
        # Skip non-spell metadata entries
        if not isinstance(entry, dict) or entry.get("type") not in ("wizard","priest","innate","hla"):
            continue
        desc = entry.get("desc", "") or ""

        # Always (re)populate duration — SPL extractor doesn't set it.
        entry["dur"] = DUR_OVERRIDES.get(ref) or parse_dur(desc)
        counts["dur"] += 1

        if ref.upper() in spl_refs:
            skipped += 1
            continue

        lv = entry.get("lv") or 1
        school = entry.get("school", "") or ""

        # Casting time: spell level by default, override map for exceptions
        entry["ct"] = CT_OVERRIDES.get(ref, lv)
        counts["ct"] += 1

        # AoE (allow override for orphan spells)
        aoe = AOE_OVERRIDES.get(ref) or parse_aoe(desc, school)
        entry["aoe"] = aoe
        counts["aoe"] += 1

        # Range (allow override)
        entry["rng"] = RNG_OVERRIDES.get(ref) or parse_rng(desc, aoe)
        counts["rng"] += 1

    with open(SPELLS_PATH, "w", encoding="utf-8") as f:
        json.dump(spells, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Applied per-spell metadata ({skipped} skipped for SPL extractor):")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
