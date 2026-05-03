"""Heuristic sphere tagger for mod-added priest spells.

Scans each mod's spl.*.new entries for type='priest' spells that don't already have a
sphere tag (7th tuple element) and assigns sphere membership based on regex matches
against the spell name + description. Accuracy ~70-80%; meant as a first pass that
users can correct over time.

Rules:
- Multiple spheres can apply (common for e.g. "Flame Strike" => combat + elemental + sun)
- Patterns are ordered by specificity; broad patterns (combat, protection) run last
- Spells with zero matches stay untagged (sph omitted) and render without dimming,
  which is the safe default.
"""
import json
import os
import re
from collections import OrderedDict, Counter

MODS_DIR = os.path.join("data", "mods")

# Each rule: (sphere_name, regex_pattern). Patterns run against f"{name} | {desc}"
# lowercased. Order matters only when we want to bias primary sphere ordering
# (but we dedupe while preserving first-seen, so put the "primary" sphere first).
RULES = [
    # Healing — strong signals
    ("healing",    r"\b(cure|heal|healing|restoration|regenerat|revive|resurrect|mass cure|raise dead|neutralize poison|slow poison|remove disease|remove fatigue|lay on hands|dying|spare the|stabiliz|recover|mend|soothe|wholeness|vitality|aura of vitality)"),

    # Summoning — conjure living things / undead. NOTE: avoid bare "undead" or
    # "beast" (common in anti-undead spell descriptions); require context.
    ("summoning",  r"\b(summon|conjure|call forth|animate (dead|skeleton)|creeping doom|insect plague|aerial servant|gate |elemental\b|spirit (wolf|companion|weapon|ally|servant|guardian)|call woodland|call lightning stop|call animal|planar ally|create undead|raise undead|invoke|spiritual ally|spiritual weapon|circle of bones|skeletal warrior|skeleton warrior|animate skeleton|animal rage|sticks to snakes|banishment|banish)"),

    # Sun — light, dawn, radiance
    ("sun",        r"\b(sun\b|sunlight|sunray|sunscorch|dawn|daylight|radianc|searing (orb|light)|false dawn|bolt of glory|aureol|moon\b|moonlight|moonblade|lunar|wall of moonlight)"),

    # Elemental — fire/cold/electricity/earth/air. Avoid generic "water" (matches
    # Bless Water, Holy Water etc.); stick to actual elemental water descriptors.
    ("elemental",  r"\b(fire\b|flame|burning|inferno|blaze|scorch|cold\b|frost|ice|freez|chill|lightning|thunder|shock|electric|storm|earth(quake)?|stone\b|boulder|wind|gale|hurricane|whirlwind|wave\b|tidal|tsunami|wall of water|elemental water|acid|vitriol|obscuring mist|mist\b|fog|cloud|smashing wave)"),

    # Destruction — decay, disintegrate, finger of death, harm. Death Watch is
    # divination (reveal HP), not destruction — don't catch it here.
    ("destruction",r"\b(destroy|destruction|disintegrat|decay|rot\b|rotting|slay|harm\b|finger of death|energy drain|wither|blight|obliter|annihilat|cataclysm|bone chill|flesh to stone|deadly|lethal|life steal|life drain|dark ritual|antilife|contagion|disease|plague)"),

    # Chaos — confusion, insanity, random
    ("chaos",      r"\b(chaos|confus|insanity|maddening|madness|random|wild magic|entropic|entropy|unbind|unravel|disorient)"),

    # Law — compel, command, hold, order
    ("law",        r"\b(command|greater command|compel|control person|hold person|hold animal|hold undead|dictate|order\b|lawful\b|bind (the|its|them)|enthrall|geas|quest)"),

    # Charm — influence minds, fear (mind-affecting)
    ("charm",      r"\b(charm|domina(te|tion)|enthrall|hypnoti|suggestion|mental|morale|cloak of fear|fear\b|frighten|terrify|nightmar|rigid thinking|symbol (fear|stun|hopelessness|pain|death|despair|persuasion)|beguil|emotion|hopeless|despair|pain\b)"),

    # Guardian — sanctuary, ward, protective aura
    ("guardian",   r"\b(sanctuar|ward|warding|mirror|shield (of|against)|death ward|free action|impervious|armor of faith|spell immunity|magic resistance|negative plane|iron skin|stoneskin|hallow|unhallow|holy ground|consecrat)"),

    # Protection — broad "resist/immune" aura
    ("protection", r"\b(protection|protect from|resist|immune|immunity|dispel|remove paralysis|remove curse|remove fear|neutraliz|barkskin|zone of sweet|chaotic commands|defensive|repel|break enchantment|magic vestment)"),

    # Combat — blessings, attack boosts, weapon effects. Keep `cause` narrowed to
    # the classic "cause X wounds" family so we don't catch generic "cause" usages.
    ("combat",     r"\b(bless|aid\b|chant|prayer|recitation|draw upon|holy might|spiritual (hammer|weapon|wrath)|magical stone|shillelagh|flame blade|sling stones|glyph of warding|miscast|strength of one|oxen strength|holy power|righteous|champion|cause (serious|light|medium|moderate|critical|mass) wounds|mass cause|poison|blade barrier|dolorous|unholy|slay|doom\b|divine (wrath|retribution|might|favor|power|shield|smite|word|aura)|smite|crusader|battle|moonblade|alicorn|lance|strike\b|striking|rage\b|wrath|fang\b|beast claw|favor of|blood (rage|oath)|heroism|heroic|cudgel|magic vestment|magic weapon|magic fang|exalted|triad|seeking|find weakness|holy (wrath|word|aura|power|smite|might))"),

    # War — specifically martial/combat-enhancement
    ("war",        r"\b(war\b|battle|martial|holy power|champion|righteous (magic|might)|strength of one|oxen strength|bless|aid\b|chant|prayer|recitation|enchant(ed)? weapon|spiritual (hammer|weapon|wrath)|flame blade|holy word|unholy word|draw upon holy|crusader|blade barrier|moonblade|alicorn|lance|rage\b|wrath|blood rage|favor of|heroism|heroic|magic vestment|exalted|triad)"),

    # Creation — create food, wall of thorns, plants
    ("creation",   r"\b(create food|create water|goodberry|wall of (thorns|briar|moonlight)|minor creation|plant growth|spike growth|tree\b|fabricat|transport via plants|grow\b|thorn spray|spike stones)"),

    # Divination — detect, scry, seeing, find. Note: use `divination` (not `divin`)
    # to avoid matching "divine" which commonly appears in combat-style descriptions.
    ("divination", r"\b(detect|scry|scrying|true (seeing|sight)|clairvoyan|clairaud|locate|find traps|know alignment|augur|divination|invisibility purge|farsight|wondrous recall|word of recall|legend lore|identify|commune|speak with|guidance|insight|foresight|foretell|foreboding|death watch)"),

    # Guardian — add antilife shell and other ward variants
    ("guardian",   r"\b(antilife|anti-life|shell|anti-?magic|aegis)"),
]


def tag_one(name: str, desc: str) -> list[str]:
    """Return a deduplicated list of spheres matched against name+desc."""
    blob = f"{name} | {desc}".lower()
    out = []
    seen = set()
    for sphere, pat in RULES:
        if re.search(pat, blob):
            if sphere not in seen:
                out.append(sphere)
                seen.add(sphere)
    return out


def main():
    import sys
    force = "--force" in sys.argv
    total_priest = 0
    already_tagged = 0
    newly_tagged = 0
    untagged = 0
    sphere_counter = Counter()
    per_mod = {}
    sample_untagged = []

    files = sorted(f for f in os.listdir(MODS_DIR) if f.endswith(".json"))
    for f in files:
        path = os.path.join(MODS_DIR, f)
        try:
            data = json.load(open(path, encoding="utf-8"), object_pairs_hook=OrderedDict)
        except Exception:
            continue
        spl = data.get("spl") or {}
        if not isinstance(spl, (dict, OrderedDict)):
            continue

        file_changes = 0
        for cn, comp in spl.items():
            if not isinstance(comp, (dict, OrderedDict)):
                continue
            new_list = comp.get("new")
            if not isinstance(new_list, list):
                continue
            for i, entry in enumerate(new_list):
                if not isinstance(entry, list) or len(entry) < 6:
                    continue
                if entry[1] != "priest":
                    continue
                total_priest += 1
                # 7th element is optional sph. With --force we re-tag from scratch;
                # without, we preserve existing tags (idempotent top-up mode).
                has_existing = len(entry) >= 7 and isinstance(entry[6], list) and entry[6]
                if has_existing and not force:
                    already_tagged += 1
                    for s in entry[6]:
                        sphere_counter[s] += 1
                    continue
                name = entry[4] if len(entry) > 4 and isinstance(entry[4], str) else ""
                desc = entry[5] if len(entry) > 5 and isinstance(entry[5], str) else ""
                spheres = tag_one(name, desc)
                if spheres:
                    # Extend entry to length 7 if needed
                    while len(entry) < 7:
                        entry.append(None)
                    if entry[6] != spheres:
                        entry[6] = spheres
                        newly_tagged += 1
                        file_changes += 1
                    else:
                        already_tagged += 1
                    for s in spheres:
                        sphere_counter[s] += 1
                else:
                    untagged += 1
                    # Clear stale sph if we're in force mode and no match
                    if force and has_existing:
                        entry[6] = None
                        file_changes += 1
                    if len(sample_untagged) < 20:
                        sample_untagged.append((f, entry[0], name))

        if file_changes:
            per_mod[f] = file_changes
            with open(path, "w", encoding="utf-8") as out:
                json.dump(data, out, indent=2, ensure_ascii=False)
                out.write("\n")

    print(f"Total mod-added priest spells: {total_priest}")
    print(f"  Already had sph:        {already_tagged}")
    print(f"  Newly tagged:           {newly_tagged}  ({100*newly_tagged/total_priest if total_priest else 0:.1f}%)")
    print(f"  No pattern match:       {untagged}")
    print()
    print("Sphere usage (total):")
    for s, c in sphere_counter.most_common():
        print(f"  {s:14} {c}")
    print()
    print("Per-mod tagging counts:")
    for f, c in sorted(per_mod.items(), key=lambda kv: -kv[1]):
        print(f"  {f:45} {c}")
    if sample_untagged:
        print()
        print(f"Sample of untagged spells ({len(sample_untagged)} shown):")
        for f, ref, name in sample_untagged:
            print(f"  {f:35} {ref:12} {name}")


if __name__ == "__main__":
    main()
