// validate_mods.js — catches data-integrity bugs in mod JSON files + presets.
//
// Checks:
//   - Duplicate wc within same mod+wf, DISTINGUISHING:
//       * ERROR: true duplicates (same wc, same cn, same n) — dedupe needed
//       * INFO:  SUBCOMPONENT siblings (same wc, different n or different pi) —
//                legitimate WeiDU pattern where an author groups mutually
//                exclusive variants under one component number (e.g.
//                keldorn_rom romance-match alignment options, d2-party-adder
//                party choices, proficiency attribute-bonus variants).
//   - Missing required fields (n, co)
//   - Invalid components (missing n)
//   - wf cross-contamination: all co[].wf values for one mod should
//     refer to THIS mod's tp2. Catches bugs like iwdification's old
//     wf="cdtweaks" on 2 components.
//   - dep + gone mutual exclusion: these flags describe different states
//     per README (dep = still selectable, author-discouraged; gone =
//     removed, kept only for conflict-system validation).
//   - Preset key format correctness: keys are `modId-cn`, NOT
//     `modId-idx`. Validate each key points at an existing cn and
//     doesn't reference a `gone` component.
//   - Schema version (`sv`) present and recognized. See README
//     "Schema versioning" for details on when to bump.
//   - `games` field tokens in whitelist (EE family + classic). See README
//     "Game targets (`games` field)" for the canonical token list.
//
// Exit codes:
//   0 — no errors (warnings are reported but still exit 0)
//   1 — one or more errors found
const fs = require('fs');
const path = require('path');
const { readMods } = require('./lib/mods-io');
const mods = readMods();

let errors = 0;
let warnings = 0;

// -------- Schema version (sv) --------
// Every mod file should carry `sv`. Validator knows about these versions:
const KNOWN_SCHEMA_VERSIONS = new Set([1]);
let missingSv = 0, unknownSv = 0;
mods.forEach(m => {
  if (m.sv === undefined || m.sv === null) {
    console.log('MISSING_SV: i=' + m.i + ' "' + m.n + '" has no sv field');
    missingSv++;
  } else if (!KNOWN_SCHEMA_VERSIONS.has(m.sv)) {
    console.log('UNKNOWN_SV: i=' + m.i + ' "' + m.n + '" sv=' + m.sv + ' (validator knows: ' + [...KNOWN_SCHEMA_VERSIONS].join(',') + ')');
    unknownSv++;
  }
});
if (missingSv) { console.log('Mods missing sv: ' + missingSv); errors += missingSv; }
if (unknownSv) { console.log('Mods with unknown sv: ' + unknownSv); errors += unknownSv; }
if (!missingSv && !unknownSv) console.log('Schema version (sv): all ' + mods.length + ' mods OK');

// -------- Game targets (`games` field) --------
// Token whitelist (must match README "Game targets" + scanner). Hyphens
// in tokens are normalized to underscores by the scanner already, but
// validator accepts both forms defensively.
const GAMES_WHITELIST = new Set([
  'eet', 'bgee', 'bg2ee', 'iwdee', 'pstee', 'sod',
  'bg1', 'bg2', 'soa', 'tob', 'totsc',
  'bgt', 'tutu', 'tutu_totsc',
  'iwd', 'iwd2', 'how', 'totlm',
  'pst', 'ca', 'iwd_in_bg2',
]);
let gamesBadToken = 0, gamesEmpty = 0, gamesShape = 0;
mods.forEach(mod => {
  (mod.co || []).forEach((c, ci) => {
    if (c.games === undefined) return;
    if (!Array.isArray(c.games)) {
      console.log('GAMES_SHAPE: i=' + mod.i + ' "' + mod.n + '" co[' + ci + '] games is not an array');
      gamesShape++;
      return;
    }
    if (c.games.length === 0) {
      console.log('GAMES_EMPTY: i=' + mod.i + ' "' + mod.n + '" co[' + ci + '] cn=' + c.cn + ' has empty games array (data bug)');
      gamesEmpty++;
      return;
    }
    for (const tok of c.games) {
      const norm = String(tok).toLowerCase().replace(/-/g, '_');
      if (!GAMES_WHITELIST.has(norm)) {
        console.log('GAMES_BAD_TOKEN: i=' + mod.i + ' "' + mod.n + '" co[' + ci + '] cn=' + c.cn + ' has unknown games token: ' + JSON.stringify(tok));
        gamesBadToken++;
      }
    }
  });
});
if (gamesBadToken) { console.log('games unknown tokens: ' + gamesBadToken); errors += gamesBadToken; }
if (gamesEmpty)    { console.log('games empty-array bugs: ' + gamesEmpty); errors += gamesEmpty; }
if (gamesShape)    { console.log('games shape errors: ' + gamesShape); errors += gamesShape; }
if (!gamesBadToken && !gamesEmpty && !gamesShape) console.log('Games field: all entries OK');

// -------- Subcomponent / Group headers (scn/grn) --------
// Shape check: both fields must be non-empty strings when present, with
// reasonable length. Empty or whitespace-only means the scanner or a
// manual edit left junk behind.
let scnBad = 0, grnBad = 0;
mods.forEach(mod => {
  (mod.co || []).forEach((c, ci) => {
    if (c.scn !== undefined) {
      if (typeof c.scn !== 'string' || !c.scn.trim() || c.scn.length > 200) {
        console.log('SCN_BAD: i=' + mod.i + ' "' + mod.n + '" co[' + ci + '] cn=' + c.cn + ' scn=' + JSON.stringify(c.scn).slice(0,60));
        scnBad++;
      }
    }
    if (c.grn !== undefined) {
      if (typeof c.grn !== 'string' || !c.grn.trim() || c.grn.length > 200) {
        console.log('GRN_BAD: i=' + mod.i + ' "' + mod.n + '" co[' + ci + '] cn=' + c.cn + ' grn=' + JSON.stringify(c.grn).slice(0,60));
        grnBad++;
      }
    }
  });
});
if (scnBad) { console.log('scn shape errors: ' + scnBad); errors += scnBad; }
if (grnBad) { console.log('grn shape errors: ' + grnBad); errors += grnBad; }
if (!scnBad && !grnBad) console.log('Subcomponent/group headers (scn/grn): all entries OK');

// -------- Duplicate wc within same mod+wf --------
// Classification:
//   - TRUE dupe (ERROR): same wc, same cn, same n (case-insensitive), same pi
//                        → two DB entries for one tp2 component, dedupe.
//   - SUBCOMPONENT sibling (INFO): same wc but differs on cn, n, or pi
//                        → intentional: WeiDU's FORCED_SUBCOMPONENT / SUBCOMPONENT
//                          lets authors group mutually exclusive variants under
//                          one DESIGNATED number. Legitimate, no action needed.
let trueDupes = 0, siblingGroups = 0;
mods.forEach(mod => {
  const byWf = {};
  (mod.co || []).forEach((c, ci) => {
    const wf = (c.wf || '').toLowerCase();
    const wc = parseInt(c.wc) || 0;
    if (wc === 0) return;
    const key = wf + ':' + wc;
    if (byWf[key] !== undefined) {
      const prev = byWf[key];
      const prevC = mod.co[prev.ci];
      const sameCn   = (prevC.cn === c.cn);
      const sameName = ((prevC.n||'').toLowerCase().trim() === (c.n||'').toLowerCase().trim());
      const samePi   = ((prevC.pi||'') === (c.pi||''));
      if (sameCn && sameName && samePi) {
        console.log('DUPE_TRUE: i=' + mod.i + ' "' + mod.n + '" wf=' + wf + ' wc=' + wc + ' at co[' + prev.ci + '] and co[' + ci + ']  n=' + JSON.stringify((c.n||'').slice(0,50)));
        trueDupes++;
      } else if (!prev.reported) {
        console.log('SUBCOMP_SIBLING: i=' + mod.i + ' "' + mod.n + '" wf=' + wf + ' wc=' + wc + ' — multiple entries differ by cn/n/pi (OK, WeiDU SUBCOMPONENT pattern)');
        siblingGroups++;
        prev.reported = true;
      }
    }
    byWf[key] = byWf[key] || { ci };
    if (byWf[key].ci !== ci) byWf[key].ci = ci;  // track latest index
  });
});
if (trueDupes) { console.log('True duplicate wc values: ' + trueDupes); errors += trueDupes; }
if (siblingGroups) console.log('SUBCOMPONENT sibling groups (OK): ' + siblingGroups);
if (!trueDupes) console.log('True duplicate wc values: 0 (OK)');

// -------- wc coverage --------
let total = 0, nonZero = 0, zero = 0;
mods.forEach(m => (m.co || []).forEach(c => {
  total++;
  if ((parseInt(c.wc) || 0) === 0) zero++; else nonZero++;
}));
console.log('\nTotal components: ' + total);
console.log('With real wc: ' + nonZero + ' (' + (nonZero / total * 100).toFixed(1) + '%)');
console.log('Still wc:0: ' + zero + ' (' + (zero / total * 100).toFixed(1) + '%)');

// -------- Missing required fields --------
let invalid = 0;
mods.forEach(m => {
  if (!m.n || !m.co || !Array.isArray(m.co)) {
    console.log('INVALID MOD: i=' + m.i + ' missing n/co');
    invalid++;
  }
  (m.co || []).forEach((c, ci) => {
    if (!c.n) { console.log('INVALID COMP: i=' + m.i + ' co[' + ci + '] missing n'); invalid++; }
  });
});
if (invalid) { console.log('\nInvalid entries: ' + invalid); errors += invalid; }

// -------- dep + gone mutual exclusion --------
let depGoneConflicts = 0;
mods.forEach(m => {
  (m.co || []).forEach(c => {
    if (c.dep && c.gone) {
      console.log('DEP_GONE_CONFLICT: i=' + m.i + ' "' + m.n + '" cn=' + c.cn + ' has BOTH dep and gone');
      depGoneConflicts++;
    }
  });
});
if (depGoneConflicts) { console.log('\nDep+Gone conflicts: ' + depGoneConflicts); errors += depGoneConflicts; }
else { console.log('\nDep+Gone conflicts: 0 (OK)'); }

// -------- wf cross-contamination --------
// Bug pattern (iwdification's case): one mod's co[] had wf="cdtweaks" on a
// SUBSET of components (2 of 18) while the rest had wf="iwdification".
// Those 2 components silently pointed the installer at cdtweaks.tp2 for
// their cn lookups.
//
// Legitimate shared-folder pattern: EET_End (i=449) lives in the same
// `eet/` folder as EET core (i=12). ALL of its components use wf="eet".
// This is fine.
//
// So we only flag MIXED wf: if a single mod's components have multiple
// distinct wf values AND at least one of those values matches another
// mod's `t` field, that's suspicious.
const tByLower = new Map();
mods.forEach(m => { if (m.t) tByLower.set(m.t.toLowerCase(), m.i); });
let wfCrossContam = 0;
mods.forEach(m => {
  const wfs = new Set();
  (m.co || []).forEach(c => { if (c.wf) wfs.add(c.wf.toLowerCase()); });
  if (wfs.size <= 1) return;  // uniform wf is fine even if it matches another mod's t
  // Mixed wfs — check each
  wfs.forEach(wf => {
    const otherModId = tByLower.get(wf);
    if (otherModId !== undefined && otherModId !== m.i) {
      const otherMod = mods.find(x => x.i === otherModId);
      const components = (m.co || []).filter(c => (c.wf || '').toLowerCase() === wf).map(c => c.cn);
      console.log('WF_CROSS_CONTAM: i=' + m.i + ' "' + m.n + '" has MIXED wf; cns ' +
        JSON.stringify(components.slice(0, 5)) + (components.length > 5 ? '...' : '') +
        ' use wf="' + wf + '" (matches mod i=' + otherModId + ' "' + (otherMod ? otherMod.n : '?') + '")');
      wfCrossContam++;
    }
  });
});
if (wfCrossContam) { console.log('\nwf cross-contamination: ' + wfCrossContam); errors += wfCrossContam; }
else { console.log('wf cross-contamination: 0 (OK)'); }

// -------- Preset validation (format: modId-cn, not modId-idx) --------
console.log('\n--- Presets (format: modId-cn) ---');
const presets = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'presets.json'), 'utf8'));
presets.forEach(p => {
  let invalidMod = 0, invalidCn = 0, pointsToGone = 0;
  (p.keys || []).forEach(k => {
    const parts = String(k).split('-');
    const mi = parseInt(parts[0]);
    const cn = parseInt(parts[1]);
    if (isNaN(mi) || isNaN(cn)) return;
    const mod = mods.find(m => m.i === mi);
    if (!mod) { invalidMod++; return; }
    const comp = (mod.co || []).find(c => c.cn === cn);
    if (!comp) { invalidCn++; return; }
    if (comp.gone) pointsToGone++;
  });
  const totalKeys = (p.keys || []).length;
  const bad = invalidMod + invalidCn + pointsToGone;
  const status = bad === 0 ? 'OK' : (pointsToGone > 0 && invalidMod === 0 && invalidCn === 0 ? 'WARN' : 'ERR');
  console.log('Preset "' + p.name + '": ' + totalKeys + ' keys, ' + bad + ' issues  [' + status + ']');
  if (invalidMod > 0) console.log('   invalid_mod_id: ' + invalidMod);
  if (invalidCn > 0) console.log('   cn_not_in_mod: ' + invalidCn);
  if (pointsToGone > 0) console.log('   points_to_gone: ' + pointsToGone + ' (warning; removed components)');
  if (invalidMod || invalidCn) errors += (invalidMod + invalidCn);
  if (pointsToGone) warnings += pointsToGone;
});

console.log('\n=== Summary ===');
console.log('Errors: ' + errors);
console.log('Warnings: ' + warnings);
if (errors > 0) process.exit(1);
process.exit(0);
