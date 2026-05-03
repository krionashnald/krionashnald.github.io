#!/usr/bin/env node
// trace_to_baselines.js
//
// Convert one or more Install Trace JSON files (from Infinity Mod Runner's
// "Save Trace" flow) into updates on the per-mod `data/mods/*.json` files.
// Each component gets:
//   installProfile.baselineSec     — P50 seconds across the samples
//   installProfile.sampleCount     — total samples contributing
//   installProfile.heavyClass      — light|medium|heavy (preserved if
//                                    already set; computed from baselineSec
//                                    when first set)
//   installProfile.updatedAt       — today's date (ISO)
//
// Traces with non-default accelerator state are NORMALIZED back to the
// reference rig using coefficients from `data/accelerator-profile-ref.json`:
//   ref_equivalent_sec = trace_sec / discount_coeff(accelerators, heavyClass)
// This lets us pool samples from users running override_fast_drive etc.
// without their runs polluting the "no accelerators" baseline.
//
// Usage:
//   node scripts/trace_to_baselines.js <trace.json> [trace2.json ...]
//   node scripts/trace_to_baselines.js --dir traces/ [--dry]
//
// Exit code 0 on success. Non-zero if no traces parseable or no mods touched.

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const MODS_DIR = path.join(ROOT, "data", "mods");
const ACCEL_PATH = path.join(ROOT, "data", "accelerator-profile-ref.json");

// ─── CLI parsing ───

const args = process.argv.slice(2);
const DRY = args.includes("--dry");
const traceFiles = [];
let mode = "files";
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === "--dry") continue;
  if (a === "--dir") {
    mode = "dir";
    const dir = args[++i];
    if (!dir) die("--dir requires a path");
    for (const f of fs.readdirSync(dir)) {
      if (f.endsWith(".json")) traceFiles.push(path.join(dir, f));
    }
  } else if (mode === "files") {
    traceFiles.push(a);
  }
}
if (traceFiles.length === 0) die("No trace files provided. Usage: trace_to_baselines.js <trace.json> [...]");

// ─── Helpers ───

function die(msg) {
  console.error(`error: ${msg}`);
  process.exit(2);
}

function loadAccelerators() {
  try {
    const raw = JSON.parse(fs.readFileSync(ACCEL_PATH, "utf8"));
    return raw.coefficients || {};
  } catch (e) {
    console.warn(`warn: couldn't load accelerator-profile-ref.json (${e.message}); using 1.0 for all discounts`);
    return null;
  }
}

function discountFor(cls, accel, coeffs) {
  if (!coeffs) return 1.0;
  let d = 1.0;
  const fd = coeffs.overrideFastDrive;
  if (accel.overrideFastDrive && fd && typeof fd[cls] === "number") d *= fd[cls];
  const ew = coeffs.experimentalWeidu;
  if (accel.experimentalWeidu && ew && typeof ew[cls] === "number") d *= ew[cls];
  const bp = coeffs.batchSizePenaltyPerStepBelow25;
  if (cls === "light" && typeof bp === "number" && accel.batchSize < 25) {
    d *= 1 + (25 - accel.batchSize) * bp;
  }
  return d;
}

function classify(sec) {
  if (sec <= 10) return "light";
  if (sec <= 120) return "medium";
  return "heavy";
}

function median(sorted) {
  if (sorted.length === 0) return 0;
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) return (sorted[mid - 1] + sorted[mid]) / 2;
  return sorted[mid];
}

// ─── Load traces ───

const samplesByKey = new Map(); // "modTp2:cn" → [normalizedSec, ...]
const acceleratorCoeffs = loadAccelerators();
let traceCount = 0;
let entryCount = 0;

for (const file of traceFiles) {
  let trace;
  try {
    trace = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    console.warn(`warn: couldn't parse ${file}: ${e.message}`);
    continue;
  }
  if (trace.schema !== 1 || trace.event !== "install_trace") {
    console.warn(`warn: ${file} is not a schema-1 install_trace; skipping`);
    continue;
  }
  const accel = trace.accelerators || { overrideFastDrive: false, experimentalWeidu: false, batchSize: 25 };
  for (const e of trace.entries || []) {
    if (typeof e.sec !== "number" || e.sec <= 0) continue;
    // Normalize: trace_sec is on user's rig WITH their accelerators.
    // To get the reference-rig-without-accelerators equivalent, divide by
    // the discount coefficient — a rig that ran fast-drive on heavy
    // components produces a trace value that's ALREADY discounted, so we
    // divide to recover the un-accelerated baseline.
    const cls = classify(e.sec);
    const discount = discountFor(cls, accel, acceleratorCoeffs);
    const normalized = e.sec / Math.max(0.05, discount);
    const key = `${(e.mod || "").toLowerCase()}:${e.cn}`;
    if (!samplesByKey.has(key)) samplesByKey.set(key, []);
    samplesByKey.get(key).push(normalized);
    entryCount++;
  }
  traceCount++;
}

if (traceCount === 0) die("No parseable traces.");
console.log(`Parsed ${traceCount} traces, ${entryCount} component samples, ${samplesByKey.size} distinct (mod, cn) pairs.`);

// ─── Apply to mod JSONs ───

// Build an index: tp2 name → filename (so we can look up which JSON to patch)
const catalogPath = path.join(MODS_DIR, "_catalog.json");
let catalog = {};
try {
  catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
} catch (e) {
  console.warn(`warn: no _catalog.json; will scan ${MODS_DIR} directly`);
}

// Also build tp2→filename from the index (some flows use modId indirection)
const nameToFile = new Map();
try {
  const idx = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "mods-index.json"), "utf8"));
  const list = Array.isArray(idx) ? idx : Object.values(idx);
  for (const entry of list) {
    const tp2 = (entry.t || "").toLowerCase();
    const modId = String(entry.i || "");
    const filename = catalog[modId];
    if (tp2 && filename) nameToFile.set(tp2, filename);
  }
} catch (e) {
  console.warn(`warn: couldn't load mods-index.json: ${e.message}`);
}

// Group samples by mod
const samplesByMod = new Map(); // modTp2 → Map<cn, [normalizedSec]>
for (const [key, samples] of samplesByKey) {
  const [mod, cnStr] = key.split(":");
  const cn = parseInt(cnStr, 10);
  if (!samplesByMod.has(mod)) samplesByMod.set(mod, new Map());
  samplesByMod.get(mod).set(cn, samples);
}

const today = new Date().toISOString().slice(0, 10);
let modsTouched = 0;
let componentsUpdated = 0;

for (const [mod, modSamples] of samplesByMod) {
  const filename = nameToFile.get(mod);
  if (!filename) {
    console.warn(`warn: no mod JSON for tp2 '${mod}' — skipping ${modSamples.size} samples`);
    continue;
  }
  const modPath = path.join(MODS_DIR, filename);
  let data;
  try {
    data = JSON.parse(fs.readFileSync(modPath, "utf8"));
  } catch (e) {
    console.warn(`warn: couldn't parse ${filename}: ${e.message}`);
    continue;
  }
  if (!Array.isArray(data.co)) {
    console.warn(`warn: ${filename} has no co[] array; skipping`);
    continue;
  }

  let touched = false;
  for (const comp of data.co) {
    if (!comp || comp.cn === undefined) continue;
    const samples = modSamples.get(comp.cn);
    if (!samples || samples.length === 0) continue;

    const existing = comp.installProfile || {};
    const existingCount = existing.sampleCount || 0;
    // Simple append — P50 of new samples, weighted against existing by count.
    // A more rigorous approach would keep a histogram, but P50 of a pool is
    // close enough for ETA purposes and keeps the JSON compact.
    const sorted = [...samples].sort((a, b) => a - b);
    const newP50 = median(sorted);
    const totalCount = existingCount + samples.length;
    // Weighted blend: pull existing baseline toward newP50 proportionally
    // to how many samples we're adding. When existingCount == 0, the new
    // P50 wins outright.
    const blended = existingCount > 0 && existing.baselineSec
      ? (existing.baselineSec * existingCount + newP50 * samples.length) / totalCount
      : newP50;

    const cls = existing.heavyClass || classify(blended);
    comp.installProfile = {
      baselineSec: Math.round(blended * 10) / 10,
      heavyClass: cls,
      sampleCount: totalCount,
      updatedAt: today,
      ...(existing.notes ? { notes: existing.notes } : {}),
    };
    touched = true;
    componentsUpdated++;
  }

  if (touched) {
    modsTouched++;
    if (!DRY) {
      fs.writeFileSync(modPath, JSON.stringify(data, null, 2) + "\n");
    }
  }
}

console.log(
  `${DRY ? "[dry] " : ""}Updated installProfile on ${componentsUpdated} components across ${modsTouched} mod files.`,
);

if (modsTouched === 0) process.exit(1);
