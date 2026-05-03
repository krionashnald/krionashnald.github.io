/**
 * cleanup_kit_names.js — Clean up scaffolded kit names
 *
 * Patterns fixed:
 * 1. Strip mod-name prefixes ("Artisan's Kitpack: X" → "X")
 * 2. Strip "Add <class> : " prefixes ("Add fighter : Marksman" → "Marksman")
 * 3. Strip trailing " Kit" when it's redundant
 * 4. Strip "Install " prefix
 * 5. Fix class inference from cleaned names
 * 6. Flag multi-kit placeholders (#1, #2...) for manual review
 *
 * Usage:
 *   node scripts/cleanup_kit_names.js           # Dry run
 *   node scripts/cleanup_kit_names.js --write   # Save changes
 */

const { readMods, writeMod } = require('./lib/mods-io');

const WRITE = process.argv.includes('--write');

// Known mod name prefixes to strip from kit names
const MOD_PREFIXES = [
  /^Artisan's Kitpack:\s*/i,
  /^The Artisan's Kitpack:\s*/i,
  /^Morpheus562's Kitpack:\s*/i,
  /^Tome and Blood:\s*/i,
  /^Might & Guile:\s*/i,
  /^Divine Remix:\s*/i,
  /^Song and Silence:\s*/i,
  /^Sword and Fist:\s*/i,
  /^Eldritch Magic:\s*/i,
  /^Monastic Orders:\s*/i,
  /^Hidden Kits:\s*/i,
  /^Bardic Wonders:\s*/i,
  /^D2 Workshop Kits:\s*/i,
  /^Will to Power:\s*/i,
];

// "Add <class> : Name" patterns
const ADD_CLASS_RE = /^Add\s+(?:fighter|ranger|paladin|cleric|druid|thief|bard|mage|monk|sorcerer|shaman)\s*(?:kit)?\s*:\s*/i;

// "Install ", "Add ", "New <class>:" prefixes
const INSTALL_RE = /^(?:Install|Add)\s+(?:the\s+)?/i;
const NEW_CLASS_RE = /^New\s+(?:wizard|cleric|druid|ranger|fighter|paladin|thief|bard|sorcerer|monk|shaman|class)\s*:\s*/i;
// "Sorcerer (X Bloodline)" → "X Bloodline" — strip class wrapper when in parens
const CLASS_PAREN_RE = /^(?:Sorcerer|Fighter|Ranger|Paladin|Cleric|Druid|Thief|Bard|Mage|Monk|Shaman)\s*\(([^)]+)\)\s*$/i;

// Trailing " Kit" or " kit" (but not if the whole name is just "Kit")
const TRAILING_KIT_RE = /\s+Kit$/i;

// Class inference
const CLASS_PATTERNS = [
  [/\bfighter\b/i, 'fighter'],
  [/\bwarrior\b/i, 'fighter'],
  [/\bberserker\b/i, 'fighter'],
  [/\bkensai\b/i, 'fighter'],
  [/\bbarbarian\b/i, 'barbarian'],
  [/\branger\b/i, 'ranger'],
  [/\bstalker\b/i, 'ranger'],
  [/\bbeastmaster\b/i, 'ranger'],
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
];

function inferClass(name) {
  for (const [pat, cls] of CLASS_PATTERNS) {
    if (pat.test(name)) return cls;
  }
  return null;
}

function cleanKitName(name) {
  let cleaned = name;

  // Strip mod prefixes
  for (const re of MOD_PREFIXES) {
    cleaned = cleaned.replace(re, '');
  }

  // Strip "Add <class> : " prefix
  cleaned = cleaned.replace(ADD_CLASS_RE, '');

  // Strip "Install/Add" prefix
  cleaned = cleaned.replace(INSTALL_RE, '');

  // Strip "New <class>:" prefix
  cleaned = cleaned.replace(NEW_CLASS_RE, '');

  // Strip "Sorcerer (X Bloodline)" → "X Bloodline"
  const parenMatch = cleaned.match(CLASS_PAREN_RE);
  if (parenMatch) cleaned = parenMatch[1];

  // Strip trailing " Kit"
  if (cleaned.length > 4) {
    cleaned = cleaned.replace(TRAILING_KIT_RE, '');
  }

  // Strip trailing class name only with 3+ words and preceding word isn't a class
  // "Arcane Archer Fighter" → "Arcane Archer", "Silverstar of Selune Cleric" → "Silverstar of Selune"
  // But NOT "Diablo2 Barbarian", "Force Mage" (2-word names keep class identity)
  const classWords = ['fighter','ranger','paladin','cleric','druid','thief','bard','mage','sorcerer','monk','shaman','barbarian'];
  const words = cleaned.split(/\s+/);
  if (words.length >= 3) {
    const last = words[words.length - 1].toLowerCase();
    const secondLast = words[words.length - 2].toLowerCase();
    if (classWords.includes(last) && !classWords.includes(secondLast)) {
      words.pop();
      cleaned = words.join(' ');
    }
  }

  return cleaned.trim();
}

function main() {
  const mods = readMods();
  let totalCleaned = 0;
  let totalPlaceholders = 0;

  mods.forEach(mod => {
    if (!mod.kits) return;

    let modChanged = false;
    const changes = [];

    Object.entries(mod.kits).forEach(([ci, entry]) => {
      if (!entry.new) return;

      entry.new.forEach(kit => {
        const oldName = kit[2];
        const newName = cleanKitName(oldName);

        // Check if it's a numbered placeholder
        if (/#\d+$/.test(newName)) {
          totalPlaceholders++;
        }

        if (newName !== oldName) {
          changes.push(`  "${oldName}" → "${newName}"`);
          kit[2] = newName;

          // Re-generate kit ID from cleaned name
          kit[0] = newName
            .replace(/[^a-zA-Z0-9\s]/g, '')
            .trim()
            .replace(/\s+/g, '_')
            .toUpperCase()
            .substring(0, 40);

          // Try to improve class inference from the original component name
          const comp = mod.co && mod.co[Number(ci)];
          const compName = comp ? comp.n : '';
          const betterClass = inferClass(compName) || inferClass(oldName);
          if (betterClass && kit[1] === 'fighter') {
            kit[1] = betterClass;
          }

          modChanged = true;
          totalCleaned++;
        }
      });
    });

    if (modChanged) {
      console.log(`${mod.n} (${mod.t}):`);
      changes.forEach(c => console.log(c));

      if (WRITE) {
        writeMod(mod);
      }
    }
  });

  console.log(`\n--- Summary ---`);
  console.log(`${totalCleaned} kit names cleaned`);
  console.log(`${totalPlaceholders} numbered placeholders remaining (need manual names)`);
  if (!WRITE) console.log(`\nDry run — use --write to save changes`);
}

main();
