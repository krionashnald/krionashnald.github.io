#!/usr/bin/env node
/**
 * scan_item_mods.js — Scan extracted mod tp2/tpa/tph files for item additions.
 *
 * Searches for COPY patterns introducing .itm files and SAY NAME patterns
 * to extract item resrefs and names. Outputs a JSON report.
 *
 * Usage: node scripts/scan_item_mods.js [--write]
 *   Without --write: prints report to stdout
 *   With --write: writes data/item_scan_report.json
 */

const fs = require('fs');
const path = require('path');
const { readMods } = require('./lib/mods-io');

const EXTRACTED = 'F:\\BGMods\\Extracted';
const REPORT_PATH = path.join(__dirname, '..', 'data', 'item_scan_report.json');

// ── Item type inference from resref prefix ──────────────────────────────────
const PREFIX_TYPE_MAP = [
  [/^SW1H/i, 'short sword'],
  [/^SW2H/i, 'large sword'],
  [/^DAGG/i, 'dagger'],
  [/^AXE?/i, 'axe'],
  [/^BLUN/i, 'mace'],
  [/^HAMM/i, 'hammer'],
  [/^FLAI/i, 'flail'],
  [/^STAF/i, 'staff'],
  [/^SPER?/i, 'spear'],
  [/^HALB/i, 'halberd'],
  [/^BOW/i, 'bow'],
  [/^XBOW/i, 'crossbow'],
  [/^SLNG/i, 'sling'],
  [/^DART/i, 'dart'],
  [/^AROW/i, 'arrow'],
  [/^BOLT/i, 'bolt'],
  [/^BULL/i, 'bullet'],
  [/^PLAT/i, 'armor'],
  [/^CHAN/i, 'armor'],
  [/^LEAT/i, 'armor'],
  [/^SHLD/i, 'shield'],
  [/^HELM/i, 'helmet'],
  [/^BRAC/i, 'bracers'],
  [/^BOOT/i, 'boots'],
  [/^BELT/i, 'belt'],
  [/^CLCK/i, 'cloak'],
  [/^RING/i, 'ring'],
  [/^AMUL/i, 'amulet'],
  [/^WAND/i, 'wand'],
  [/^POTN/i, 'potion'],
  [/^SCRL/i, 'scroll'],
  [/^MISC/i, 'misc'],
  [/^ROBE/i, 'robe'],
  [/^GEM/i, 'gem'],
];

function inferType(resref) {
  for (const [rx, type] of PREFIX_TYPE_MAP) {
    if (rx.test(resref)) return type;
  }
  return 'misc';
}

// ── Name inference from resref keywords ─────────────────────────────────────
const NAME_HINTS = {
  'sword': 'large sword', 'blade': 'large sword', 'scimitar': 'large sword',
  'katana': 'large sword', 'dagger': 'dagger', 'axe': 'axe', 'mace': 'mace',
  'hammer': 'hammer', 'flail': 'flail', 'staff': 'staff', 'spear': 'spear',
  'halberd': 'halberd', 'bow': 'bow', 'xbow': 'crossbow', 'sling': 'sling',
  'dart': 'dart', 'arrow': 'arrow', 'bolt': 'bolt', 'armor': 'armor',
  'armour': 'armor', 'plate': 'armor', 'chain': 'armor', 'leather': 'armor',
  'shield': 'shield', 'helm': 'helmet', 'bracer': 'bracers', 'gauntlet': 'bracers',
  'boot': 'boots', 'shoe': 'boots', 'belt': 'belt', 'girdle': 'belt',
  'cloak': 'cloak', 'ring': 'ring', 'amulet': 'amulet', 'necklace': 'amulet',
  'wand': 'wand', 'rod': 'wand', 'potion': 'potion', 'scroll': 'scroll',
  'robe': 'robe',
};

function inferTypeFromName(name) {
  const lower = name.toLowerCase();
  for (const [keyword, type] of Object.entries(NAME_HINTS)) {
    if (lower.includes(keyword)) return type;
  }
  return null;
}

// ── Build tp2 index once for fast lookup ────────────────────────────────────
let _tp2Index = null;
function buildTp2Index() {
  if (_tp2Index) return _tp2Index;
  _tp2Index = {};
  console.log('Building tp2 index from Extracted folder...');
  const dirs = fs.readdirSync(EXTRACTED);
  for (const dir of dirs) {
    const dirPath = path.join(EXTRACTED, dir);
    try { if (!fs.statSync(dirPath).isDirectory()) continue; } catch(e) { continue; }
    // Check 2 levels deep for tp2 files
    const check = (d, depth) => {
      if (depth > 2) return;
      try {
        for (const e of fs.readdirSync(d)) {
          const p = path.join(d, e);
          try {
            if (e.toLowerCase().endsWith('.tp2')) {
              const base = e.toLowerCase().replace('setup-', '').replace('.tp2', '');
              _tp2Index[base] = d;
            } else if (depth < 2 && fs.statSync(p).isDirectory()) {
              check(p, depth + 1);
            }
          } catch(err) { /* skip */ }
        }
      } catch(err) { /* skip */ }
    };
    check(dirPath, 0);
  }
  console.log(`  Indexed ${Object.keys(_tp2Index).length} tp2 files`);
  return _tp2Index;
}

function findExtractedFolder(tp2Id) {
  const index = buildTp2Index();
  return index[tp2Id.toLowerCase()] || null;
}

// ── Collect all .tp2/.tpa/.tph files recursively ────────────────────────────
function collectScriptFiles(dir) {
  const files = [];
  function walk(d) {
    try {
      for (const e of fs.readdirSync(d)) {
        const p = path.join(d, e);
        try {
          const st = fs.statSync(p);
          if (st.isDirectory()) walk(p);
          else if (/\.(tp2|tpa|tph)$/i.test(e)) files.push(p);
        } catch (err) { /* skip */ }
      }
    } catch (err) { /* skip */ }
  }
  walk(dir);
  return files;
}

// ── Scan a single mod's extracted files for items ───────────────────────────
function scanMod(modDir, mod) {
  const scriptFiles = collectScriptFiles(modDir);
  if (scriptFiles.length === 0) return null;

  const items = []; // {resref, name, type, file}
  const seenResrefs = new Set();

  // Substitute WeiDU OUTER_SPRINT variables into a path. varMap is file-local.
  // Unrecognized %VAR% tokens (e.g. MOD_FOLDER) are left as-is — the caller still
  // needs to extract the resref from the tail, so we only care about variables
  // that land inside the resref itself.
  function substVars(str, varMap) {
    return str.replace(/%([A-Za-z_][A-Za-z_0-9]*)%/g, (match, name) => {
      const v = varMap[name.toLowerCase()];
      return v != null ? v : match;
    });
  }

  for (const filePath of scriptFiles) {
    let content;
    try {
      content = fs.readFileSync(filePath, 'utf8');
    } catch (err) { continue; }

    const relFile = path.relative(modDir, filePath);

    // Collect OUTER_SPRINT assignments in this file: OUTER_SPRINT varname ~value~
    // (Also handle OUTER_TEXT_SPRINT variants.) Case-insensitive variable names.
    const varMap = {};
    const sprintRx = /\bOUTER_(?:TEXT_)?SPRINT\s+([A-Za-z_][A-Za-z_0-9]*)\s+~([^~]*)~/gi;
    let sm;
    while ((sm = sprintRx.exec(content)) !== null) {
      varMap[sm[1].toLowerCase()] = sm[2];
    }

    // Pattern 1: COPY ~source.itm~ ~override/RESREF.itm~
    // Also: COPY ~source.itm~ ~override~  (uses source filename as resref)
    const copyRx = /COPY\s+~([^~]*?([^~\/\\]+)\.itm)~\s+~override(?:\/([^~]+\.itm))?~/gi;
    let m;
    while ((m = copyRx.exec(content)) !== null) {
      const srcFile = m[2]; // source filename without extension
      const dstFile = m[3]; // destination filename if specified
      let resref = dstFile ? dstFile.replace(/\.itm$/i, '') : srcFile;

      // Resolve %var% via OUTER_SPRINT map. If anything unresolved remains, skip.
      if (resref.includes('%')) {
        resref = substVars(resref, varMap);
        if (resref.includes('%')) continue;
      }

      resref = resref.toUpperCase();
      if (seenResrefs.has(resref)) continue;
      seenResrefs.add(resref);

      // Try to find the name from nearby SAY NAME2
      let name = '';
      const afterCopy = content.substring(m.index, Math.min(m.index + 2000, content.length));
      const sayMatch = afterCopy.match(/SAY\s+(?:NAME2|0x0c)\s+~([^~]+)~/i);
      if (sayMatch) name = sayMatch[1].trim();

      // Infer type from resref prefix, then from name
      let type = inferType(resref);
      if (type === 'misc' && name) {
        const nameType = inferTypeFromName(name);
        if (nameType) type = nameType;
      }

      items.push({ resref, name, type, file: relFile });
    }

    // Pattern 2: COPY_EXISTING ~RESREF.itm~ ~override~ (modifications, not new items)
    // We track these separately but don't count them as "new"

    // Pattern 3: Variable-based COPY (common in complex mods)
    // COPY ~path/%variable%.itm~ ~override/%variable%.itm~
    // We note these but can't resolve them
  }

  return items.length > 0 ? items : null;
}

// ── Main ────────────────────────────────────────────────────────────────────
function main() {
  const writeMode = process.argv.includes('--write');

  const mods = readMods();
  const itemMods = mods.filter(m => (m.c || '').toUpperCase().includes('ITEM'));

  console.log(`Scanning ${itemMods.length} item-category mods...`);

  const report = {};
  let found = 0, notFound = 0, noItems = 0;

  for (const mod of itemMods) {
    const modDir = findExtractedFolder(mod.t);
    if (!modDir) {
      notFound++;
      report[mod.t] = { id: mod.i, name: mod.n, status: 'not_extracted', items: [] };
      continue;
    }

    const items = scanMod(modDir, mod);
    if (!items) {
      noItems++;
      report[mod.t] = { id: mod.i, name: mod.n, status: 'no_items_found', dir: modDir, items: [] };
      continue;
    }

    found++;
    // Categorize items by type
    const typeCounts = {};
    items.forEach(it => { typeCounts[it.type] = (typeCounts[it.type] || 0) + 1; });

    report[mod.t] = {
      id: mod.i,
      name: mod.n,
      status: 'found',
      dir: modDir,
      itemCount: items.length,
      typeCounts,
      items
    };
  }

  console.log(`\nResults:`);
  console.log(`  Found items: ${found} mods`);
  console.log(`  No items found: ${noItems} mods`);
  console.log(`  Not extracted: ${notFound} mods`);

  // Summary
  let totalItems = 0;
  const allTypes = {};
  for (const [tp2, data] of Object.entries(report)) {
    if (data.status !== 'found') continue;
    totalItems += data.itemCount;
    for (const [type, count] of Object.entries(data.typeCounts || {})) {
      allTypes[type] = (allTypes[type] || 0) + count;
    }
  }
  console.log(`\n  Total items across all mods: ${totalItems}`);
  console.log(`  By type:`);
  for (const [type, count] of Object.entries(allTypes).sort((a, b) => b[1] - a[1])) {
    console.log(`    ${type}: ${count}`);
  }

  // Show top mods
  console.log(`\nTop mods by item count:`);
  Object.entries(report)
    .filter(([, d]) => d.status === 'found')
    .sort((a, b) => b[1].itemCount - a[1].itemCount)
    .slice(0, 15)
    .forEach(([tp2, d]) => {
      console.log(`  ${tp2}: ${d.itemCount} items (${d.name})`);
    });

  // Show mods not found
  const missing = Object.entries(report).filter(([, d]) => d.status === 'not_extracted');
  if (missing.length > 0) {
    console.log(`\nNot extracted (${missing.length}):`);
    missing.forEach(([tp2, d]) => console.log(`  ${tp2}: ${d.name}`));
  }

  if (writeMode) {
    fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2));
    console.log(`\nWrote ${REPORT_PATH}`);
  } else {
    console.log(`\nDry run. Use --write to save report.`);
  }
}

main();
