/**
 * populate_kit_descriptions.js — Fill in kit descriptions from tp2/tra sources
 * Truncated to ~100-120 chars from the first sentence of the in-game description
 */
const { readMods, writeMod } = require('./lib/mods-io');

const DESCS = {
  // ═══ TALENTS OF FAERUN (i=683) ═══
  // Bloodlines
  'Arcane Bloodline': 'Natural gift for magic of unknown origin. Bonus spell slots and arcane power that grows with experience.',
  'Shadowed Bloodline': 'Touched by the Plane of Shadow. Gains shadow magic abilities, stealth bonuses, and resistance to darkness.',
  'Fey Bloodline': 'Touched by capricious fey nature. Gains charm abilities, woodland stride, and fey-themed innate powers.',
  'Celestial Bloodline': 'Blessed by celestial power. Gains holy resistance, healing abilities, and radiant damage bonuses.',
  'Fiendish Bloodline': 'Tainted by fiendish influence. Gains fire resistance, dark abilities, and infernal innate powers.',
  'Gravetouched Bloodline': 'Tainted by the grave. Gains undead resistance, necromantic abilities, and death-themed powers.',
  'Stormborn Bloodline': 'Born in the heart of a storm. Gains lightning abilities, electrical resistance, and storm-themed powers.',
  'Efreeti Bloodline': 'Descended from efreeti of the Plane of Fire. Gains fire abilities, heat resistance, and flame powers.',
  'Rimefrost Bloodline': 'Ice runs in these veins. Gains cold abilities, frost resistance, and winter-themed innate powers.',
  // Dragon Disciples
  'Red Dragon Disciple': 'Chromatic red dragon heritage. Fire breath weapon, fire resistance, AC and HP bonuses.',
  'Blue Dragon Disciple': 'Chromatic blue dragon heritage. Lightning breath weapon, electrical resistance, AC and HP bonuses.',
  'Green Dragon Disciple': 'Chromatic green dragon heritage. Acid breath weapon, acid resistance, AC and HP bonuses.',
  'Black Dragon Disciple': 'Chromatic black dragon heritage. Acid breath weapon, acid resistance, AC and HP bonuses.',
  // Elementalists
  'Fire Elementalist': 'Specialist wizard focusing on fire magic. Extra fire spell slot per level. Cannot cast water/ice spells.',
  'Water Elementalist': 'Specialist wizard focusing on water magic. Extra water spell slot per level. Cannot cast fire spells.',
  'Air Elementalist': 'Specialist wizard focusing on air magic. Extra air spell slot per level. Cannot cast earth spells.',
  'Earth Elementalist': 'Specialist wizard focusing on earth magic. Extra earth spell slot per level. Cannot cast air spells.',
  // Single kits
  'Force Mage': 'Specialist wizard focusing on pure magical force. Uses force missiles, walls, and shields.',
  'Bloodrager': 'Sorcerer whose innate magic is tied to deep rage. Can enter a magical frenzy combining arcane and fury.',
  'Favored Soul': 'Divine caster chosen by a deity. Casts divine spells spontaneously like a sorcerer.',
  // Blackguards
  'Thrall of Orcus': 'Blackguard devoted to Orcus, demon prince of undeath. Gains undead command and necromantic powers.',
  'Disciple of Asmodeus': 'Blackguard who made an unholy pact with Asmodeus. Gains infernal powers and fiendish abilities.',
  // Specialty Priests
  'Hammer of Moradin': 'Dwarven priest-warrior of the chief dwarven deity. Combines martial prowess with divine forge magic.',
  'Forgemaster of Moradin': 'Dwarven smith-priest of Moradin. Expert in crafting and divine forge magic.',
  'Berserker-Priest of Tempus': 'War priest who channels Tempus through berserker fury. Combines rage with divine battle magic.',
  'Fury of Talos': 'Priest of the storm god. Commands lightning and destructive weather magic.',
  'Sword of Selune': 'Warrior-priest of the moon goddess. Combines swordplay with lunar divine magic.',
  'Magehunter of Helm': 'Priest trained to counter arcane magic. Dispel Magic at enhanced power, magic resistance.',
  'Dark Knight of Bane': 'Dark warrior-priest of the god of tyranny. Fear aura, dark divine magic.',
  'Knight of Iyachtu Xvim': 'Priest of the Son of Bane. Commands fear and dark divine power.',
  'Templar of Lathander': 'Holy warrior of the Morninglord. Bonus vs undead, radiant abilities.',
  'Holy Justice of Tyr': 'Priest-knight of the god of justice. Detects evil, smites the unjust.',
  'Guardian of Helm': 'Defensive priest of the Watcher. Protection aura, enhanced vigilance abilities.',
  'Demarch of Mask': 'Priest of the god of thieves. Stealth abilities combined with shadow divine magic.',
  'Shadow of Mask': 'Shadow priest of Mask. Enhanced stealth, shadow magic, and divine thievery.',
  'Lorekeeper of Oghma': 'Knowledge priest of the god of invention. Enhanced lore, identification, and divination.',
  'Diviner of Oghma': 'Divination specialist priest of Oghma. Scrying and knowledge-seeking divine magic.',
  'Painbearer of Ilmater': 'Priest of the Crying God. Absorbs pain of others, enhanced healing, endurance.',
  'Abjurer of Ilmater': 'Protective priest of Ilmater. Specializes in abjuration and shielding divine magic.',
  'Luckbringer of Tymora': 'Priest of Lady Luck. Luck-based abilities, fortune favors in combat and saves.',
  'Deathstalker of Bhaal': 'Priest of the dead god of murder. Assassination abilities and death magic.',
  'Firewalker of Kossuth': 'Priest of the Firelord. Fire immunity, flame-based divine magic.',
  'Dweomerkeeper of Mystra': 'Priest of the goddess of magic. Combines arcane and divine spellcasting.',
  // Multi-class (ToF)
  'Raging Flame of Kossuth': 'Fighter/Cleric of Kossuth. Berserker rage combined with fire divine magic.',
  'Axe of Clangeddin': 'Fighter/Cleric of the dwarven battle god. Axe specialization with divine power.',
  'Battlerager of Clangeddin': 'Fighter/Cleric. Dwarven rage combined with Clangeddin battle prayers.',
  'Wrathful Spear of Gruumsh': 'Fighter/Cleric of the orc god. Spear mastery with orcish war prayers.',
  'Crusader of Tyr': 'Fighter/Cleric of the god of justice. Holy warrior combining martial and divine skill.',
  'Shaman of Tempus': 'Fighter/Cleric of the war god. Battle meditation and war priest abilities.',
  'Abjurant Defender': 'Fighter/Mage specializing in protective magic. Abjuration combined with martial skill.',
  'Silent Sword': 'Fighter/Thief stealth warrior. Combines backstab with fighter combat mastery.',
  'Magetracker': 'Fighter/Thief trained to hunt mages. Spell disruption and tracking abilities.',
  'Nightstalker of Malar': 'Cleric/Ranger of the Beastlord. Hunting abilities combined with bestial divine magic.',
  'Forester of Baervan': 'Cleric/Ranger of the gnome nature god. Forest stealth with divine nature magic.',
  'Scout of Corellon': 'Cleric/Ranger of the elven god. Elven archery combined with divine magic.',
  'Night Wolf': 'Druid/Ranger shapeshifter. Wolf form with druidic nature magic.',
  'Swashbuckler of Sune': 'Cleric/Thief of the goddess of beauty. Charm abilities with roguish combat.',
  'Assassin of Talona': 'Cleric/Thief of the plague goddess. Poison abilities with dark divine magic.',
  'Assassin of Cyric': 'Cleric/Thief of the god of strife. Murder and deception with divine power.',
  'Thief of Mask': 'Cleric/Thief of the god of shadows. Shadow abilities with divine thievery.',
  'Thief of Tymora': 'Cleric/Thief of Lady Luck. Luck-enhanced thieving with divine fortune.',
  'Bounty Hunter of Malar': 'Cleric/Thief of the Beastlord. Tracking and trapping with bestial divine magic.',
  'Silent Avenger': 'Druid/Thief combining nature magic with stealth assassination.',
  'Guardian of Corellon': 'Fighter/Mage/Cleric of the elven god. Triple-class elven champion.',
  'Adventurer of Tymora': 'Fighter/Mage/Cleric of Lady Luck. Lucky jack-of-all-trades.',
  'Polymath of Mystra': 'Fighter/Mage/Cleric of Mystra. Master of all three arts through magical devotion.',
  'Totemic Shaman': 'Fighter/Druid with enhanced animal summoning and totemic powers.',
  'Raging Shifter': 'Fighter/Druid combining berserker rage with druidic shapeshifting.',

  // ═══ FAITHS AND POWERS (i=339) ═══
  'Cleric of Lathander': 'Priest of the Morninglord, god of renewal. Dawn-themed healing and anti-undead powers.',
  'Cleric of Torm': 'Priest of the True God, patron of paladins. Martial divine caster with honor-bound powers.',
  'Cleric of Tymora': 'Priest of Lady Luck. Fortune-based divine magic and luck manipulation.',
  'Cleric of Helm': 'Priest of the Vigilant One. Protection and warding divine abilities.',
  'Cleric of Kelemvor': 'Priest of the Lord of the Dead. Anti-undead powers and death domain magic.',
  'Cleric of Tempus': 'Priest of the Lord of Battles. War domain with combat divine magic.',
  'Cleric of Leira': 'Priest of the goddess of illusion. Deception and illusion divine magic.',
  'Cleric of Loviatar': 'Priest of the Maiden of Pain. Pain-inflicting divine magic.',
  'Stormbringer of Talos': 'Priest of the Destroyer. Storm and lightning divine magic.',
  'Sworn of Cyric': 'Priest of the Prince of Lies. Deception and strife divine magic.',
  'Waveservant of Umberlee': 'Priest of the Bitch Queen. Water and storm divine magic.',
  'Priest of Oghma': 'Priest of the Binder of Knowledge. Lore and divination divine magic.',
  'Priest of Ilmater': 'Priest of the Crying God. Healing and endurance divine magic.',
  'Priest of Deneir': 'Priest of the Scribe of Oghma. Knowledge and glyph divine magic.',
  'Priest of Sune': 'Priest of Firehair. Beauty and charm divine magic.',
  'Battleguard of Tempus': 'Elite warrior-priest of the war god. Enhanced combat and war domain magic.',
  'Priest of Azuth': 'Priest of the High One. Magic domain combining arcane and divine.',
  'Priest of Shar': 'Priest of the Mistress of the Night. Darkness and loss divine magic.',
  'Priest of Moander': 'Priest of the Darkbringer. Corruption and decay divine magic.',
  'Priest of Beshaba': 'Priest of the Maid of Misfortune. Bad luck and misfortune divine magic.',
  'Ur-Priest': 'Heretical priest who steals divine power. No deity allegiance, raw divine energy.',
  // FnP Druids
  'Forest Druid': 'Druid attuned to temperate woodlands. Enhanced plant and animal magic in forests.',
  'Mountain Druid': 'Druid of highland realms. Stone and storm nature magic, cold resistance.',
  'Jungle Druid': 'Druid of tropical wilds. Poison resistance, insect and plant magic.',
  'Desert Druid': 'Druid of arid wastes. Heat resistance, sand and sun nature magic.',
  'Arctic Druid': 'Druid of frozen tundra. Cold resistance, ice and snow nature magic.',
  'Cave Druid': 'Druid of the Underdark. Darkvision, stone and fungal nature magic.',
  'Beast Lord': 'Druid focused on animal companionship. Enhanced summoning and animal empathy.',
  'Elementalist': 'Druid channeling elemental forces. Access to elemental spells across domains.',
  'Hivekeeper': 'Druid who tends insect colonies. Insect summoning and swarm abilities.',
  'Shadow Druid': 'Militant druid extremist. Aggressive nature magic, hostility to civilization.',
  'Lost Druid': 'Druid displaced from their grove. Wandering nature magic, adaptable abilities.',
  'Chaos Priest': 'Chaotic divine caster. Unpredictable wild magic effects on spells.',
  // FnP Paladins
  'Champion of Tyr': 'Holy champion of the god of justice. Smite evil, detect injustice.',
  'Champion of Kelemvor': 'Holy champion of the Lord of the Dead. Anti-undead crusader.',
  'Champion of Tempus': 'Holy champion of the war god. Battle prowess and war domain abilities.',
  'Champion of Bane': 'Dark champion of the god of tyranny. Fear aura and domination powers.',
  'Champion of Helm': 'Holy champion of the Watcher. Protection aura and vigilant defense.',
  'Champion of Talos': 'Dark champion of the storm god. Lightning and destructive storm powers.',
  'Champion of Moradin': 'Dwarven holy champion of the Soul Forger. Forge-blessed weapons and armor.',
  'Champion of Azuth': 'Holy champion of the High One. Spell resistance and anti-magic crusader.',
  'Champion of the Red Knight': 'Holy champion of the goddess of strategy. Tactical combat bonuses.',
  'Champion of Gruumsh': 'Orcish champion of the One-Eyed God. Berserker rage with dark divine power.',
  'Champion of Kossuth': 'Holy champion of the Firelord. Fire abilities and elemental divine power.',
  'Champion of Ilmater': 'Holy champion of the Crying God. Damage absorption and healing powers.',
  'Champion of Garagos': 'Dark champion of the god of war and destruction. Berserker fury.',
  'Champion of Corellon': 'Elven holy champion of the Creator. Elven grace with divine power.',

  // ═══ MORPHEUS562 (i=320) ═══
  'Battle Master': 'Two-handed weapon expert who wreaks havoc on the battlefield with powerful cleaving attacks.',
  'Psi Warrior': 'Fighter augmenting physical might with psi-infused abilities. Telekinetic strikes and mental shields.',
  'Shield Breaker': 'Specialized fighter whose purpose is destroying enemy defenses. Sunder abilities.',
  'Dragoon': 'Warrior dedicated to polearm combat. Charging attacks and reach weapon mastery.',
  'Death Knight': 'Fallen warrior wielding dark powers. Undead abilities and fear aura.',
  'Archmage Prestige': 'Powerful spellcaster dedicated to the art of magic. Enhanced arcane power and spell mastery.',
  'Kaze no Kama': 'Eastern martial artist wielding wind-based ki powers. Ranged ki strikes and wind abilities.',
  'Champion of the Silver Flame': 'Paladin dedicated to fighting supernatural evil. Bonus vs fiends and undead.',
  'Templar': 'Favored knight defending the faith. Enhanced divine combat abilities.',
  'Reaver': 'Evil warrior reveling in death and destruction. Vampiric strikes and fear.',
  'Oathbreaker': 'Fallen paladin who broke sacred oaths. Dark powers from broken divine bonds.',
  'Grey Knight': 'Neutral paladin balancing good and evil. Flexible alignment with modified abilities.',

  // ═══ MIGHT & GUILE (i=335) ═══
  'Corsair': 'Dashing fighter-rogue hybrid. Part warrior, part charming sailor with roguish combat tricks.',
  'Sohei': 'Fighter drawing on implacable fighting spirit. Monk-like focus with fighter combat training.',
  'Ironsmith': 'Master weapon and armor forger. Crafting abilities and enhanced equipment maintenance.',
  'Barbarian Ranger': 'Combines barbarian fury with ranger wilderness skills and dual-wielding.',
  'Mage Hunter': 'Ranger specializing in tracking and countering arcane spellcasters. Spell disruption.',
  'Elven Archer': 'Elven ranger variant with superior archery. Enhanced ranged combat abilities.',
  'Rake': 'Roguish charmer combining thief skills with swashbuckling flair.',
  'Ninja': 'Eastern assassin with stealth mastery. Poison, disguise, and silent killing techniques.',
  'Slinger': 'Halfling specialist in sling combat. Enhanced ranged damage with slings.',
  'Marksman': 'Thief variant focused on ranged combat. Sniper-like precision with ranged weapons.',
  'Jongleur': 'Acrobatic bard combining juggling, tumbling, and performance with light combat.',
  'Gallant': 'Courtly bard skilled in diplomacy and noble combat. Charm and inspire abilities.',
  'Meistersinger': 'Master vocalist whose songs carry enhanced magical power and duration.',
  'Loresinger': 'Scholarly bard preserving ancient knowledge through song. Enhanced lore abilities.',
  'Barbarian/Thief': 'Combines barbarian rage and toughness with thief stealth and skills.',
  'Tomb Runner': 'Adventurer specializing in dungeon exploration. Trap expertise and ancient lore.',
  'Thug': 'Rogue who applies violence effectively. Enhanced combat abilities for a thief.',
  'Spellfilcher': 'Mage/Thief who steals magical protections and spell effects from enemies.',
  'Loremaster': 'Scholar combining arcane and roguish knowledge. Enhanced identification and lore.',

  // ═══ SONG AND SILENCE (i=657) ═══
  'Acrobat': 'Entertainer from carnivals and circuses. Tumbling, balance, and evasion abilities.',
  'Chorister': 'Sacred singer whose hymns carry divine power. Enhanced healing and buffing songs.',
  'Dirgesinger': 'Singer of sorrow and doom. Songs debuff enemies with fear, weakness, and despair.',
  'Luring Piper': 'Musician who charms and controls creatures with enchanting melodies. Rat-catcher origins.',
  'Adventurer': 'Jack-of-all-trades thief focused on exploration rather than crime. Balanced skills.',
  'Burglar': 'Expert at breaking and entering. Enhanced Pick Locks, Find Traps, and stealth.',
  'Soulknife': 'Psionic thief who manifests a blade of mental energy. Psychic combat abilities.',
  'Sharpshooter': 'Stealthy ranged specialist preferring to engage enemies from a distance.',
  'Shadowdancer': 'Nimble warrior operating between light and darkness. Shadow Step and stealth mastery.',

  // ═══ ELDRITCH MAGIC (i=640) ═══
  'Abyssal Warrior': 'Veteran of the Blood War thriving in demonic environments. Fiendish combat abilities.',
  'Bladesinger': 'Deadly elven warrior combining swordplay with arcane magic in elegant combat.',
  'Eldritch Knight': 'Combines martial mastery with arcane spellcasting. Armored mage-warrior.',
  'Herbalist': 'Nature healer using plant-based remedies. Druid variant focused on healing arts.',
  'Priest of Mystra': 'Cleric of the goddess of magic. Combines divine and arcane understanding.',
  'Priestess of Lolth': 'Cleric of the Spider Queen. Dark divine magic and spider summoning.',
  'Undead Hunter for Elves': 'Elven paladin variant dedicated to destroying undead threats.',
  'War Wizard': 'Elven combat mage trained for warfare. Offensive spellcasting with light armor.',
  'Wilderness Runner': 'Elven ranger deeply connected to the wilds. Enhanced speed and nature tracking.',
  'Windrider': 'Elven ranger with wind and aerial abilities. Enhanced movement and ranged combat.',

  // ═══ DIVINE REMIX (i=338) ═══
  'Silverstar of Selune': 'Cleric of the Moonmaiden. Lunar magic, protection against lycanthropes and shapeshifters.',
  'Nightcloak of Shar': 'Cleric of the Mistress of the Night. Shadow and darkness divine magic.',
  'Holy Strategist of the Red Knight': 'Cleric of the goddess of strategy. Tactical buffs and battlefield control.',
  'Painbearer of Ilmater': 'Cleric of the Crying God. Absorbs pain of allies, enhanced healing.',
  'Firewalker of Kossuth': 'Cleric of the Firelord. Fire immunity and flame divine magic.',
  'Authlim of Iyachtu Xvim': 'Cleric of the Son of Bane. Dark commanding presence and fear magic.',
  'Heartwarder of Sune': 'Cleric of Firehair. Charm and beauty divine magic.',
  'Feywarden of Corellon': 'Cleric of the elven Creator. Elven grace with divine nature magic.',
  'Strifeleader of Cyric': 'Cleric of the Prince of Lies. Deception and conflict divine magic.',
  'Bowslinger': 'Ranger variant with sling proficiency. Enhanced ranged combat with slings.',
  'Feralan': 'Wild ranger raised by animals. Feral combat style, enhanced animal empathy.',
  'Forest Runner': 'Swift ranger excelling at woodland pursuit. Enhanced speed and tracking.',
  'Justifier': 'Ranger dedicated to opposing planar creatures. Extra-planar hunting abilities.',
  'Oozemaster': 'Druid who studies oozes and slimes. Ooze summoning and acid resistance.',

  // ═══ SHAMAN KITS ═══
  'Spiritwalker': 'Shaman walking between the mortal and spirit worlds. Enhanced spirit communication.',
  'Storm Caller': 'Shaman channeling storm spirits. Lightning and thunder shamanic abilities.',
  'Town Medium': 'Urban shaman serving as intermediary between townsfolk and spirits.',
  'Witchlight': 'Shaman wielding will-o-wisp-like spirit lights. Illumination and spirit fire magic.',
  'Mistweaver': 'Half-orc shaman calling mist spirits. Obscuring mists and spirit concealment.',

  // ═══ MISC ═══
  'Chaos Knight': 'Warrior of chaos wielding unpredictable combat abilities. Random magical effects in battle.',
  'Kit Mule': 'Utility kit that enables kit-related functionality for other mods.',
  'Seducer': 'Charming thief using beauty and persuasion. Enhanced charm and deception abilities.',
  'Shadow Monk': 'Monk wielding shadow magic. Shadow Step, blindness, and dark ki abilities.',
  'Dark Hunter': 'Ranger stalking prey through darkness. Enhanced stealth and night-hunting abilities.',
  'Arcane Trickster': 'Thief with minor arcane talent. Combines roguish skills with illusion magic.',
  'Sylvan Disciple': 'Sorcerer attuned to nature spirits. Druidic spell access with spontaneous casting.',
  'Revenant Disciple': 'Sorcerer touched by undeath. Necromantic sorcery and deathless resilience.',
  'Bow Knight': 'Paladin variant focused on archery. Ranged holy warrior with mounted combat.',
  'Dwarven Artificer': 'Dwarven thief specializing in mechanical devices and traps. Expert tinkerer.',
  'Shadow Slinger': 'Halfling ranged specialist hiding in shadows. Stealth-based sling attacks.',
  'Hybrid Agent': 'Half-elf bard/infiltrator. Combines bardic performance with espionage skills.',
  'Wildguard': 'Elven fighter defending wild places. Nature-attuned combat abilities.',
  'Twilight Blade': 'Elven shadow warrior. Combines stealth with fighter combat in twilight conditions.',
  'Mirrorblade': 'Gnome fighter/mage using reflection magic. Illusory doubles and mirror strikes.',
  'Frostmaster': 'Mage specializing in cold and ice magic. Frost spells and cold resistance.',
};

const mods = readMods();
let filled = 0;
let skipped = 0;

mods.forEach(mod => {
  if (!mod.kits) return;
  let modChanged = false;
  Object.entries(mod.kits).forEach(([ci, entry]) => {
    if (!entry.new) return;
    entry.new.forEach(k => {
      const name = k[2];
      const currentDesc = k[3];
      if (currentDesc && currentDesc.length > 10) { skipped++; return; } // already has desc
      if (DESCS[name]) {
        k[3] = DESCS[name];
        modChanged = true;
        filled++;
      }
    });
  });
  if (modChanged) writeMod(mod);
});

console.log('Filled ' + filled + ' descriptions, skipped ' + skipped + ' (already had descriptions)');
