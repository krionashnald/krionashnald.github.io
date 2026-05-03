#!/usr/bin/env node
// apply_trace_aggregate.js
//
// Consume `data/install-traces-aggregate.json` from the infinity-mod-telemetry
// repo and patch per-mod `installProfile` fields in data/mods/*.json.
//
// Unlike `trace_to_baselines.js` (which processes individual raw traces),
// this script consumes the already-aggregated output from the telemetry
// repo's weekly workflow — each entry is a P50 of pooled samples with a
// confidence gate already applied upstream.
//
// Usage:
//   # local (pointing at a cloned telemetry repo)
//   node scripts/apply_trace_aggregate.js ../infinity-mod-telemetry/data/install-traces-aggregate.json
//
//   # fetched from the live deploy
//   node scripts/apply_trace_aggregate.js --url \
//     https://anprionsa.github.io/infinity-mod-telemetry/data/install-traces-aggregate.json
//
//   # --dry prints the diff without writing files
//
// Intended to be run by a maintainer before committing Forge data updates.
// Could also run as a GitHub Action in infinity-mod-forge that PRs itself weekly.

const fs = require("fs");
const path = require("path");
const https = require("https");
const http = require("http");

const ROOT = path.resolve(__dirname, "..");
const MODS_DIR = path.join(ROOT, "data", "mods");

const args = process.argv.slice(2);
const DRY = args.includes("--dry");
let source = null;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--dry") continue;
  if (args[i] === "--url") { source = { kind: "url", value: args[++i] }; continue; }
  if (!source) source = { kind: "file", value: args[i] };
}
if (!source) {
  console.error("Usage: apply_trace_aggregate.js <file> | --url <url> [--dry]");
  process.exit(2);
}

// ─── Load aggregate ───

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith("https:") ? https : http;
    client
      .get(url, (resp) => {
        if (resp.statusCode && resp.statusCode >= 400) {
          return reject(new Error(`HTTP ${resp.statusCode}`));
        }
        let body = "";
        resp.setEncoding("utf8");
        resp.on("data", (c) => (body += c));
        resp.on("end", () => {
          try { resolve(JSON.parse(body)); } catch (e) { reject(e); }
        });
      })
      .on("error", reject);
  });
}

async function loadAggregate() {
  if (source.kind === "url") {
    return fetchJson(source.value);
  }
  return JSON.parse(fs.readFileSync(source.value, "utf8"));
}

// ─── Apply to mod JSONs ───

async function main() {
  const agg = await loadAggregate();
  if (agg.schema !== 1 || !agg.entries) {
    console.error("error: aggregate file is not schema 1 or is missing entries");
    process.exit(2);
  }
  const entries = agg.entries;
  console.log(`Loaded aggregate: ${Object.keys(entries).length} entries (publishedAt ${agg.updatedAt || "?"})`);

  // Build tp2 → filename map from the catalog
  const catalogPath = path.join(MODS_DIR, "_catalog.json");
  let catalog = {};
  try {
    catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
  } catch (e) {
    console.warn(`warn: couldn't load _catalog.json: ${e.message}`);
  }
  const nameToFile = new Map();
  try {
    const idx = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "mods-index.json"), "utf8"));
    const list = Array.isArray(idx) ? idx : Object.values(idx);
    for (const m of list) {
      const tp2 = (m.t || "").toLowerCase();
      const id = String(m.i || "");
      if (tp2 && catalog[id]) nameToFile.set(tp2, catalog[id]);
    }
  } catch (e) {
    console.warn(`warn: couldn't load mods-index.json: ${e.message}`);
  }

  // Group aggregate entries by mod tp2
  const byMod = new Map(); // modTp2 → Map<cn, aggregateEntry>
  for (const [key, entry] of Object.entries(entries)) {
    const idx = key.indexOf(":");
    if (idx < 0) continue;
    const mod = key.substring(0, idx);
    const cn = parseInt(key.substring(idx + 1), 10);
    if (!Number.isFinite(cn)) continue;
    if (!byMod.has(mod)) byMod.set(mod, new Map());
    byMod.get(mod).set(cn, entry);
  }

  let modsTouched = 0;
  let componentsUpdated = 0;
  let componentsUnchanged = 0;

  for (const [mod, modEntries] of byMod) {
    const filename = nameToFile.get(mod);
    if (!filename) {
      console.warn(`warn: no mod JSON for tp2 '${mod}' (${modEntries.size} entries)`);
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
    if (!Array.isArray(data.co)) continue;

    let touched = false;
    for (const comp of data.co) {
      if (!comp || comp.cn === undefined) continue;
      const agg = modEntries.get(comp.cn);
      if (!agg) continue;

      const before = comp.installProfile || {};
      // Only overwrite if the aggregate has STRICTLY MORE samples than what
      // we already have. Prevents a stale aggregate from regressing data
      // that was manually curated (sampleCount=999 hand-seeded for sketchy
      // components, for instance).
      if ((before.sampleCount || 0) >= (agg.sampleCount || 0)) {
        componentsUnchanged++;
        continue;
      }
      comp.installProfile = {
        baselineSec: agg.baselineSec,
        heavyClass: agg.heavyClass,
        sampleCount: agg.sampleCount,
        updatedAt: agg.updatedAt,
        ...(before.notes ? { notes: before.notes } : {}),
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
    `${DRY ? "[dry] " : ""}Applied: ${componentsUpdated} components updated across ${modsTouched} mods. ` +
    `(${componentsUnchanged} left unchanged — existing data has equal or more samples.)`,
  );
}

main().catch((e) => {
  console.error(`error: ${e.message}`);
  process.exit(2);
});
