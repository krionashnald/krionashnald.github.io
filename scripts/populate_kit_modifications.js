/**
 * Populate kits.modify entries for mods that change vanilla kits
 */
const { readMod, writeMod } = require('./lib/mods-io');

function addModify(mod, ci, entries) {
  if (!mod.kits) mod.kits = {};
  if (!mod.kits['' + ci]) mod.kits['' + ci] = {};
  if (!mod.kits['' + ci].modify) mod.kits['' + ci].modify = [];
  entries.forEach(e => {
    if (!mod.kits['' + ci].modify.some(m => m[0] === e[0]))
      mod.kits['' + ci].modify.push(e);
  });
}

function findCoIdx(mod, pattern) {
  return mod.co.findIndex(c => pattern.test(c.n));
}

// ═══ BARDIC WONDERS (i=325) — Blade/Jester/Skald overhauls ═══
const bw = readMod(325);
if (bw) {
  // Find Blade Overhaul component
  bw.co.forEach((c, i) => {
    if (/blade overhaul/i.test(c.n)) {
      addModify(bw, i, [['BLADE', 'replace', 'Complete Blade overhaul with Blade Dancer, Weapons Display, revised Offensive/Defensive Spin']]);
    }
    if (/jester overhaul/i.test(c.n)) {
      addModify(bw, i, [['JESTER', 'replace', 'Complete Jester overhaul with Piercing Mockery song, Heckle, Mad Ramble abilities']]);
    }
    if (/skald overhaul/i.test(c.n)) {
      addModify(bw, i, [['SKALD', 'replace', 'Complete Skald overhaul with weapon specialization, Battle Song of Valor, Combat Casting']]);
    }
  });
  writeMod(bw);
  console.log('Bardic Wonders: vanilla kit modifications added');
}

// ═══ MIGHT & GUILE (i=335) ═══
const mg = readMod(335);
if (mg) {
  mg.co.forEach((c, i) => {
    if (/revised? archery|revised? archer/i.test(c.n)) {
      addModify(mg, i, [['ARCHER', 'tweak', 'Revised Called Shot abilities and archery mechanics']]);
    }
    if (/revised? stalker/i.test(c.n)) {
      addModify(mg, i, [['STALKER', 'tweak', 'Revised Stalker weapon proficiencies and abilities']]);
    }
    if (/revised? beastmaster/i.test(c.n)) {
      addModify(mg, i, [['BEASTMASTER', 'tweak', 'Revised Beastmaster weapon compatibility (daggers, axes, spears)']]);
    }
    if (/revised? monk/i.test(c.n)) {
      addModify(mg, i, [['SUN_SOUL_MONK', 'tweak', 'Revised monk fist items and abilities'],
                         ['DARK_MOON_MONK', 'tweak', 'Revised monk fist items and abilities']]);
    }
    if (/revised? backstab/i.test(c.n)) {
      addModify(mg, i, [['ASSASSIN', 'tweak', 'Revised backstab multiplier mechanics'],
                         ['BOUNTY_HUNTER', 'tweak', 'Revised backstab multiplier mechanics']]);
    }
    if (/revised? bard/i.test(c.n)) {
      addModify(mg, i, [['BLADE', 'tweak', 'Bard class overhaul with revised spell tables and skills'],
                         ['JESTER', 'tweak', 'Bard class overhaul with revised spell tables and skills'],
                         ['SKALD', 'tweak', 'Bard class overhaul with revised spell tables and skills']]);
    }
    if (/revised? swashbuckler/i.test(c.n)) {
      addModify(mg, i, [['SWASHBUCKLER', 'tweak', 'Revised Swashbuckler abilities and progression']]);
    }
  });
  writeMod(mg);
  console.log('Might & Guile: vanilla kit modifications added');
}

// ═══ SONG AND SILENCE (i=657) ═══
const ss = readMod(657);
if (ss) {
  // Component 0 fixes vanilla bard/thief kits
  const ci0 = findCoIdx(ss, /true bard|bard kit fix|component.*0/i);
  // Check all components for vanilla kit fixes
  ss.co.forEach((c, i) => {
    if (/blade.*fix|fix.*blade/i.test(c.n)) {
      addModify(ss, i, [['BLADE', 'tweak', 'Fixes Blade pick pockets skill']]);
    }
    if (/skald.*fix|fix.*skald/i.test(c.n)) {
      addModify(ss, i, [['SKALD', 'tweak', 'Fixes Skald THAC0 bonus']]);
    }
    if (/swashbuckler.*fix|revised? swash/i.test(c.n)) {
      addModify(ss, i, [['SWASHBUCKLER', 'tweak', 'Weapon proficiency and description fixes']]);
    }
  });
  writeMod(ss);
  console.log('Song and Silence: vanilla kit modifications added');
}

// ═══ SWORD AND FIST (i=315) ═══
const sf = readMod(315);
if (sf) {
  sf.co.forEach((c, i) => {
    if (/monk remix|revised? monk/i.test(c.n)) {
      addModify(sf, i, [['SUN_SOUL_MONK', 'replace', 'Complete monk overhaul: revised saves, abilities, fist items, stunning blow'],
                         ['DARK_MOON_MONK', 'replace', 'Complete monk overhaul: revised saves, abilities, fist items']]);
    }
  });
  writeMod(sf);
  console.log('Sword and Fist: vanilla kit modifications added');
}

// ═══ TALENTS OF FAERUN (i=683) ═══
const tof = readMod(683);
if (tof) {
  tof.co.forEach((c, i) => {
    if (/adjust.*vanilla.*priest|vanilla.*priest.*adjust/i.test(c.n)) {
      addModify(tof, i, [
        ['PRIEST_OF_HELM', 'tweak', 'Revised with sphere system and deity-specific abilities'],
        ['PRIEST_OF_TALOS', 'tweak', 'Revised with sphere system and deity-specific abilities'],
        ['PRIEST_OF_LATHANDER', 'tweak', 'Revised with sphere system and deity-specific abilities'],
        ['PRIEST_OF_TYR', 'tweak', 'Revised with sphere system and deity-specific abilities'],
        ['PRIEST_OF_TEMPUS', 'tweak', 'Revised with sphere system and deity-specific abilities'],
      ]);
    }
    if (/revised? weapon prof/i.test(c.n)) {
      addModify(tof, i, [
        ['BERSERKER', 'tweak', 'Revised weapon proficiency system'],
        ['KENSAI', 'tweak', 'Revised weapon proficiency system'],
        ['WIZARDSLAYER', 'tweak', 'Revised weapon proficiency system'],
        ['ARCHER', 'tweak', 'Revised weapon proficiency system'],
        ['STALKER', 'tweak', 'Revised weapon proficiency system'],
        ['CAVALIER', 'tweak', 'Revised weapon proficiency system'],
        ['INQUISITOR', 'tweak', 'Revised weapon proficiency system'],
        ['UNDEAD_HUNTER', 'tweak', 'Revised weapon proficiency system'],
      ]);
    }
  });
  writeMod(tof);
  console.log('Talents of Faerun: vanilla kit modifications added');
}

// ═══ FAITHS AND POWERS (i=339) ═══
const fnp = readMod(339);
if (fnp) {
  fnp.co.forEach((c, i) => {
    if (/cleric spell table|unnerfed cleric/i.test(c.n)) {
      addModify(fnp, i, [
        ['PRIEST_OF_HELM', 'tweak', 'Revised cleric spell progression table'],
        ['PRIEST_OF_TALOS', 'tweak', 'Revised cleric spell progression table'],
        ['PRIEST_OF_LATHANDER', 'tweak', 'Revised cleric spell progression table'],
      ]);
    }
    if (/druid.*cleric table|cleric.*druid/i.test(c.n)) {
      addModify(fnp, i, [
        ['TOTEMIC_DRUID', 'tweak', 'Druid uses cleric spell/XP tables'],
        ['SHAPESHIFTER', 'tweak', 'Druid uses cleric spell/XP tables'],
        ['AVENGER', 'tweak', 'Druid uses cleric spell/XP tables'],
      ]);
    }
  });
  writeMod(fnp);
  console.log('Faiths and Powers: vanilla kit modifications added');
}

console.log('\nDone!');
