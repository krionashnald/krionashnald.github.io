/**
 * populate_kits.js — Scaffold kit detail data for mods with k > 0 components
 *
 * Reads all mod detail files and generates skeleton `kits.new` entries
 * from component names. Many kit mods name their components after the kit,
 * e.g., "Battle Master Kit" → ["BATTLE_MASTER", "fighter", "Battle Master", ""]
 *
 * Usage:
 *   node scripts/populate_kits.js           # Dry run — shows what would change
 *   node scripts/populate_kits.js --write   # Actually write files
 */

const { readMods, writeMod, MODS_DIR } = require('./lib/mods-io');
const fs = require('fs');
const path = require('path');

const WRITE = process.argv.includes('--write');

// Class inference from component name keywords
const CLASS_PATTERNS = [
  [/\bfighter\b/i, 'fighter'],
  [/\bwarrior\b/i, 'fighter'],
  [/\bberserker\b/i, 'fighter'],
  [/\bkensai\b/i, 'fighter'],
  [/\bbarbarian\b/i, 'barbarian'],
  [/\branger\b/i, 'ranger'],
  [/\bpaladin\b/i, 'paladin'],
  [/\bcavalier\b/i, 'paladin'],
  [/\binquisitor\b/i, 'paladin'],
  [/\bblackguard\b/i, 'paladin'],
  [/\bcleric\b/i, 'cleric'],
  [/\bpriest\b/i, 'cleric'],
  [/\bdruid\b/i, 'druid'],
  [/\bshaman\b/i, 'shaman'],
  [/\bthief\b/i, 'thief'],
  [/\bassassin\b/i, 'thief'],
  [/\bshadowdancer\b/i, 'thief'],
  [/\bbounty.?hunter\b/i, 'thief'],
  [/\bswashbuckler\b/i, 'thief'],
  [/\bbard\b/i, 'bard'],
  [/\bblade\b/i, 'bard'],
  [/\bjester\b/i, 'bard'],
  [/\bskald\b/i, 'bard'],
  [/\bmage\b/i, 'mage'],
  [/\bwizard\b/i, 'mage'],
  [/\bsorcerer\b/i, 'sorcerer'],
  [/\bmonk\b/i, 'monk'],
  // Multi-class patterns
  [/\bf\/m\b/i, 'multi'],
  [/\bf\/t\b/i, 'multi'],
  [/\bf\/c\b/i, 'multi'],
  [/\bc\/m\b/i, 'multi'],
  [/\bc\/t\b/i, 'multi'],
  [/\bc\/r\b/i, 'multi'],
  [/\bmulti/i, 'multi'],
];

function inferClass(name) {
  for (const [pat, cls] of CLASS_PATTERNS) {
    if (pat.test(name)) return cls;
  }
  return 'fighter'; // default guess
}

function nameToId(name) {
  return name
    .replace(/\bkit\b/gi, '')
    .replace(/[^a-zA-Z0-9\s]/g, '')
    .trim()
    .replace(/\s+/g, '_')
    .toUpperCase()
    .substring(0, 40);
}

function cleanKitName(compName) {
  // Remove common suffixes like "Kit", "kit for ...", component number prefixes
  return compName
    .replace(/\s*\bkit\b\s*/gi, ' ')
    .replace(/^\d+\s*[-:]\s*/, '')
    .replace(/\s*\(.*?\)\s*$/, '')
    .trim();
}

function main() {
  const mods = readMods();
  let totalMods = 0;
  let totalKits = 0;
  let totalSkipped = 0;

  mods.forEach(mod => {
    if (!mod.co || mod.co.length === 0) return;

    // Check if any component has k > 0
    const hasKits = mod.co.some(c => (c.k || 0) > 0);
    if (!hasKits) return;

    // Skip if already has kits data
    if (mod.kits && Object.keys(mod.kits).length > 0) {
      totalSkipped++;
      return;
    }

    const kits = {};
    let modKitCount = 0;

    mod.co.forEach((comp, ci) => {
      const k = comp.k || 0;
      if (k === 0) return;

      const kitName = cleanKitName(comp.n || 'Unknown');
      const cls = inferClass(comp.n || '');

      // If k === 1, single kit from this component — use component name
      if (k === 1) {
        const kitId = nameToId(kitName || mod.t + '_' + ci);
        kits['' + ci] = {
          new: [[kitId, cls, kitName || comp.n, '']]
        };
        modKitCount++;
      } else {
        // k > 1: multiple kits from one component — create placeholder entries
        const entries = [];
        for (let j = 0; j < k; j++) {
          const kitId = nameToId((kitName || mod.t) + '_' + (j + 1));
          entries.push([kitId, cls, kitName + ' #' + (j + 1), '']);
        }
        kits['' + ci] = { new: entries };
        modKitCount += k;
      }
    });

    if (modKitCount > 0) {
      totalMods++;
      totalKits += modKitCount;
      console.log(`${mod.n} (${mod.t}): ${modKitCount} kits scaffolded`);

      if (WRITE) {
        mod.kits = kits;
        // Also compute kC for each component
        mod.co.forEach((comp, ci) => {
          if (kits['' + ci] && kits['' + ci].new) {
            const classCounts = {};
            kits['' + ci].new.forEach(([, cls]) => {
              classCounts[cls] = (classCounts[cls] || 0) + 1;
            });
            comp.kC = classCounts;
          }
        });
        writeMod(mod);
      }
    }
  });

  console.log(`\n--- Summary ---`);
  console.log(`${totalMods} mods with ${totalKits} kits scaffolded`);
  console.log(`${totalSkipped} mods already had kit data (skipped)`);
  if (!WRITE) {
    console.log(`\nDry run — use --write to save changes`);
  }
}

main();
