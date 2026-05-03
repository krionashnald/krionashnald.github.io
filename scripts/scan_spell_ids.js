#!/usr/bin/env node
/**
 * scan_spell_ids.js — Scan extracted mod tp2/tpa/tph files for SPELL.IDS additions
 *
 * Finds all APPEND to spell.ids, parses spell IDs to extract type+level,
 * and generates spLv data per mod.
 *
 * Usage: node tools/scan_spell_ids.js [extractedDir]
 * Default extractedDir: F:\BGMods\Extracted
 */

const fs = require('fs');
const path = require('path');

const EXTRACTED_DIR = process.argv[2] || 'F:\\BGMods\\Extracted';
const MODS_DIR = path.join(__dirname, '..', 'data', 'mods');

// Parse a 4-digit spell ID into type + level
// First digit: 1=priest, 2=wizard, 3=psionic, 4=innate/SPCL
// Second digit: spell level
// Last two digits: slot number
function parseSpellId(num) {
  const n = parseInt(num);
  if (isNaN(n) || n < 1000 || n > 9999) return null;
  const type = Math.floor(n / 1000);
  const level = Math.floor((n % 1000) / 100);
  const slot = n % 100;

  let typeKey = null;
  if (type === 1 && level >= 1 && level <= 7) typeKey = 'p' + level; // priest
  else if (type === 2 && level >= 1 && level <= 9) typeKey = 'w' + level; // wizard
  // type 3 = psionic, type 4 = innate/SPCL — don't count toward spell level caps

  return { type, level, slot, typeKey, raw: n };
}

// Recursively find all tp2/tpa/tph files in a directory
function findModFiles(dir) {
  const results = [];
  try {
    const entries = fs.readdirSync(dir, { withFileTypes: true });
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        results.push(...findModFiles(full));
      } else if (/\.(tp2|tpa|tph)$/i.test(e.name)) {
        results.push(full);
      }
    }
  } catch (err) { /* skip unreadable dirs */ }
  return results;
}

// Extract APPEND spell.ids entries from file content
function extractAppends(content, filePath) {
  const results = [];
  const dynamic = [];

  // Pattern 1: APPEND ~spell.ids~ ~NNNN SPELL_NAME~ (with optional UNLESS)
  // Also handles: APPEND "spell.ids" "NNNN SPELL_NAME"
  const appendPattern = /APPEND\s+[~"](?:spell\.ids|SPELL\.IDS)[~"]\s+[~"]([^~"]*)[~"]/gi;
  let match;
  while ((match = appendPattern.exec(content)) !== null) {
    const appendContent = match[1].trim();

    // Check if it contains variables (%...%)
    if (/%[^%]+%/.test(appendContent)) {
      dynamic.push({ line: appendContent, file: filePath });
      continue;
    }

    // Parse: "NNNN SPELL_NAME" or "NNNN\tSPELL_NAME"
    const spellMatch = appendContent.match(/^(\d{4})\s+(\S+)/);
    if (spellMatch) {
      const parsed = parseSpellId(spellMatch[1]);
      if (parsed) {
        results.push({
          id: parsed.raw,
          name: spellMatch[2],
          typeKey: parsed.typeKey,
          type: parsed.type,
          level: parsed.level,
          file: filePath
        });
      }
    }
  }

  // Pattern 2: Multi-line APPEND blocks
  // APPEND ~spell.ids~
  //   ~NNNN NAME~
  //   ~NNNN NAME~
  // END (or similar)
  const blockPattern = /APPEND\s+[~"](?:spell\.ids|SPELL\.IDS)[~"]\s*\n([\s\S]*?)(?:^(?:END|UNLESS|IF|ACTION)|\n\n)/gmi;
  while ((match = blockPattern.exec(content)) !== null) {
    const block = match[1];
    const lines = block.split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('//') || trimmed.startsWith('*')) continue;

      // Check for variables
      if (/%[^%]+%/.test(trimmed)) {
        if (!dynamic.some(d => d.line === trimmed)) {
          dynamic.push({ line: trimmed, file: filePath });
        }
        continue;
      }

      const spellMatch = trimmed.match(/(\d{4})\s+(\S+)/);
      if (spellMatch) {
        const parsed = parseSpellId(spellMatch[1]);
        if (parsed && !results.some(r => r.id === parsed.raw && r.name === spellMatch[2])) {
          results.push({
            id: parsed.raw,
            name: spellMatch[2],
            typeKey: parsed.typeKey,
            type: parsed.type,
            level: parsed.level,
            file: filePath
          });
        }
      }
    }
  }

  return { results, dynamic };
}

// Map extracted folder name to mod database
function loadModDatabase() {
  const catalogPath = path.join(MODS_DIR, '_catalog.json');
  const catalog = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));

  const mods = {};
  for (const [id, filename] of Object.entries(catalog)) {
    try {
      const modData = JSON.parse(fs.readFileSync(path.join(MODS_DIR, filename), 'utf8'));
      mods[modData.t.toLowerCase()] = { id: parseInt(id), filename, data: modData };
    } catch (e) { /* skip */ }
  }
  return mods;
}

// Main
function main() {
  console.log(`Scanning ${EXTRACTED_DIR} for SPELL.IDS additions...\n`);

  // Find all mod folders that contain APPEND spell.ids
  const modFolders = fs.readdirSync(EXTRACTED_DIR, { withFileTypes: true })
    .filter(e => e.isDirectory())
    .map(e => e.name);

  const allResults = {};
  const allDynamic = {};
  let totalSpells = 0;
  let totalDynamic = 0;

  for (const folder of modFolders) {
    const modDir = path.join(EXTRACTED_DIR, folder);
    const files = findModFiles(modDir);

    let modSpells = [];
    let modDynamic = [];

    for (const file of files) {
      try {
        const content = fs.readFileSync(file, 'utf8');
        if (!/APPEND[\s\S]*?spell\.ids/i.test(content)) continue;

        const { results, dynamic } = extractAppends(content, path.relative(EXTRACTED_DIR, file));
        modSpells.push(...results);
        modDynamic.push(...dynamic);
      } catch (e) { /* skip */ }
    }

    // Deduplicate by spell ID
    const seen = new Set();
    modSpells = modSpells.filter(s => {
      const key = s.id + '_' + s.name;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    if (modSpells.length > 0 || modDynamic.length > 0) {
      allResults[folder] = modSpells;
      if (modDynamic.length > 0) allDynamic[folder] = modDynamic;
      totalSpells += modSpells.length;
      totalDynamic += modDynamic.length;
    }
  }

  // Build spLv per mod
  const spLvByMod = {};
  for (const [folder, spells] of Object.entries(allResults)) {
    const spLv = {};
    for (const s of spells) {
      if (s.typeKey) {
        spLv[s.typeKey] = (spLv[s.typeKey] || 0) + 1;
      }
    }
    if (Object.keys(spLv).length > 0) {
      spLvByMod[folder] = {
        spLv,
        sp: Object.values(spLv).reduce((a, b) => a + b, 0),
        spells: spells.filter(s => s.typeKey), // only wizard/priest
        innate: spells.filter(s => !s.typeKey).length,
        details: spells
      };
    }
  }

  // Load mod database for comparison
  const modDb = loadModDatabase();

  // Output report
  console.log('=== SPELL.IDS EXTRACTION REPORT ===\n');
  console.log(`Mods scanned: ${modFolders.length}`);
  console.log(`Mods with SPELL.IDS additions: ${Object.keys(allResults).length}`);
  console.log(`Total spells found: ${totalSpells}`);
  console.log(`Dynamic/variable entries (need manual review): ${totalDynamic}\n`);

  // Per-level summary
  const levelTotals = {};
  for (const mod of Object.values(spLvByMod)) {
    for (const [key, count] of Object.entries(mod.spLv)) {
      levelTotals[key] = (levelTotals[key] || 0) + count;
    }
  }

  console.log('=== PER-LEVEL TOTALS (all mods combined) ===');
  console.log('Wizard:');
  for (let i = 1; i <= 9; i++) {
    const key = 'w' + i;
    console.log(`  L${i}: ${levelTotals[key] || 0} new spells`);
  }
  console.log('Priest:');
  for (let i = 1; i <= 7; i++) {
    const key = 'p' + i;
    console.log(`  L${i}: ${levelTotals[key] || 0} new spells`);
  }

  // Per-mod breakdown
  console.log('\n=== PER-MOD BREAKDOWN ===\n');
  const sortedMods = Object.entries(spLvByMod).sort((a, b) => b[1].sp - a[1].sp);

  for (const [folder, data] of sortedMods) {
    const spLvStr = Object.entries(data.spLv)
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([k, v]) => `${k}:${v}`)
      .join(', ');

    console.log(`${folder} — ${data.sp} wizard/priest spells (${data.innate} innate/other)`);
    console.log(`  spLv: { ${spLvStr} }`);

    // Compare with database
    // Try to find matching mod in database by tp2 name
    const tp2Names = new Set();
    for (const s of data.details) {
      // Extract tp2 name from file path (first subfolder after mod folder)
      const parts = s.file.split(/[/\\]/);
      if (parts.length >= 2) tp2Names.add(parts[1].toLowerCase());
    }

    let dbMatch = null;
    for (const tp2 of tp2Names) {
      if (modDb[tp2]) { dbMatch = modDb[tp2]; break; }
    }

    if (dbMatch) {
      // Check existing sp values
      const existingSp = dbMatch.data.co
        ? dbMatch.data.co.reduce((sum, c) => sum + (c.sp || 0), 0)
        : 0;
      if (existingSp > 0) {
        console.log(`  DB: ${dbMatch.filename} — existing sp total: ${existingSp} ${existingSp === data.sp ? '✓' : '⚠ MISMATCH'}`);
      } else {
        console.log(`  DB: ${dbMatch.filename} — NO sp tracking`);
      }
    } else {
      console.log(`  DB: NOT FOUND in mod database`);
    }
    console.log('');
  }

  // Dynamic entries needing manual review
  if (Object.keys(allDynamic).length > 0) {
    console.log('=== DYNAMIC ENTRIES (NEED MANUAL REVIEW) ===\n');
    for (const [folder, entries] of Object.entries(allDynamic)) {
      console.log(`${folder}:`);
      for (const e of entries) {
        console.log(`  ${e.file}: ${e.line}`);
      }
      console.log('');
    }
  }

  // Output JSON for data import
  const jsonOutput = {};
  for (const [folder, data] of Object.entries(spLvByMod)) {
    jsonOutput[folder] = {
      spLv: data.spLv,
      sp: data.sp,
      innate: data.innate,
      spells: data.spells.map(s => ({
        id: s.id,
        name: s.name,
        typeKey: s.typeKey
      }))
    };
  }

  const outputPath = path.join(__dirname, 'spell_ids_report.json');
  fs.writeFileSync(outputPath, JSON.stringify(jsonOutput, null, 2));
  console.log(`\nJSON report written to: ${outputPath}`);
}

main();
