#!/usr/bin/env node
/**
 * populate_items.js — Scaffold item data into mod detail files.
 *
 * Uses item_scan_report.json + component analysis to set:
 *   - Component-level: it (item count), itC (per-type breakdown)
 *   - Mod-level: items field with new/scope entries
 *
 * For mods not in the scan report (not extracted), infers counts from
 * component names where possible.
 *
 * Usage: node scripts/populate_items.js [--write]
 */

const fs = require('fs');
const path = require('path');
const { readMods, writeMod } = require('./lib/mods-io');

const REPORT_PATH = path.join(__dirname, '..', 'data', 'item_scan_report.json');

// ── Infer item count from component name ────────────────────────────────────
// Many item mods name components like "Standard Install", "New Items", etc.
// For single-component mods, the scan report count is authoritative.
// For multi-component mods, we distribute or infer.

function inferCountFromName(name) {
  const lower = (name || '').toLowerCase();
  // Skip non-item components
  if (/\b(audio|sound|portrait|music|bam|icon|tweak|fix|patch|compat|graphic)\b/i.test(lower)) return 0;
  // "X items" pattern
  const numMatch = lower.match(/(\d+)\s*(?:new\s+)?items?/);
  if (numMatch) return parseInt(numMatch[1]);
  return null; // unknown
}

// ── Infer item type from component name ─────────────────────────────────────
const COMP_NAME_TYPES = [
  [/sword|blade|scimitar|katana|falchion/i, 'large sword'],
  [/dagger|knife|stiletto/i, 'dagger'],
  [/axe/i, 'axe'],
  [/mace|club/i, 'mace'],
  [/hammer|maul/i, 'hammer'],
  [/flail|morning\s*star/i, 'flail'],
  [/staff|stave/i, 'staff'],
  [/spear|pike|trident|javelin/i, 'spear'],
  [/halberd|polearm|bardiche/i, 'halberd'],
  [/bow(?!l)/i, 'bow'],
  [/crossbow|xbow/i, 'crossbow'],
  [/sling/i, 'sling'],
  [/dart/i, 'dart'],
  [/arrow/i, 'arrow'],
  [/bolt/i, 'bolt'],
  [/armor|armour|plate|chain|leather|mail|studded/i, 'armor'],
  [/shield|buckler/i, 'shield'],
  [/helm|hat|circlet|crown/i, 'helmet'],
  [/bracer|gauntlet|glove/i, 'bracers'],
  [/boot|shoe|sandal|slipper/i, 'boots'],
  [/belt|girdle|sash/i, 'belt'],
  [/cloak|cape|mantle/i, 'cloak'],
  [/robe|vest/i, 'robe'],
  [/ring|band/i, 'ring'],
  [/amulet|necklace|pendant|periapt|talisman/i, 'amulet'],
  [/wand|rod/i, 'wand'],
  [/potion|elixir|oil|salve/i, 'potion'],
  [/scroll/i, 'scroll'],
  [/gem|jewel|stone/i, 'gem'],
];

function inferTypeFromCompName(name) {
  for (const [rx, type] of COMP_NAME_TYPES) {
    if (rx.test(name)) return type;
  }
  return null;
}

// ── Main ────────────────────────────────────────────────────────────────────
function main() {
  const writeMode = process.argv.includes('--write');

  let report = {};
  if (fs.existsSync(REPORT_PATH)) {
    report = JSON.parse(fs.readFileSync(REPORT_PATH, 'utf8'));
  }

  const mods = readMods();
  const itemMods = mods.filter(m => (m.c || '').toUpperCase().includes('ITEM'));

  const resync = process.argv.includes('--resync');

  console.log(`Processing ${itemMods.length} item-category mods...${resync ? ' (resync mode)' : ''}`);

  let updated = 0, skipped = 0;

  for (const mod of itemMods) {
    const scanData = report[mod.t];
    const scanItems = (scanData && scanData.status === 'found') ? scanData.items : [];
    const scanCount = scanItems.length;

    // Skip if mod already has item data populated, UNLESS in resync mode with more items found
    if (mod.items && Object.keys(mod.items).length > 0) {
      const existingNewCount = Object.values(mod.items).reduce((s, e) => s + ((e.new || []).length), 0);
      if (!(resync && scanCount > existingNewCount)) {
        skipped++;
        continue;
      }
      // resync: fall through and rebuild
    }

    const co = mod.co || [];
    let modChanged = false;

    // Strategy depends on component count
    if (co.length === 1) {
      // Single component: assign all scanned items to component 0
      const comp = co[0];
      if (scanCount > 0) {
        comp.it = scanCount;

        // Build type breakdown from scan
        const itC = {};
        scanItems.forEach(it => {
          const type = it.type || 'misc';
          itC[type] = (itC[type] || 0) + 1;
        });
        // If all misc, try inferring from comp name
        if (Object.keys(itC).length === 1 && itC.misc) {
          const inferred = inferTypeFromCompName(comp.n);
          if (inferred) {
            delete itC.misc;
            itC[inferred] = scanCount;
          }
        }
        comp.itC = itC;

        // Create items detail entry
        if (!mod.items) mod.items = {};
        mod.items['0'] = {
          scope: 'additions',
          new: scanItems.map(it => [it.resref, it.type || 'misc', it.name || '', ''])
        };
        modChanged = true;
      }
    } else {
      // Multi-component: try to assign scan items by file/context, or use component names
      // For now, assign scanned items to component 0 (main) and set counts from names for others
      if (!mod.items) mod.items = {};

      for (let ci = 0; ci < co.length; ci++) {
        const comp = co[ci];
        const nameCount = inferCountFromName(comp.n);
        const nameType = inferTypeFromCompName(comp.n);

        // For multi-component, if we have scan data and it's comp 0, use scan count
        if (ci === 0 && scanCount > 0 && (!comp.it || resync)) {
          comp.it = scanCount;
          const itC = {};
          scanItems.forEach(it => { itC[it.type || 'misc'] = (itC[it.type || 'misc'] || 0) + 1; });
          if (Object.keys(itC).length === 1 && itC.misc && nameType) {
            delete itC.misc;
            itC[nameType] = scanCount;
          }
          comp.itC = itC;
          mod.items['' + ci] = {
            scope: 'additions',
            new: scanItems.map(it => [it.resref, it.type || 'misc', it.name || '', ''])
          };
          modChanged = true;
        } else if (nameCount != null && nameCount > 0 && !comp.it) {
          comp.it = nameCount;
          if (nameType) {
            comp.itC = { [nameType]: nameCount };
          }
          modChanged = true;
        }
      }
    }

    // For not-extracted mods: set a minimum count of 1 for the main component
    // if no scan data exists but the mod is clearly an item mod
    if (!modChanged && co.length > 0 && !co[0].it) {
      const comp = co[0];
      const nameType = inferTypeFromCompName(comp.n || mod.n);
      // Don't set count — leave for manual population
      // Just mark that we checked it
    }

    if (modChanged) {
      if (writeMode) writeMod(mod);
      updated++;
    }
  }

  console.log(`\nResults:`);
  console.log(`  Updated: ${updated} mods`);
  console.log(`  Skipped (already have data): ${skipped}`);
  console.log(`  Unchanged: ${itemMods.length - updated - skipped}`);

  if (!writeMode) {
    console.log(`\nDry run. Use --write to update mod files.`);
    // Show sample
    const samples = itemMods.filter(m => (m.co || []).some(c => c.it > 0)).slice(0, 10);
    for (const m of samples) {
      const compsWithItems = m.co.filter(c => c.it > 0);
      console.log(`  ${m.t}: ${compsWithItems.map(c => `${c.n} (it=${c.it})`).join(', ')}`);
    }
  }
}

main();
