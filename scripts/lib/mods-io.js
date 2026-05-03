/**
 * mods-io.js — Read/write layer for split mod database
 *
 * Detail files (data/mods/*.json) are the single source of truth.
 * mods-index.json is a derived build artifact for fast browser loading.
 *
 * Usage in tools:
 *   const { readMods, writeMods, readMod, writeMod } = require('./lib/mods-io');
 *   const mods = readMods();           // Returns full array like old mods.json
 *   writeMods(mods);                   // Writes back to detail files + rebuilds index
 *   const mod = readMod(12);           // Read single mod by ID
 *   writeMod(mod);                     // Write single mod back
 */

const fs = require('fs');
const path = require('path');

const DATA = path.join(__dirname, '..', '..', 'data');
const MODS_DIR = path.join(DATA, 'mods');
const INDEX_PATH = path.join(DATA, 'mods-index.json');
const CATALOG_PATH = path.join(MODS_DIR, '_catalog.json');
const PRESETS_PATH = path.join(DATA, 'presets.json');

function djb2(str) {
  let h = 5381;
  for (let i = 0; i < str.length; i++) h = ((h << 5) + h + str.charCodeAt(i)) >>> 0;
  return h.toString(36).slice(0, 8);
}

// Scalar fields included in the index (copied from detail files)
const INDEX_FIELDS = ['i', 't', 'n', 'c', 'cats', 's', 'u', 'a', 'v', 'sum', 'tags', 'ph', 'ab', 'ov', 'pl', 'ios', 'sg', 'ord', 'lang', 'langs', 'pfx', 'gh'];
// Computed index fields derived from co[] (not stored in detail files)
const COMPUTED_FIELDS = ['cc', 'coNames', 'coG', 'coX', 'coTG', 'coWC', 'coWF', 'coK', 'coSP', 'coSS', 'coSpLv', 'coKC', 'coIT', 'coITC', 'coGames', 'games', 'coScn', 'coGrn'];

// Compute mod-level games union from component games arrays.
// Semantics: if any component has `games` omitted (universal), the mod-level
// union is also omitted (mod as a whole is universal). Otherwise, mod.games
// is the set-union of all component games arrays, sorted.
function computeModGamesUnion(co) {
  if (!co || co.length === 0) return null;
  const union = new Set();
  for (const c of co) {
    if (!c.games) return null;  // any universal component -> mod is universal
    for (const g of c.games) union.add(g);
  }
  return union.size ? [...union].sort() : null;
}

// Compute mod-level cats array: unique set of (mod.c + all co[].cat overrides).
// Only returns an array when the mod spans multiple categories (via per-component
// cat overrides). Returns null for single-category mods so the UI can check
// `mod.cats && mod.cats.length > 1` as the multi-cat signal.
function computeModCats(mod) {
  if (!mod.co || mod.co.length === 0) return null;
  const cats = new Set();
  if (mod.c) cats.add(mod.c);
  for (const c of mod.co) if (c.cat) cats.add(c.cat);
  if (cats.size <= 1) return null;
  // Preserve mod.c as first element, then others
  const rest = [...cats].filter(x => x !== mod.c).sort();
  return [mod.c, ...rest];
}
// Fields that should NOT be written to detail files (index-only computed fields)
const DETAIL_EXCLUDE = new Set(COMPUTED_FIELDS);

/**
 * Read all mods — returns array identical to old mods.json format.
 * Merges index + detail files into full mod objects.
 */
function readMods() {
  const index = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf8'));
  const catalog = JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf8'));

  const indexIds = new Set(index.map(e => String(e.i)));

  const result = index.map(entry => {
    const filename = catalog[entry.i];
    if (!filename) return stripComputed(entry);

    const fp = path.join(MODS_DIR, filename);
    if (!fs.existsSync(fp)) return stripComputed(entry);

    const detail = JSON.parse(fs.readFileSync(fp, 'utf8'));
    // Detail file is the source of truth — start with it, fill gaps from index
    const mod = {};
    Object.keys(detail).forEach(k => {
      if (k === 'co') return;
      mod[k] = detail[k];
    });
    // Fill any index fields not in detail (shouldn't happen after migration)
    Object.keys(entry).forEach(k => {
      if (!DETAIL_EXCLUDE.has(k) && mod[k] === undefined) mod[k] = entry[k];
    });
    mod.co = detail.co || [];
    return mod;
  });

  // Add new mods from catalog that aren't in the index yet
  Object.keys(catalog).forEach(id => {
    if (indexIds.has(id)) return;
    const fp = path.join(MODS_DIR, catalog[id]);
    if (!fs.existsSync(fp)) return;
    const detail = JSON.parse(fs.readFileSync(fp, 'utf8'));
    result.push(detail);
  });

  return result;
}

/**
 * Read a single mod by ID — returns full mod object.
 */
function readMod(modId) {
  const index = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf8'));
  const catalog = JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf8'));
  const entry = index.find(e => e.i === modId);
  if (!entry) return null;

  const filename = catalog[modId];
  if (!filename) return stripComputed(entry);

  const fp = path.join(MODS_DIR, filename);
  if (!fs.existsSync(fp)) return stripComputed(entry);

  const detail = JSON.parse(fs.readFileSync(fp, 'utf8'));
  const mod = {};
  Object.keys(detail).forEach(k => { if (k !== 'co') mod[k] = detail[k]; });
  Object.keys(entry).forEach(k => { if (!DETAIL_EXCLUDE.has(k) && mod[k] === undefined) mod[k] = entry[k]; });
  mod.co = detail.co || [];
  return mod;
}

/**
 * Write all mods — updates both index and per-mod detail files.
 * Accepts array in old mods.json format.
 */
function writeMods(mods) {
  const catalog = JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf8'));
  const index = [];

  mods.forEach(mod => {
    // Build index entry
    const entry = {};
    INDEX_FIELDS.forEach(f => { if (mod[f] !== undefined) entry[f] = mod[f]; });
    entry.cc = mod.co ? mod.co.length : 0;
    entry.coNames = mod.co ? mod.co.map(c => c.n || '') : [];

    const coG = mod.co ? mod.co.map(c => c.g || null) : [];
    const coX = mod.co ? mod.co.map(c => c.x != null ? c.x : null) : [];
    const coTG = mod.co ? mod.co.map(c => c.tg || null) : [];
    const coWC = mod.co ? mod.co.map(c => c.wc != null ? c.wc : (c.cn != null ? c.cn : null)) : [];
    const coWF = mod.co ? mod.co.map(c => c.wf || null) : [];
    const coK = mod.co ? mod.co.map(c => c.k || 0) : [];
    const coSP = mod.co ? mod.co.map(c => c.sp || 0) : [];
    const coSS = mod.co ? mod.co.map(c => c.ss || 0) : [];
    const coSpLv = mod.co ? mod.co.map(c => c.spLv || null) : [];
    const coKC = mod.co ? mod.co.map(c => c.kC || null) : [];
    if (coG.some(v => v !== null)) entry.coG = coG;
    if (coX.some(v => v !== null)) entry.coX = coX;
    if (coTG.some(v => v !== null)) entry.coTG = coTG;
    if (coWC.some(v => v !== null)) entry.coWC = coWC;
    if (coWF.some(v => v !== null)) entry.coWF = coWF;
    if (coK.some(v => v > 0)) entry.coK = coK;
    if (coSP.some(v => v > 0)) entry.coSP = coSP;
    if (coSS.some(v => v > 0)) entry.coSS = coSS;
    if (coSpLv.some(v => v !== null)) entry.coSpLv = coSpLv;
    if (coKC.some(v => v !== null)) entry.coKC = coKC;
    if (mod.ss && !coSS.some(v => v > 0)) entry.ss = mod.ss;

    // Games: per-component array + mod-level union
    const coGames = mod.co ? mod.co.map(c => c.games || null) : [];
    if (coGames.some(v => v !== null)) entry.coGames = coGames;
    const modGames = computeModGamesUnion(mod.co);
    if (modGames) entry.games = modGames;

    // Subcomponent + Group headers: per-component parallel arrays
    const coScn = mod.co ? mod.co.map(c => c.scn || null) : [];
    const coGrn = mod.co ? mod.co.map(c => c.grn || null) : [];
    if (coScn.some(v => v !== null)) entry.coScn = coScn;
    if (coGrn.some(v => v !== null)) entry.coGrn = coGrn;

    // Cats: auto-compute mod-level cats from component cat overrides.
    // Overrides anything manually set in mod.cats — computed is authoritative.
    const computedCats = computeModCats(mod);
    if (computedCats) entry.cats = computedCats;
    else delete entry.cats;

    index.push(entry);

    // Write detail file — all fields except computed index arrays
    const filename = catalog[mod.i];
    if (filename) {
      const detail = { i: mod.i, t: mod.t };
      Object.keys(mod).forEach(k => {
        if (k === 'co') return;
        if (!DETAIL_EXCLUDE.has(k) && mod[k] !== undefined) detail[k] = mod[k];
      });
      detail.co = mod.co || [];
      fs.writeFileSync(path.join(MODS_DIR, filename), JSON.stringify(detail, null, 2));
    }
  });

  fs.writeFileSync(INDEX_PATH, JSON.stringify(index, null, 2));

  // Update preset hashes.
  //
  // Keys are stable across this pass — this function only writes mod data
  // and recomputes each preset's DJB2 hash so the Forge can detect stale
  // presets on load. Presets migrated to schemaVersion >= 2 store wc-based
  // keys (WeiDU component numbers); legacy presets store idx-based keys.
  // The hash is computed on whatever keys the preset file holds, so the
  // format-invariance of v2 keys (stable across coWC shifts) translates
  // directly into hash stability when mods update.
  if (fs.existsSync(PRESETS_PATH)) {
    const presets = JSON.parse(fs.readFileSync(PRESETS_PATH, 'utf8'));
    let changed = false;
    presets.forEach(p => {
      if (p.keys) {
        const h = djb2([...p.keys].sort().join(','));
        if (p.hash !== h) { p.hash = h; changed = true; }
      }
    });
    if (changed) fs.writeFileSync(PRESETS_PATH, JSON.stringify(presets, null, 2) + '\n');
  }
}

/**
 * Write a single mod — updates its index entry and detail file.
 */
function writeMod(mod) {
  const index = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf8'));
  const catalog = JSON.parse(fs.readFileSync(CATALOG_PATH, 'utf8'));

  // Update index entry
  const idx = index.findIndex(e => e.i === mod.i);
  if (idx === -1) return;

  const entry = {};
  INDEX_FIELDS.forEach(f => { if (mod[f] !== undefined) entry[f] = mod[f]; });
  entry.cc = mod.co ? mod.co.length : 0;
  entry.coNames = mod.co ? mod.co.map(c => c.n || '') : [];
  const coG = mod.co ? mod.co.map(c => c.g || null) : [];
  const coX = mod.co ? mod.co.map(c => c.x != null ? c.x : null) : [];
  const coTG = mod.co ? mod.co.map(c => c.tg || null) : [];
  const coWC = mod.co ? mod.co.map(c => c.wc != null ? c.wc : (c.cn != null ? c.cn : null)) : [];
  const coWF = mod.co ? mod.co.map(c => c.wf || null) : [];
  const coK = mod.co ? mod.co.map(c => c.k || 0) : [];
  const coSP = mod.co ? mod.co.map(c => c.sp || 0) : [];
  const coSS = mod.co ? mod.co.map(c => c.ss || 0) : [];
  if (coG.some(v => v !== null)) entry.coG = coG;
  if (coX.some(v => v !== null)) entry.coX = coX;
  if (coTG.some(v => v !== null)) entry.coTG = coTG;
  if (coWC.some(v => v !== null)) entry.coWC = coWC;
  if (coWF.some(v => v !== null)) entry.coWF = coWF;
  // Games: per-component + mod-level union (writeMod variant)
  const coGames2 = mod.co ? mod.co.map(c => c.games || null) : [];
  if (coGames2.some(v => v !== null)) entry.coGames = coGames2;
  const modGames2 = computeModGamesUnion(mod.co);
  if (modGames2) entry.games = modGames2;
  // Subcomponent + Group headers (writeMod variant)
  const coScn2 = mod.co ? mod.co.map(c => c.scn || null) : [];
  const coGrn2 = mod.co ? mod.co.map(c => c.grn || null) : [];
  if (coScn2.some(v => v !== null)) entry.coScn = coScn2;
  if (coGrn2.some(v => v !== null)) entry.coGrn = coGrn2;
  // Cats: auto-compute (writeMod variant)
  const computedCats2 = computeModCats(mod);
  if (computedCats2) entry.cats = computedCats2;
  else delete entry.cats;
  const coSpLv2 = mod.co ? mod.co.map(c => c.spLv || null) : [];
  const coKC2 = mod.co ? mod.co.map(c => c.kC || null) : [];
  if (coK.some(v => v > 0)) entry.coK = coK;
  if (coSP.some(v => v > 0)) entry.coSP = coSP;
  if (coSS.some(v => v > 0)) entry.coSS = coSS;
  if (coSpLv2.some(v => v !== null)) entry.coSpLv = coSpLv2;
  if (coKC2.some(v => v !== null)) entry.coKC = coKC2;
  if (mod.ss && !coSS.some(v => v > 0)) entry.ss = mod.ss;

  index[idx] = entry;
  fs.writeFileSync(INDEX_PATH, JSON.stringify(index, null, 2));

  // Write detail file — all fields except computed index arrays
  const filename = catalog[mod.i];
  if (filename) {
    const detail = { i: mod.i, t: mod.t };
    Object.keys(mod).forEach(k => {
      if (k === 'co') return;
      if (!DETAIL_EXCLUDE.has(k) && mod[k] !== undefined) detail[k] = mod[k];
    });
    detail.co = mod.co || [];
    fs.writeFileSync(path.join(MODS_DIR, filename), JSON.stringify(detail, null, 2));
  }
}

function stripComputed(entry) {
  const mod = {};
  Object.keys(entry).forEach(k => { if (!COMPUTED_FIELDS.includes(k)) mod[k] = entry[k]; });
  mod.co = [];
  return mod;
}

module.exports = { readMods, writeMods, readMod, writeMod, DATA, MODS_DIR, INDEX_PATH, CATALOG_PATH };
