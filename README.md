# Infinity Mod Forge

> **Renamed from EET Mod Forge** (v4.0.0). The suite was renamed from "EET" to "Infinity" to reflect support for the broader Infinity Engine game family, not just EET installs. The EET *mod* (EET.tp2) is unrelated to this rename.

**Master install order builder for Baldur's Gate: Enhanced Edition Trilogy** (and, increasingly, the wider Infinity Engine family)

Browse 800+ mods and 7,500+ components. Build a WeiDU.log. Export for [mod_installer](https://github.com/dark0dave/mod_installer) or Project Infinity. Analyze debug logs. Preview NPC portraits. Browse the complete spell, kit, and item catalogs with mod impact tracking. Plan characters with a full interactive character sheet. Check for updates. Scan your mod folder for version mismatches.

URL: https://krion64.github.io/

## Contents

- [Features](#features)
- [Running locally](#running-locally)
- [Architecture](#data-architecture) · [Repo structure](#repo-structure)
- [Contributing](#contributing) — [Mod fields](#mod-level-field-reference) · [Component fields](#component-fields) · [Portraits](#adding-portrait-data) · [Spells](#adding-spell-data) · [Kits](#adding-kit-data) · [Items](#adding-item-data) · [Known issues](#adding-known-issues) · [Proficiencies](#adding-proficiency-data)
- [Data sources](#data-sources) · [Credits](#credits)
- [Changelog](#changelog)

## Features

- **Browse the full Infinity Engine mod catalog** — 800+ mods and 7,500+ components organized by install order across 26 categories, with search, game phase filters (BG1/SoD/SoA/ToB), author filtering, and an install-target picker (EET / BG:EE / BG2:EE / IWD:EE / PST:EE) that narrows the catalog to mods installable on your chosen engine. 400+ mods have detailed component-level notes from tp2 analysis, including resolved WeiDU SUBCOMPONENT and GROUP hierarchy. Install order context, split mod navigation, and multi-category mods are handled automatically.

- **Build a WeiDU.log** — Select components with checkboxes, then export a valid `WeiDU.log` and `WeiDU-BGEE.log` pair for [mod_installer](https://github.com/dark0dave/mod_installer) or Project Infinity. Import an existing WeiDU.log or Project Infinity CSV (`weidu-log.csv`) to recreate a selection, with exact-LABEL matching and a fuzzy-review breakdown for anything not found. Pre-export validation catches components that won't install on your chosen target. Multi-language export with 15 languages.

- **Start from presets or the guided wizard** — Three curated presets plus a 7-step guided build wizard that recommends a starting point based on experience level, content interests, and difficulty preference.

- **Conflict detection** — 1,100+ conflict rules and 120+ dependency rules with real-time alerts. Component-level detail, severity levels, install order notes, and grouped suggestions.

- **Version tracker** — Scans GitHub releases for 250+ mods to find version mismatches. Folder scan feature (Chrome/Edge) compares your local mod directory against known releases.

- **Diagnostics** — Upload a WSETUP.DEBUG file to detect errors and match them against known issues with workarounds. Tracks engine limits in real time: SPLSTATE.IDS (256 cap), Spell IDs per level (50 cap), and Kit Cap (320 cap).

- **NPC Portrait Viewer** — 230+ NPCs across 3 sub-tabs with phase-by-phase portrait tracking and conflict detection. 1,800+ portrait entries from 200+ mods with 800+ player-selectable PC portraits.

- **Spell Catalog** — 300+ vanilla spells with game icons and mod impact tracking. 1,200+ spell entries across 50+ mods with action badges and conflict detection. Rich per-spell metadata (spheres, class eligibility, casting time, range, save type) extracted from SPL files. Priest sphere system supports per-deity spell filtering.

- **Item Catalog** — 2,700+ vanilla items + 2,000+ mod-added items across 7 category tabs, each with inventory icons (3,500+ BAM-extracted PNGs) and type-glyph fallbacks when art is missing. Per-card stat badges (THAC0/damage/AC/speed/2H), special-effect icons (immunities, resistances, charges, abilities), class-restriction indicators, and clickable type-filter pills. Variants with the same name+type collapse into one card with a grouped variants list — enchantment ladders (+1/+2/+3), AC ladders (Bracers of Defense AC 8→3), and cross-source clones (vanilla + mod duplicates tagged TWEAKED). Full detail modal with requirements, abilities, and mod attribution. Hundreds of creature-attack / engine-helper items automatically filed under an Internal sub-tab so the main view stays clean.

- **Character Planner** — BG2-inspired interactive character sheet. Choose race, class/kit, set ability scores, and slide through levels 1–40. Combat stats, 11 equipment slots, spell slots with deity sphere filtering, and interactive proficiency allocation. Fully mod-aware: 650+ mod kits + 27 vanilla kits carry structured ability data for the planner.

- **Community builds & telemetry** — Browse, load, and merge mod builds published by other players via the Community tab. Publish your own from the bottom toolbar. Anonymized install reports from [Infinity Mod Runner](https://github.com/Anprionsa/infinity-mod-runner) feed per-component stability indicators (green/yellow/red). All data is public in the [infinity-mod-telemetry](https://github.com/Anprionsa/infinity-mod-telemetry) repo.

- **Multi-language UI** — App interface in German, French, Polish, and Russian. Mod names and summaries translated via DeepL.

> See the **Resources** tab in the app for install guides, badge reference, troubleshooting FAQ, and the WeiDU prefix registry.

## Running locally

Just serve the directory:

```sh
# Python
python3 -m http.server 8000

# Node
npx serve .

# Then open http://localhost:8000
```

Or push to GitHub and enable Pages — it works as-is.

## Data architecture

### Single source of truth

Per-mod detail files under `data/mods/` are the **single source of truth** for all mod data. Each file (e.g., `stratagems.json`) contains the complete mod record: metadata (name, author, URL, summary, version, tags, game phases), components, conflicts, dependencies, portraits, spells, kits, known issues, recommendations, EET compatibility, and GitHub repo identifiers.

You only ever edit one file. Everything else is derived.

Two derived files support the app at runtime:

- **`data/mods-index.json`** — Lightweight array of every mod with just enough data for the browse list (name, category, author, component count, `ord`, tags, summaries, GitHub repo info, etc.). **Build artifact** — rebuilt automatically by the pre-commit hook or `python scripts/build_index.py --write`. Never edit manually.
- **`data/mods/_catalog.json`** — Maps mod IDs to filenames (e.g., `"12": "EET.json"`). When a user expands a mod card, the app fetches the full per-mod file on demand.

One external cache provides dynamic data:

- **`data/version_cache.json`** — GitHub API scan results (stars, push dates, release tags). Refreshed weekly by CI (`scripts/scan_versions.py`). The app merges this with static `gh` fields from the index at runtime.

### Why per-mod files

- **Single edit workflow** — change one file and everything stays in sync (index rebuilds on commit).
- **Git diffs are readable** — changing one mod touches one file instead of a 3 MB monolith.
- **Lazy loading** — the app only fetches full component data when the user expands a mod card, cutting initial page load.
- **Parallel contribution** — multiple contributors can edit different mods without merge conflicts.

### Conflicts and dependencies

Conflict and dependency rules are stored inside each per-mod file (under `conflicts` and `dependencies` arrays), co-located with the mod they belong to. There are 1,100+ conflict rules across 250+ mods and 120+ dependency rules total. All conflicts are bidirectional — if mod A declares a conflict with mod B, mod B has a matching reciprocal entry.

## Repo structure

```
data/
  mods-index.json      # Derived index (one entry per mod) — rebuilt by pre-commit hook, never edit manually
  mods/                # Per-mod JSON files — the single source of truth
    _catalog.json      # ID → filename mapping for lazy loading
    stratagems.json    # Example: full mod record with metadata, components, conflicts, deps
    cdtweaks.json
    ...
  presets.json         # 3 curated install profiles (First Adventure, Seasoned Adventurer, Veteran's Challenge). Each preset's `keys` array uses format "<modId>-<cn>" where `cn` is the tp2 component number (DESIGNATED value), NOT the co[] array index.
  config.json          # App configuration: version, engine limits, badges, mod type icons, URLs, wizard data
  categories.json      # Install order categories with display names, descriptions, and ordering rationale
  chargen.json         # Character Planner data: races, ability tables, THAC0, saves, HP, spell slots, proficiencies, HLAs, kit abilities
  faq.json             # FAQ content, first-time tips, prefix validation rules
  known_issues.json    # Global cross-mod issue patterns (mod: "*"). Per-mod issues use the ki field in each mod's JSON file
  tools.json           # Community tools catalog (utilities, dev tools, launchers)
  spell-tables.json    # Spell system tables: sphere list, class level caps, scribe INT thresholds, sorcerer/bard pick tables
  prefix-registry.json # WeiDU file prefix registry for the Help tab Prefix Registry browser
  version_cache.json   # GitHub/Weaselmods release data — auto-updated weekly by Actions
  npcs.json            # NPC definitions for portrait viewer (with default images)
  spells-vanilla.json  # Vanilla BG2:EE spell catalog (names, levels, schools, descriptions)
  kits-vanilla.json    # Vanilla BG2:EE kit catalog (names, classes, descriptions)
  classes-vanilla.json # Vanilla BG2:EE base class catalog
  items-vanilla.json   # Vanilla BG2:EE item catalog (names, types, prices, icons, descriptions)
  lang/                # i18n translation files (ui-*.json, mods-*.json, tools-*.json for de/fr/pl/ru)

portraits/               # NPC and PC portrait images (PNG thumbnails)

spells/
  icons/               # Spell icons (48x48 PNG, extracted from BG2:EE BAM files)

items/
  icons/               # Item inventory icons (48x48 PNG, extracted from BG2:EE BAM files + mod sources)

scripts/
  build_index.py       # Rebuild mods-index.json from per-mod files (run via pre-commit hook)
  scan_versions.py     # Scan GitHub repos for release info, update version_cache.json
  scrape_weaselmods.py # Scrape Weaselmods.net for version info, update version_cache.json
  translate.py         # i18n: translate UI strings, mod names, summaries via DeepL with hash-based caching
  populate_langs.py    # Parse TP2 LANGUAGE directives from extracted mods, write langs maps to mod JSONs
  populate_kits.js     # Extract kit data from mod tp2/tra source files into mod detail files
  populate_portraits.py  # Build portrait mappings from extracted mod portrait directories
  extract_vanilla_spells_spl.py  # Extract per-spell metadata from BG2:EE SPL files → spells-vanilla.json
  extract_installed_mod_spells.py  # Extract real mod spell data from installed game override/ + TLK
  extract_vanilla_items.py   # Extract vanilla items from BG2:EE BIF/KEY/TLK → items-vanilla.json
  extract_item_icons.py      # Extract vanilla item BAM icons → items/icons/ PNGs
  extract_mod_item_icons.py  # Extract mod item BAM icons from extracted mod folders
  tag_mod_spell_spheres.py   # Auto-tag mod-added priest spells with AD&D 2e sphere membership
  scan_item_mods.js    # Scan extracted mod tp2 files for item additions → item_scan_report.json
  populate_items.js    # Scaffold item data (items/it/itC) into mod detail files from scan report (--resync rebuilds from updated scans)
  enrich_item_data.py  # Resolve names/descriptions from SAY patterns, per-item TRAs, COPY_EXISTING, and dialog.tlk strrefs
  populate_item_stats.py / populate_item_specials.py / populate_item_metadata.py  # Vanilla .itm binary parsing for stats, special effects, and equipment metadata
  populate_mod_item_stats.py / populate_mod_item_specials.py / populate_mod_item_metadata.py  # Mod-item equivalents
  apply_item_overrides.py  # Apply manual overrides + auto-flag internal/creature items (dialogue names, empty shells, impossible stats)
  tp2_to_modjson.py    # Generate a mod detail file skeleton from a WeiDU tp2 file
  lib/mods-io.js       # Shared mod read/write utilities for Node.js scripts
  validate_mods.js     # Validate per-mod file schema and consistency

.github/workflows/
  update-versions.yml  # Weekly scheduled version scan (scan_versions.py + scrape_weaselmods.py)

index.html             # The app (single-file React 18, fetches data/ at startup)
```

## Contributing

### Adding a mod to the catalog

Create a new JSON file in `data/mods/` named after the mod's tp2 name (e.g., `MODNAME.json`), and add an entry to `data/mods/_catalog.json` mapping the mod's `i` value to the filename. The index is rebuilt automatically on commit.

**Per-mod file** (`data/mods/MODNAME.json`):

```json
{
  "i": 999,
  "t": "MODNAME",
  "n": "Human-Readable Name",
  "c": "QUEST MODS BG2",
  "u": "https://github.com/author/mod",
  "a": "Author Name",
  "v": "4.2",
  "sum": "One-sentence summary of what this mod does.",
  "tags": ["quest"],
  "ph": ["SoA"],
  "no": "Install notes...",
  "ord": 500,
  "co": [
    {
      "n": "Main Component",
      "cn": 0,
      "wf": "MODNAME",
      "wp": "MODNAME\\MODNAME.TP2",
      "wc": 0,
      "wq": "exact"
    }
  ],
  "conflicts": [],
  "dependencies": []
}
```

**Catalog entry** (`data/mods/_catalog.json`):

```json
{
  "999": "MODNAME.json"
}
```

The pre-commit hook automatically rebuilds `mods-index.json` when you commit changes to any mod file. You can also rebuild manually with `python scripts/build_index.py --write`.

### Mod-level field reference

| Field | Required | Description |
|-------|----------|-------------|
| `i` | Yes | Unique mod ID |
| `sv` | Yes | Schema version (integer). See [Schema versioning](#schema-versioning) below. Current: `1` |
| `t` | Yes | WeiDU tp2 name (folder name, case-sensitive) |
| `n` | Yes | Human-readable mod name |
| `c` | Yes | Primary install order category (must match a key in `data/categories.json`) |
| `cats` | No | Per-component category overrides array. For merged multi-category mods, each element maps to the corresponding component's actual category. `null` means "use the primary `c`" |
| `s` | No | Subcategory description |
| `u` | No | URL to mod homepage or download |
| `a` | No | Author name(s) |
| `v` | No | Latest known version string |
| `sum` | No | One-sentence mod summary |
| `ph` | No | Game phases array: `["BG1","SoD","SoA","ToB"]` — **narrative span**, distinct from `games` (engine target) |
| `games` | No | Engine/game target array derived from tp2 `REQUIRE_PREDICATE GAME_IS`. Mod-level value is the union of all component `games` arrays. Omitted = universal (no predicate in tp2). See [Game targets (`games` field)](#game-targets-games-field) below |
| `no` | No | Mod-level install notes |
| `ord` | Yes | Explicit install order position (integer) |
| `tags` | No | Tag array for filtering (e.g., `["qol","restore"]`) |
| `cl` | No | Install order changelog array (see below) |
| `co` | Yes | Array of components (full per-mod file only) |
| `cc` | Yes | Component count (index entry only) |
| `conflicts` | No | Array of conflict rules (per-mod file only) |
| `dependencies` | No | Array of dependency rules (per-mod file only) |
| `pt` | No | Portrait data — NPC and/or PC portraits provided by this mod (see "Adding portrait data") |
| `spl` | No | Spell data — spells modified or added by this mod (see "Adding spell data") |
| `kits` | No | Kit data — kits modified or added by this mod (see "Adding kit data") |
| `kitAbilities` | No | Structured kit ability data for the Character Planner (see "Adding kit data" → `kitAbilities` section) |
| `items` | No | Item data — items added or modified by this mod (see "Adding item data") |
| `ki` | No | Known issues — mod-specific error/warning patterns for the debug log analyzer (see "Adding known issues") |
| `prof` | No | Proficiency data — weapon proficiency system changes made by this mod (see "Adding proficiency data") |
| `langs` | No | Language map — maps ISO 639-1 language codes to WeiDU LANGUAGE indices for this mod's TP2. E.g., `{"en": 0, "fr": 2, "de": 3}`. Auto-populated by `scripts/populate_langs.py` from TP2 files. Omitted for English-only mods (defaults to `#0`). Used by the Export language selector to generate correct `#lang` values in WeiDU.log |
| `pfx` | No | WeiDU file prefix for this mod (e.g., `"D5"`, `"7C"`). Used by the Prefix Registry in the Help tab and for conflict detection |
| `gh` | No | GitHub repo identifiers: `{"o": "Owner", "r": "RepoName"}`. Static only — dynamic data (stars, push dates) comes from `version_cache.json` at runtime |
| `au` | No | Author URL (forum profile or personal homepage, when different from `u`) |
| `dl` | No | Download URL (direct download link, when different from `u`) |
| `ios` | No | Set to `false` for mods that require Windows-only tools (EEex). Used by the Cross-Platform sidebar filter |
| `ic` | No | Install conflict notes (free text). Brief description of known compatibility issues shown in the detail panel |
| `rq` | No | Requirements text (e.g., `"EET"`, `"BG1 + SoD"`). Short description of prerequisites |
| `in` | No | Install notes array: `[{"t": "description", "type": "folder\|manual"}]`. Actionable setup steps users must perform before installing (folder renames, file fixes, manual input) |
| `wb` | No | Set to `true` when ALL components are BGEE-side (dual-install mods). For per-component BGEE flags, use the component-level `wb` field |
| `rec` | No | Recommendations: `{"goes_with": [...], "avoid": [...], "tip": "..."}`. Curated advice shown in the detail panel |
| `eet_compat` | No | EET compatibility: `{"ver": "v1.5", "place": "post", "notes": "..."}`. Minimum tested version and install placement from the official EET compatibility list |

### Component fields

| Field | Required | Description |
|-------|----------|-------------|
| `n` | Yes | Component name |
| `cn` | Yes | Component number |
| `wf` | No | WeiDU folder name (defaults to mod `t`) |
| `wp` | No | WeiDU tp2 path (defaults to `WF\WF.TP2`) |
| `wc` | No | WeiDU component number (defaults to `cn`) |
| `wq` | No | Match quality: `"exact"` or `"fuzzy"` |
| `g` | No | Subcomponent group ID — mutually exclusive choices share the same `g` value (rendered as radio buttons). Used for mutex logic only, not display |
| `scn` | No | **Subcomponent name** — resolved WeiDU `SUBCOMPONENT` @ref. The human-readable group header WeiDU shows during install (e.g. `"Improved Golems"`, `"Static PsT Character Portraits"`). Siblings (components with the same `g`) share the same `scn`. See [Subcomponent hierarchy](#subcomponent-hierarchy-scn-and-grn) below |
| `grn` | No | **Group name** — resolved WeiDU `GROUP` @ref. The top-level install-order category label from the tp2 (e.g. `"Enemy Improvements"`, `"Cosmetic Changes"`). Optional, applied where the tp2 uses it |
| `tg` | No | Component tag(s) — string or array of strings. Colored badges shown on the component row. Values: `rec` (REC, green — recommended), `adv` (ADV, purple — advanced), `cos` (COS, blue — cosmetic), `cau` (CAUTION, red — risky), `pnp` (PnP, gold — pen-and-paper rules), `qol` (QoL, cyan — quality of life) |
| `pi` | No | Project Infinity ID override. When present, the PI-format export uses this string instead of the auto-generated `MOD:cn;name` format |
| `pl` | No | Platform restriction. Set to `"win"` for components that require EEex (Windows only). Displays a WIN badge |
| `x` | No | Parent component **INDEX** (array position in `co[]`, not `cn` value). Marks sub-options that depend on a parent component. When the parent is deselected, all sub-options with matching `x` are auto-deselected |
| `rd` | No | Required dependency **INDEX** (array position in `co[]`). Marks components that require another component from the same mod to function. When the required component is not selected, the UI shows a pink warning dot on the component, a "missing reqs" count in the conflict banner, and a "+ Enable" button to quickly add the missing component. Example: SCS tactical components (cn:6000-8190) all have `"rd": 67` pointing to cn:5900 (AI Init) |
| `rd2` | No | Secondary required dependency **INDEX**. For chain dependencies where a component requires two other components. Example: SCS cn:6840 requires both cn:5900 (via `rd`) AND cn:6030 (via `rd2`) |
| `dep` | No | Set to `true` for DEPRECATED components. The component still exists in the tp2 (possibly commented out) but the mod author recommends against using it. Displayed with a visual indicator but still selectable |
| `gone` | No | Set to `true` for components that have been REMOVED from the mod entirely. These are NOT selectable by users but remain in the database so the conflict system can validate references to them. Important for data completeness — other mods may have conflict entries pointing at these component numbers |
| `cat` | No | Per-component category override (for merged multi-category mods). Overrides the mod-level `c` for install order placement |
| `ord` | No | Per-component install order override. When a single mod has components that must install at different positions |
| `wb` | No | Set to `true` for BGEE-side components (dual-install mods) |
| `no` | No | Component-level notes |
| `in` | No | Install notes array (same format as mod-level `in`). Component-specific setup steps |
| `k` | No | Number of ADD_KIT calls this component makes (for kit cap tracking) |
| `kC` | No | Per-component kit class breakdown. Keys are class names (e.g., `"fighter"`, `"ranger"`), values are kit counts. Auto-computed by `scripts/build_index.py` and stored in the index as `coKC` |
| `sp` | No | Total new SPELL.IDS slots consumed by this component (wizard + priest). Should equal the sum of `spLv` values when both are present |
| `spLv` | No | Per-level SPELL.IDS breakdown. Keys: `w1`–`w9` (wizard levels), `p1`–`p7` (priest levels). Values: number of new spells added at that level. E.g., `{"w3": 2, "p7": 4}`. The game has a 50-slot-per-level cap; the Diagnostics tab tracks per-level usage |
| `ss` | No | SPLSTATE.IDS slots consumed by this component |
| `it` | No | Number of items added by this component (for item tracking in the Items tab overview) |
| `itC` | No | Per-type item breakdown. Keys are item type names (e.g., `"large sword"`, `"armor"`, `"misc"`). Values: count of items of that type. E.g., `{"large sword": 3, "armor": 1}`. Auto-computed by `scripts/build_index.py` and stored in the index as `coITC` |
| `games` | No | Engine/game target array. Auto-derived from tp2 `REQUIRE_PREDICATE GAME_IS` by `scripts/scan_game_targets.py`. Omitted = universal (no predicate in the tp2 — assumes any-compat). See [Game targets (`games` field)](#game-targets-games-field) below |

### Game targets (`games` field)

Both mod- and component-level optional field. Array of lowercase game ident tokens matching WeiDU's `GAME_IS` vocabulary verbatim, derived from `REQUIRE_PREDICATE GAME_IS ~...~` clauses in the tp2 source.

**Semantics:**
- Listed tokens are the OR-union — component installs if the target game matches *any* token in the list (same as WeiDU).
- **Omitted / null** = universal. The tp2 has no engine predicate on this component; assume it installs on any engine the mod's tp2 supports.
- Mod-level `games` is the union of all component `games` arrays (derived at index-build time). If any component is universal, the mod-level field is also omitted.

**Token whitelist:**

*EE family — these are the install targets the app supports:*

| Token | Game |
|-------|------|
| `eet` | Enhanced Edition Trilogy |
| `bgee` | Baldur's Gate: Enhanced Edition (standalone, pre-EET) |
| `bg2ee` | Baldur's Gate II: Enhanced Edition (standalone) |
| `iwdee` | Icewind Dale: Enhanced Edition |
| `pstee` | Planescape: Torment: Enhanced Edition |
| `sod` | Siege of Dragonspear (BGEE + SoD DLC) |

*Classic / legacy — tagged for data fidelity, but **not** install targets. Components scoped only to classic tokens hard-conflict against every EE install target the app supports:*

| Token | Game |
|-------|------|
| `bg1` | Baldur's Gate (classic) |
| `bg2` `soa` | Baldur's Gate II: SoA (classic) |
| `tob` | Baldur's Gate II: Throne of Bhaal (classic) |
| `totsc` | BG1: Tales of the Sword Coast (classic) |
| `bgt` | Baldur's Gate Trilogy (conversion mod) |
| `tutu` `tutu_totsc` | Easy Tutu (BG1-in-BG2-engine conversion mod) |
| `iwd` | Icewind Dale (classic) |
| `iwd2` | Icewind Dale II (classic) |
| `how` | Heart of Winter (IWD classic expansion) |
| `totlm` | Trials of the Luremaster (IWD classic expansion) |
| `pst` | Planescape: Torment (classic) |
| `ca` | Classic Adventures (BG2 classic-tree expansion) |
| `iwd_in_bg2` | IWD-in-BG2 conversion mod |

**Token normalization:** hyphens are treated as underscores (`iwd-in-bg2` == `iwd_in_bg2`), case-insensitive, matching WeiDU's tolerant parsing.

**Negative predicates** (both `NOT GAME_IS ~...~` and `!GAME_IS ~...~` — WeiDU accepts both forms) are expanded by the scanner into positive form: the component's `games` list becomes `{full whitelist} \ {excluded tokens}`. This keeps consumers on a single positive list with one filter path.

**Scanner scope (v2):** per-BEGIN `REQUIRE_PREDICATE GAME_IS ~...~`, `REQUIRE_PREDICATE NOT GAME_IS ~...~`, and `REQUIRE_PREDICATE !GAME_IS ~...~`, plus parenthesized variants. `ACTION_IF GAME_IS` blocks are **not** component gates in WeiDU's grammar (verified across the 605-mod catalog: zero tp2s wrap BEGIN components with them). Those blocks are used for setup-phase logic only — `OUTER_SPRINT`, `INCLUDE`, variable plumbing — not for conditional component definition. The scanner does not pursue them.

**Pre-commit integration:** when any `data/mods/*.json` is staged, the pre-commit hook runs `scripts/scan_game_targets.py --apply --only <stem>` per staged mod, populating any empty `games` fields from the tp2. Idempotent: already-populated fields are never overwritten.

**Validation rules:**
- Tokens must be in the whitelist; unknown tokens → error.
- Empty `games: []` → error (means "compatible with nothing" — always a data bug).
- `games` field only makes sense if non-empty or omitted.

**Hard conflict derivation (runtime):** a component is EE-installable if `games ∩ {eet, bgee, bg2ee, iwdee, pstee} ≠ ∅`, or `games` is omitted. When a component's `games` is entirely classic-only, any selection of it on an EE install target is a hard conflict and should be blocked at the UI / runner layer. The data layer doesn't carry a derived boolean — consumers compute installability from `games` against the active install target.

### Subcomponent hierarchy (`scn` and `grn`)

WeiDU's `BEGIN` is one of three things in a mod's install flow:

1. A **standalone component** (the most common case — a checkbox that installs one thing)
2. A member of a **`SUBCOMPONENT` group** — mutually exclusive variants the user picks one of (radio-button group)
3. A member of a **`GROUP`** — a top-level install-order category label (e.g. "Enemy Improvements", "Cosmetic Changes")

The `scn` and `grn` fields store the human-readable headers for (2) and (3), resolved from the tp2's TRA file at scan time.

**Why this matters:** when a mod author uses SUBCOMPONENT with generic sub-option names (e.g. Tactics Remix has 8 pairs of components named "Double Tactics Remix HP values" / "Default Tactics Remix HP values" under different SUBCOMPONENT groups like "Improved Golems", "Improved Mind Flayers", etc.), the only disambiguating context is the SUBCOMPONENT @ref. Without it, the UI has no way to show the user which pair is for which enemy.

**Shape:**
- `scn` — plain string, per component. Siblings in the same `g` group share the same `scn`.
- `grn` — plain string, per component. Optional; many mods don't use GROUP at all.

**Example (Tactics Remix):**
```json
{
  "cn": 7000,
  "n": "Double Tactics Remix HP values",
  "g": "TacticsRemix-ImprovedGolems",
  "scn": "Improved Golems",
  "grn": "Enemy Improvements"
}
{
  "cn": 7001,
  "n": "Default Tactics Remix HP values",
  "g": "TacticsRemix-ImprovedGolems",
  "scn": "Improved Golems",
  "grn": "Enemy Improvements"
}
```

UI should render this as:
```
[Enemy Improvements]             ← grn
  Improved Golems — Choose One:  ← scn + "Choose One" because g is set
    □ Double Tactics Remix HP values   ← n
    □ Default Tactics Remix HP values
```

**Scanner:** `scripts/scan_subcomponents.py` extracts `SUBCOMPONENT @ref` and `GROUP @ref` from each BEGIN block and resolves via TRA. Handles string-literal forms (`SUBCOMPONENT ~name~` and `SUBCOMPONENT "name"`) and negation/predicate variants. Does not pursue `FORCED_SUBCOMPONENT` as a distinct field — it's treated identically to `SUBCOMPONENT` (both produce a group header).

**Index aggregation:** `data/mods-index.json` carries `coScn[]` and `coGrn[]` parallel arrays (one entry per component). No mod-level aggregate; the UI derives groupings per-component from these arrays.

**Relationship to `g`:** `g` and `scn` describe the same relationship from two angles. `g` is the mutex ID (for radio-button behavior), `scn` is the display header (for UI labeling). In practice they travel together — components sharing `g` share `scn`. The UI may prefer `scn` for the header and still use `g` for mutex logic.

### Schema versioning

Every mod file carries an `sv` (schema version) field as its second property (right after `i`). Current version: **`1`**.

**Why:** The schema has evolved over time — fields have been added, semantics refined, meanings clarified. Without a version stamp, tools that consume this data (Infinity Mod Forge, Infinity Mod Runner, infinity-mod-telemetry, third-party mod authors) have no way to detect when a file is ahead of or behind their expectations. The `sv` field lets consumers fail loudly on unknown versions instead of silently misinterpreting data.

**What v1 defines** (the current baseline):
- `dep` as a **string reason** (not boolean). A truthy `dep` means the author discourages installing, but the component still exists in the tp2 and still installs.
- `gone: true` for components **fully removed** from the tp2. These are retained in the database so other mods' conflict entries can still resolve the cn, but they are not user-selectable.
- `dep` and `gone` are **mutually exclusive**.
- `tp2n` field: the raw tp2 component name (pre-enrichment), used by `scripts/audit_tp2_drift.py` to detect drift between the database and the canonical v18 tp2.
- Preset key format: `"<modId>-<cn>"` where `cn` is the tp2 DESIGNATED number (or BEGIN-order fallback). NOT the `co[]` array index.
- `wf` field: every component in a mod must use the same `wf` value. Cross-contamination (a mod's components pointing at different install folders) is a data bug.

**When to bump:**
- Renaming/removing a required field — **major bump**.
- Changing the meaning of an existing value (e.g., flipping `dep` back to boolean, or letting `gone` coexist with `dep`) — **major bump**.
- Adding a new optional field — no bump; consumers default to absent.
- Fixing data (adding missing components, correcting names) — no bump.

**Migration scripts** live in `scripts/migrations/v<N>_to_v<N+1>.py`. Each must be idempotent and additive where possible.

**Validator:** `scripts/validate_mods.js` warns on any mod missing `sv` or carrying an `sv` the validator doesn't recognize.

### Merged mods (multi-category)

Mods that previously existed as separate split entries sharing the same tp2 (e.g., SCS had 4 entries across Tactical, Post-Tactical, Creature, and Kit categories) are now merged into a single catalog entry. Per-component `cat` fields and the mod-level `cats` array control which category each component appears in for install order purposes.

### Install order changelog

Mods can have a `cl` array tracking install-order-related changes (category moves, positioning updates, compatibility-driven reordering). This is not a general mod changelog; it only records changes relevant to install order.

```json
"cl": [
  {"d": "2026-03-10", "m": "Added from Infinity Insanity WeiDU logs"},
  {"d": "2026-03-15", "m": "Moved from QUEST MODS BG2 to NPC EXPANSIONS per EET compat update"}
]
```

The changelog is shown as a collapsible dropdown in the mod detail panel.

### Adding a conflict

Add a conflict to the relevant mod's per-mod file under the `conflicts` array:

```json
{
  "a": "modA_tp2",
  "b": "modB_tp2",
  "severity": "hard",
  "reason": "Why these conflict",
  "comp_a": "Component name in mod A",
  "comp_b": "Component name in mod B"
}
```

**Severity levels:**
- `hard` — Mods are mutually exclusive. "is incompatible with"
- `partial` — Specific components conflict. "may conflict with"
- `soft` — Possible issues. "may conflict with"

**Optional fields:**
- `comp_a` / `comp_b` — When present, the alert shows which specific components conflict instead of just mod names.
- `orderOnly` — Set to `true` when the entry is not a real compatibility conflict but an informational note about install order, cosmetic "last installed wins" overlap, complementary mods, or managed coexistence. These entries display in a separate teal "order" category in the conflict panel and are hidden by default. Use this for entries where Infinity Mod Forge's install order already handles the situation and no user action is needed.

### Adding a dependency

Add to the `dependencies` array in the dependent mod's per-mod file:

```json
{
  "mod": "dependent_tp2",
  "requires": "required_tp2",
  "type": "hard",
  "reason": "Why this dependency exists"
}
```

### Adding portrait data

Portrait data lives in two places: NPC definitions in `data/npcs.json` and per-mod portrait mappings in each mod's `pt` field.

**1. Add NPC definitions** (if the NPC doesn't already exist in `data/npcs.json`):

```json
{
  "npc_id": {
    "name": "Display Name",
    "game": "bg2",
    "recruitable": true,
    "default": "portraits/default/npc_id.png"
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Display name for the portrait viewer |
| `game` | Yes | Game scope: `"bg1"`, `"bg2"`, `"both"`, `"sod"`, `"tob"` — controls which phases show |
| `recruitable` | No | `true` for party companions (shows under Companions tab) |
| `default` | No | Path to vanilla/default portrait image |
| `defaultBg1` | No | BG1-specific default portrait (for NPCs with `"game": "both"`) |

**2. Add portrait images** as PNGs under `portraits/<mod_folder>/`.

**3. Add `pt` field** to the mod's `data/mods/<mod>.json`:

```json
{
  "i": 690,
  "t": "PaintBG",
  "pt": {
    "npc": {
      "7": [["aerie", "portraits/paintbg/aerie_v1.png", "bg2"]],
      "8": [["aerie", "portraits/paintbg/aerie_v2.png", "bg2"]]
    },
    "pc": {
      "2": {
        "label": "PaintBG: BG2 PC Portraits",
        "images": ["portraits/paintbg_pc/man1.png", "portraits/paintbg_pc/woman1.png"]
      }
    }
  },
  "co": [...]
}
```

**NPC portraits** (`pt.npc`): Keys are the **array index** of the component in `co[]` (not the `cn` value). Each value is an array of `[npc_id, image_path, phase]` tuples. Phase is `"bg1"`, `"sod"`, `"bg2"`, `"tob"`, or `"all"`.

**PC portraits** (`pt.pc`): Keys are array indices. Each value has a `label` (display name) and `images` array of portrait paths.

A single component can provide portraits for multiple NPCs (e.g., a "Followers: Vanilla" component that sets portraits for all vanilla companions). When multiple selected mods provide portraits for the same NPC in the same phase, the last mod in install order wins.

### Adding spell data

Spell modification/addition data lives in each mod's `spl` field, keyed by **component array index** (same convention as `pt` for portraits). The vanilla spell catalog is in `data/spells-vanilla.json`.

**Add `spl` field** to the mod's `data/mods/<mod>.json`:

```json
{
  "i": 288,
  "t": "spell_rev",
  "spl": {
    "0": {
      "scope": "overhaul",
      "spells": [
        ["SPWI112", "replace", "Rebalanced scaling: 1 missile per 2 levels"],
        ["SPWI408", "modify", "Reduced max skins from 10 to 5"]
      ],
      "new": [
        ["YOURID01", "wizard", 4, "Conjuration", "Shadow Monsters", "Summons shadow creatures"]
      ]
    }
  },
  "co": [...]
}
```

**Modified vanilla spells** (`spells` array): Each entry is a `[resref, action, summary]` tuple.
- `resref`: IESDP spell resource reference (e.g., `SPWI112` for Magic Missile, `SPPR104` for Cure Light Wounds)
- `action`: One of `replace` (complete overhaul), `modify` (significant change), `tweak` (minor adjustment), `remove` (spell disabled)
- `summary`: Brief description of what changed

**New spells** (`new` array): Each entry is a `[resref, type, level, school, name, description]` tuple.
- `resref`: Unique identifier for the new spell (use `YOUR` prefix for mod-added spells without known SPELL.IDS entries)
- `type`: `"wizard"`, `"priest"`, `"innate"`, `"hla"`, or `"special"`
- `level`: Spell level (1-9 for wizard, 1-7 for priest, 0 for innate/HLA)
- `school`: Spell school (Abjuration, Alteration, Conjuration, Divination, Enchantment, Evocation, Illusion, Necromancy)
- `name`: Display name
- `description`: 1-2 sentence summary

**Scope** (optional): `"overhaul"` (major revision like SR), `"additions"` (new spells like IWDification), `"tweaks"` (minor adjustments), `"icons"` (visual changes only).

New spells are merged into the main Wizard/Priest/Innate spell tables at their proper level. The UI shows them with a green ADDED badge. When multiple mods modify the same vanilla spell, the last mod in install order wins and a conflict indicator appears.

**Extracting real mod spell data (recommended over `YOUR*` placeholders)**: For mods that add large numbers of spells, `scripts/extract_installed_mod_spells.py <prefix> --write --report out.json` reads an installed game's `override/` + patched `dialog.tlk` to produce real ref names, levels, schools, icon refs, and human-readable names. It also pulls the BAM icons and writes them to `spells/icons/<ref>.png`. Run against an installed BG2:EE with the mod present; pass the mod's WeiDU prefix (e.g. `D5` for Faiths and Powers, `AC` for Aerial, etc.). `scripts/extract_mod_spell_icons.py <mod_dir>` does the icon-only pass against an extracted mod source directory (no TLK needed, but names come out as raw SPL filenames).

**Global spell rules** live in `data/spell-tables.json`: `sphereList` (15 BG2 spheres), `classSpellLevelCaps` (per-class max level), `scribeIntByLevel` (INT → max learnable level, chance to learn), `sorcererPicksPerLevel`, `bardSpellLevelCapByLevel`.

### Adding kit data

Kit modification/addition data lives in each mod's `kits` field (and optionally `classes` for class overhauls), keyed by **component array index**. Vanilla kits are in `data/kits-vanilla.json`, base classes in `data/classes-vanilla.json`.

**Add `kits` field** to the mod's `data/mods/<mod>.json`:

```json
{
  "i": 320,
  "t": "morpheus562skitpack",
  "kits": {
    "0": {
      "new": [
        ["BATTLE_MASTER", "fighter", "Battle Master", "Two-handed weapon expert with cleaving attacks."]
      ],
      "modify": [
        ["BERSERKER", "tweak", "Revised rage duration and immunities"]
      ]
    }
  },
  "co": [...]
}
```

**New kits** (`new` array): Each entry is a `[kitId, class, name, description]` tuple.
- `kitId`: Unique identifier (KITLIST.2DA name, e.g., `BATTLE_MASTER`)
- `class`: One of `fighter`, `ranger`, `paladin`, `cleric`, `druid`, `thief`, `bard`, `mage`, `sorcerer`, `monk`, `shaman`, `barbarian`, `multi` (multiclass), `npc` (non-player/internal kits)
- `name`: Display name
- `description`: 1-2 sentence summary (~100 chars)

**Modified vanilla kits** (`modify` array): Each entry is a `[vanillaKitId, action, summary]` tuple.
- `vanillaKitId`: Vanilla kit reference from `kits-vanilla.json` (e.g., `BERSERKER`, `ASSASSIN`)
- `action`: One of `replace` (complete overhaul), `modify` (significant change), `tweak` (minor adjustment), `remove` (kit disabled)
- `summary`: Brief description of what changed

**Class overhauls** (`classes` field, separate from `kits`): For mods that modify base classes rather than kits.

```json
"classes": {
  "0": [
    ["FIGHTER", "modify", "Revised THAC0 progression and proficiency system"]
  ]
}
```

**Component `kC` field**: Per-component kit class breakdown (parallel to `spLv` for spells). Auto-computed by `scripts/build_index.py` and stored in the index as `coKC`.

```json
"kC": { "fighter": 2, "ranger": 1 }
```

**NPC kits**: Use class `"npc"` for kits that count against the 320 cap but aren't player-selectable (NPC companion kits, creature kits, internal mod kits). For NPC assignment components, use the format `"Kit Name: NPC Name"` in the name field — the UI will render the kit name prominently with the NPC name as a smaller subtitle.

Kit cards display in the Kits tab organized by class subtabs. The Kit Cap (320 engine limit) tracker shows in the Overview with per-class breakdowns. Action badges (ADDED, MODIFIED, TWEAKED, REPLACED, VANILLA) appear as colored top bars on each card.

**`kitAbilities` field** (optional, for Character Planner integration): Structured data the planner reads to compute dual/multi-class eligibility, HLA pool filtering, spell restrictions, and stat bonuses. Keyed by **component array index** → kit ID.

```json
"kitAbilities": {
  "0": {
    "BATTLE_MASTER": {
      "passive": [
        { "n": "Mastery Bonus", "type": "thac0PerLevel", "rate": 3, "value": 1, "desc": "+1 THAC0 per 3 levels" }
      ],
      "activated": [
        { "n": "Trip Attack", "freq": "1/day per 4 levels", "effects": "Knockdown on hit.", "level": 2 }
      ],
      "restrictions": { "armor": "no plate" },
      "statReq": { "str": 15 },
      "statBonus": { "con": -1, "note": "-1 CON modifier" },
      "canDual": true,
      "canDualTo": ["MAGE", "THIEF", "CLERIC", "DRUID"],
      "allowedMulticlass": [],
      "hlaPool": { "class": "FIGHTER", "include": ["Trip Mastery"], "note": "Standard fighter HLA pool + custom additions" },
      "spellRestrictions": { "noSpells": true, "note": "Fighter kit." },
      "resistBonus": { "fire": 10, "note": "+10% fire resistance" },
      "npcOnly": false
    }
  }
}
```

Supported fields:
- `passive` / `activated` / `restrictions` — Required. Kit descriptions and mechanical effects
- `statReq` — Minimum ability score requirements (e.g. `{str: 15}`)
- `statBonus` — Innate stat modifiers the kit grants (e.g. `{dex: 1, con: -1}`)
- `canDual` — Boolean; whether the kit can dual-class (paladin/bard/sorcerer/monk kits: false)
- `canDualTo` — Array of target classes the kit can dual to (use vanilla defaults or mod-specific)
- `allowedMulticlass` — Array of `"CLASS/CLASS"` combos for kits that permit multi-class
- `hlaPool` — Object with `class`, optional `include`/`exclude`, and `note`. The planner uses this to filter which HLAs appear at lv20+
- `spellRestrictions` — Object with `noSpells` / `bannedSchools` / `oppositionSchools` / `sphereSystem` / `deity` / `specialist` / `note`
- `resistBonus` — Object with per-type resistance percentages (`fire`, `cold`, `electricity`, `acid`)
- `npcOnly` — Boolean; if true, kit is hidden at chargen (companion NPC kits only)

The planner looks up by `detail.kitAbilities[''+componentIndex][kitId]` when a component is selected. Falls back to `chargen.json.kitAbilities` for vanilla kits.

### Adding item data

Item modification/addition data lives in each mod's `items` field, keyed by **component array index** (same convention as `spl` for spells and `kits` for kits). Vanilla items are in `data/items-vanilla.json`.

**Add `items` field** to the mod's `data/mods/<mod>.json`:

```json
{
  "i": 273,
  "t": "itemupgrade",
  "items": {
    "0": {
      "scope": "additions",
      "new": [
        ["C2AMUL01", "amulet", "Amulet of Selune's Grace", ""],
        ["C2SW1H01", "large sword", "Purifier +5", ""]
      ]
    }
  },
  "co": [...]
}
```

**New items** (`new` array): Each entry is a `[resref, type, name, description]` tuple.
- `resref`: Item resource reference (8-char max, uppercase)
- `type`: Item category — one of: `large sword`, `short sword`, `dagger`, `axe`, `mace`, `hammer`, `flail`, `morning star`, `staff`, `spear`, `halberd`, `bow`, `crossbow`, `sling`, `dart`, `arrow`, `bolt`, `bullet`, `armor`, `shield`, `helmet`, `bracers`, `boots`, `belt`, `cloak`, `robe`, `ring`, `amulet`, `gem`, `wand`, `potion`, `scroll`, `food`, `misc`
- `name`: Display name (can be empty if unknown)
- `description`: Brief description (can be empty)

**Modified vanilla items** (`modify` array, future use): Each entry is a `[resref, action, summary]` tuple, same pattern as spells.

**Scope** (optional): `"additions"` (new items), `"tweaks"` (rebalances), `"overhaul"` (major revision like Item Revisions).

**Component `itC` field**: Per-component item type breakdown (parallel to `kC` for kits). Auto-computed by `scripts/build_index.py` and stored in the index as `coITC`.

```json
"itC": { "large sword": 3, "armor": 1, "ring": 2 }
```

Item icons are auto-resolved from `items/icons/I{RESREF}.png`. The extraction scripts `scripts/extract_vanilla_items.py` and `scripts/extract_mod_item_icons.py` generate icons from BG2:EE BAM files and mod source data respectively.

Items are displayed in the Items tab organized by 7 category sub-tabs: Weapons, Ranged, Armor, Accessories, Consumables, Miscellaneous, and Internal. The Internal tab shows non-player items (creature attacks, keys, containers, broken items, familiars) in a compact table instead of cards. Type breakdown pills within each category act as clickable filters.

### Adding known issues

Known issues live in two places:

- **Per-mod `ki` field** — Mod-specific errors and warnings. The `ki` array lives in the mod's `data/mods/<mod>.json`, co-located with the mod it describes (like `pt` for portraits, `spl` for spells). No `mod` field is needed — it's implicit from the file.
- **Global `data/known_issues.json`** — Cross-mod and generic patterns that apply to any mod (e.g., `DELETE_BYTES out of bounds`, BCS round-trip failures, `NOT_INSTALLED`). Use `"mod": "*"` for these.

The debug log analyzer merges both sources at runtime. Per-mod `ki` entries are loaded from `_detailCache` when mod details are fetched.

**Per-mod known issue** — add a `ki` array to `data/mods/<mod>.json`:

```json
{
  "i": 544,
  "t": "valen",
  "ki": [
    {
      "pattern": "ERROR Installing \\[Valen\\]|cannot open target.*portraits",
      "severity": "error",
      "category": "concerning",
      "description": "Valen COPYs valenL.bmp to a portraits/ directory that doesn't exist.",
      "workaround": "Create a portraits/ directory in the game folder before installing.",
      "user_action": "apply-patches",
      "components": [0],
      "forum": "https://example.com/thread"
    },
    {
      "pattern": "VALEN\\.tra.*no translation for @\\d+",
      "severity": "warning",
      "category": "cosmetic",
      "description": "Translation tag missing — falls back to English. No player-visible impact outside non-English locales.",
      "workaround": "None needed for English installs.",
      "user_action": "none"
    }
  ],
  "co": [...]
}
```

**Global known issue** — add to `data/known_issues.json`:

```json
{
  "pattern": "DELETE_BYTES out of bounds",
  "mod": "*",
  "severity": "critical",
  "known": true,
  "description": "A mod tried to modify a file that was a different size than expected.",
  "workaround": "Check install order."
}
```

**`ki` field reference:**

| Field | Required | Description |
|-------|----------|-------------|
| `pattern` | Yes | Regex pattern to match against error/warning lines in the debug log. Use `\\[` for literal brackets. Alternation (`\|`) is supported for multiple patterns |
| `severity` | Yes | One of `critical`, `error`, `warning`, `info`. Describes the underlying mechanism (WeiDU exit, warn line, etc.) |
| `category` | No | One of `cosmetic`, `likely-benign`, `caution`, `concerning`. Describes **player-visible impact** — orthogonal to `severity`. A `severity: "warning"` with `category: "cosmetic"` is a WeiDU warn line the user can safely ignore; a `severity: "error"` with `category: "concerning"` is a genuine bug they should act on. Used by the runner's live-install issues panel to show a "7 warnings: 6 cosmetic · 1 unknown" breakdown instead of an undifferentiated count |
| `user_action` | No | Short hint for the end user, keyed from a small vocabulary (see below). Separate from `workaround` — the workaround is the detailed how-to; `user_action` is the one-word tag the UI uses to decide which button/badge to show |
| `description` | Yes | What this error means and why it happens |
| `workaround` | Yes | How to fix or work around the issue |
| `components` | No | Array of component **indices** (positions in `co[]`, not `cn` values) that this issue affects. Omit for mod-wide issues |
| `forum` | No | URL to a forum thread or bug report with more context |

**`category` values:**

| Value | Meaning | UI color | Example |
|-------|---------|----------|---------|
| `cosmetic` | Zero player-visible impact — install log noise only | muted / gray | TRA missing tag (falls back to English), IDS already-has-entry, harmless BCS decompile warning already handled by our round-trip safety patches |
| `likely-benign` | Usually fine, but keep an eye out | blue | Missing resource the mod gracefully falls back from, kit index shuffled to a different ID |
| `caution` | Might indicate a real issue — check in-game | yellow | Item ability header offset/length mismatch, unexpected dialogue tag |
| `concerning` | Likely a real problem — read the workaround | orange | Critical script corruption, missing prerequisite, cross-mod script collision |

Unclassified entries (no `category` set) render as "unknown" in the runner UI — a signal for the user that this warning hasn't been triaged yet. Aim to classify all entries over time.

**`user_action` values:**

| Value | Meaning | UI rendering |
|-------|---------|--------------|
| `none` | No action needed. Safe to ignore | no button |
| `retry` | Transient — re-run the install or just this batch | "Retry" button |
| `apply-patches` | The EETMR patches fix this; ensure patches are applied | link to Ready Check patches row |
| `check-docs` | Read the description/workaround/forum for details | expand workaround inline |
| `contact-author` | Unusual — mod author should know | link to forum/GitHub issue |

**When to use per-mod vs. global:**

- Use **per-mod `ki`** when the pattern is specific to one mod (e.g., a known bug in that mod's tp2, a missing prerequisite, an incompatibility). The pattern should match the mod's component name or a distinctive error message from that mod's install.
- Use **global `known_issues.json`** when the pattern applies across many mods (e.g., WeiDU engine warnings, SFO framework issues, generic file-not-found patterns). Set `"mod": "*"`.

**`category` and `user_action` are currently being trialed on a subset of `ki` entries** — the Infinity Mod Runner's live-install issues panel uses them (when present) to show a severity breakdown instead of treating every "Installed with warnings" line identically. Entries without them still work fine for the Debug panel's post-install log analysis. Fill them in incrementally as you triage each pattern.

A growing number of mods have `ki` entries, and the global file has a curated set of generic patterns.

### Adding proficiency data

Proficiency data lives in each mod's `prof` field, keyed by **component `cn` value** (the WeiDU component number, NOT the array index). The vanilla proficiency list is in `data/chargen.json` under `proficiencies`. The Character Planner uses this data to dynamically update the proficiency picker based on selected mods.

**Add `prof` field** to the mod's `data/mods/<mod>.json`:

```json
{
  "i": 247,
  "t": "cdtweaks",
  "prof": {
    "2160": {
      "add": [
        { "id": "WAKIZASHI", "n": "Wakizashi", "cat": "melee", "desc": "Split from Scimitar" },
        { "id": "NINJATO", "n": "Ninjato", "cat": "melee", "desc": "Split from Scimitar" }
      ],
      "remove": [],
      "modify": [
        { "id": "SCIMITAR", "n": "Scimitar", "desc": "Wakizashi and Ninjato split out" }
      ]
    },
    "2200": {
      "multiclass": { "fighterMaxPips": 5 },
      "desc": "Multi-class fighters can reach Grand Mastery (5 pips)"
    }
  },
  "co": [...]
}
```

**Modes:**

- **Patch mode** (default when `mode` is absent): Uses `add`, `remove`, and `modify` to incrementally change the vanilla proficiency list. Backward-compatible.
- **Replace mode** (`"mode": "replace"`): Swaps out the entire proficiency list with a `proficiencies` array. Use for mods that completely restructure the weapon proficiency system (e.g., BG-style or IWD-style groupings). Last replace-mode component in install order wins.

**Patch operations:**

| Field | Type | Description |
|-------|------|-------------|
| `add` | Array of objects | New proficiencies: `{ "id": "...", "n": "...", "cat": "melee\|ranged\|style\|skill", "desc": "..." }` |
| `remove` | Array of strings | Proficiency IDs to remove from the list |
| `modify` | Array of objects | Changes to existing profs: `{ "id": "...", "n": "...", "maxPips": N, "desc": "..." }`. Only changed fields are required |

**Replace mode:**

```json
"2161": {
  "mode": "replace",
  "proficiencies": [
    { "id": "LARGE_SWORD", "n": "Large Sword", "cat": "melee", "desc": "Bastard, Long, Two-Handed, Katana, Scimitar" },
    { "id": "SMALL_SWORD", "n": "Small Sword", "cat": "melee", "desc": "Short Sword and Dagger" },
    { "id": "TWO_WEAPON", "n": "Two-Weapon Style", "cat": "style", "maxPips": 3 }
  ],
  "desc": "BG1-style weapon proficiency categories with fighting styles"
}
```

**Global overrides** (`global` object): Applied to all proficiencies universally.

| Field | Description |
|-------|-------------|
| `maxPips` | Override the class-group pip ceiling for all classes |
| `minPips` | Set a floor — pips below this value are locked and cannot be removed |
| `styleMaxPips` | Override the pip cap for `cat:"style"` entries specifically |

```json
"4": {
  "global": { "minPips": 3 },
  "desc": "All classes start with minimum 3 pips (Mastery) in every weapon"
}
```

**Progression overrides** (`profSlots` object): Override how many proficiency points a class group earns. Partial — only specified fields are merged.

```json
"312": {
  "profSlots": {
    "warrior": { "rate": 2 },
    "priest": { "rate": 3 },
    "rogue": { "rate": 3 },
    "arcane": { "rate": 4 }
  },
  "desc": "Accelerated proficiency progression"
}
```

Valid class groups: `warrior`, `priest`, `rogue`, `arcane`, `monk`. Fields: `initial` (starting points), `rate` (levels per new point), `maxPips` (class ceiling).

**Multiclass overrides** (`multiclass` object):

| Field | Description |
|-------|-------------|
| `fighterMaxPips` | Maximum pips a multiclass fighter can reach (vanilla: 2) |

**Informational flags** (`flags` object): Booleans displayed as info badges in the planner. Do not change the proficiency list, but inform the user about system-level changes.

| Flag | Meaning |
|------|---------|
| `aprFromSpec` | All classes gain bonus APR from weapon specialization |
| `stylesRebalanced` | Weapon style bonuses differ from vanilla |
| `pnpDualClassProfs` | PnP proficiency rules for dual-class characters |
| `luaProfSystem` | Proficiency system externalized to Lua |
| `stylesForAll` | Weapon styles available to all classes |

**Proficiency categories** (`cat` values):

| Value | Label | Description |
|-------|-------|-------------|
| `melee` | Melee Weapons | Standard melee weapon proficiencies |
| `ranged` | Ranged Weapons | Ranged weapon proficiencies |
| `style` | Fighting Styles | Two-Weapon, Sword and Shield, etc. |
| `skill` | Combat Skills | Non-weapon proficiencies added by mods (e.g., Heavy Armor, Spellcraft) |

**Vanilla proficiency IDs** (from `chargen.json`): `BASTARD_SWORD`, `LONG_SWORD`, `SHORT_SWORD`, `AXE`, `TWO_HANDED_SWORD`, `KATANA`, `SCIMITAR`, `DAGGER`, `WAR_HAMMER`, `CLUB`, `SPEAR`, `HALBERD`, `FLAIL_MORNINGSTAR`, `MACE`, `QUARTERSTAFF`, `CROSSBOW`, `LONGBOW`, `SHORTBOW`, `DART`, `SLING`, `TWO_WEAPON`, `SWORD_SHIELD`, `SINGLE_WEAPON`, `TWO_HANDED`.

Mods with `prof` entries include cdtweaks, weapons_reforged, Combat_Skill_Proficiencies, dw_talents, skills_and_abilities, HouseTweaks, item_rev, and RR.

### Design tokens

The app uses CSS custom properties defined in `:root`. To change colors or spacing globally, edit the variables at the top of `index.html`:

```css
:root {
  --bg: #0c0e14;      /* Main background */
  --bg2: #141620;     /* Card background */
  --gold: #d4a843;    /* Primary accent */
  --tx: #c8ccd8;      /* Main text */
  --grn: #4ade80;     /* Success/selected */
  --red: #f87171;     /* Error/conflict */
  --blu: #60a5fa;     /* Links/info */
  --bg-warn: #2a2010; /* Warning background */
  --bg-err: #2a1010;  /* Error background */
  /* ... see index.html for full list */
}
```

App configuration is loaded from `data/config.json` at startup, including version, engine limits, essential mod IDs, mod type icons, badge definitions, language names, category labels, URLs, and wizard onboarding data. The code declares minimal defaults that are overridden by the JSON at load time. See `data/config.json` for the full structure.

### Categories

The 26 install order categories, in order:

1. PRE EET BGEE MODS
2. EET STARTS HERE
3. ENGINE
4. INTERFACE
5. GRAPHICS
6. RESTORATIONS
7. QUEST MODS BG1
8. QUEST MODS BG2
9. QUEST MODS ToB
10. NEW NPC MODS
11. NPC EXPANSIONS
12. NPC CROSSMOD
13. CREATURE MODS
14. EXPERIENCE TWEAKS
15. ITEM ADDITION MODS
16. SPELL MODS
17. KIT & CLASS MODS
18. PRE-TACTICAL TWEAKS
19. TACTICAL MODS
20. POST-TACTICAL TWEAKS
21. NPC CUSTOMIZATION
22. POST-TACTICAL QUESTS
23. MUSIC & AUDIO
24. PORTRAITS
25. EET FINALIZATION
26. POST EET

## Data sources

The catalog is built by merging six sources:

| Source | What it provides |
|---|---|
| [install-EET-4.txt](https://www.scribd.com/document/777087788/install-EET-4) | 3,400+ component entries with install order, compatibility notes, and author commentary |
| [EET Mod Install Order Guide (Google Sheet)](https://docs.google.com/spreadsheets/d/1tt4f-rKqkbk8ds694eJ1YcOjraZ2pISkkobqZ5yRcvI/edit?gid=676921267#gid=676921267) | Mod-level metadata: authors, URLs, game phases, tags |
| WeiDU.log | Actual installed components with real tp2 paths and versions |
| [EET Compatibility List](https://k4thos.github.io/EET-Compatibility-List/) | Minimum versions and placement requirements |
| [Infinity Insanity Guide](https://docs.google.com/document/d/1hy38KD0bS2qJCaOeWz0F-50z7GkZcCH7QWjDsheKPrA/edit) | 170+ additional mods, conflict annotations, and mod URLs from Endarire's mega-install |
| [EE-Mod-Setup](https://github.com/bujiasbitwise-contributions/EE-Mod-Setup) | 168 component-level conflict rules and 105 dependency rules from the EET Game.ini config |

Mod metadata, tp2 analysis, and compatibility research also drawn from [Gibberlings3](https://www.gibberlings3.net/), [Beamdog Forums](https://forums.beamdog.com/), [Spellhold Studios](https://www.shsforums.net/), [Weaselmods](https://www.weaselmods.net/), [Artisan's Corner](https://artisans-corner.com/), and [Pocket Plane Group](https://www.pocketplane.net/).

## Credits

- **Install order guide**: [install-EET-4.txt](https://www.scribd.com/document/777087788/install-EET-4) — the most comprehensive EET install order with 9,380 lines of component entries and compatibility notes
- **EET Mod Install Order Guide**: [Google Sheets](https://docs.google.com/spreadsheets/d/1tt4f-rKqkbk8ds694eJ1YcOjraZ2pISkkobqZ5yRcvI/edit?gid=676921267#gid=676921267) — the community-maintained spreadsheet that inspired this project and provided mod-level metadata
- **Infinity Insanity**: Endarire (Greg Campbell) — the [Infinity Insanity Guide](https://docs.google.com/document/d/1hy38KD0bS2qJCaOeWz0F-50z7GkZcCH7QWjDsheKPrA/edit) (Unreleased) provided WeiDU logs, conflict data, and mod URLs that contributed 170+ mod entries to the catalog, plus install order notes for 167 mods
- **EE-Mod-Setup**: [bujiasbitwise-contributions](https://github.com/bujiasbitwise-contributions/EE-Mod-Setup) — component-level conflict and dependency data from the EET Game.ini configuration
- **EET**: [K4thos](https://github.com/Gibberlings3/EET) and the Gibberlings Three community
- **mod_installer**: [dark0dave](https://github.com/dark0dave/mod_installer) — open source WeiDU log-based installer
- **Mod authors**: The hundreds of people who build and maintain BG mods across Gibberlings3, Spellhold Studios, Weaselmods, Artisan's Corner, Pocket Plane Group, and beyond

## Changelog

### v4.1.0 (2026-04-21)
- **Install target multi-game UI** — New dropdown at the top of the sidebar lets users pick which Infinity Engine install this config targets (EET, BG:EE, BG2:EE, IWD:EE, PST:EE, or "All Enhanced Editions (advanced)"). No silent default — a gold "CHOOSE" chip marks it until the user picks; once chosen, the filter hides classic-only mods, surfaces compatibility badges on mod headers and per-component rows, warns when selected components can't install on the target (red `!` badge + incompatible-selection banner with "Clear incompatible"), dims preset/community builds that don't fit, and pops a pre-export modal with three paths (Cancel / Export as-is / Strip and export) so WeiDU never sees components it would just skip. Essentials filter by target too (IWD:EE hides the EET toolchain). State persists in `localStorage.emf_installTarget`. New module-scope helpers: `INSTALL_TARGETS`, `CLASSIC_TOKENS`, `normGames`, `compInstallableOn`, `modHasAnyInstallable`, `isClassicOnly`, `presetCompatible`
- **Subcomponent hierarchy rendering (`scn` / `grn`)** — Expanded mod cards now surface WeiDU's SUBCOMPONENT and GROUP structure. The "Choose One" mutex label reads the real scanner-resolved name ("Tougher Giants — Choose One", "Static PsT Character Portraits — Choose One") instead of a prefix heuristic; the heuristic is preserved as fallback for the ~211 mods whose tp2 wasn't in the Extracted bundle. Cyan uppercase section headers (`grn`) group subcomponents above them ("Enemy Improvements", "Update Existing Encounters"). Duplicate `grn` headers from tp2 authoring artifacts suppressed (WeiDU collates them at install time, we do too). Each scn group carries an optional engine-restriction badge ("PSTEE only", "EET/BG2EE only") via `scnGroupGames`, which intersects sibling `games` arrays and reports only when the restriction narrows the EE target set. Resolves the forum complaint about Tactics Remix showing 8+ identical "Double/Default HP" pairs with no enemy context and cdtweaks cn=270/271 sitting under a generic "CHOOSE ONE"
- **Project Infinity CSV import** — Drag-and-drop a PI-format `weidu-log.csv` into the existing WeiDU.log drop zone. Auto-detects format via header sniffing; description-based matching with exact LABEL match first, then startsWith-unique fuzzy fallback; mojibake recovery (`latin-1 → utf-8` re-decode) for double-encoded names. Fuzzy-matched rows surface in the import result with an expandable "review recommended" breakdown so users can verify before trusting the match
- **Category ↔ install-phase clarity** — Filtering by a sidebar category (e.g. "Pre-Tactical Tweaks") now renders a flat mod list with a sticky caption ("# Pre-Tactical Tweaks — 42 mods tagged with this category") instead of the previous cross-section grouping that could show the same mod under two install-phase headers. Each card in the flat view carries a small gold `↪ {phase}` chip showing the mod's primary install phase, so when filtering "Post-Tactical Tweaks" users can see at a glance which cards are *actually* post-tactical vs. which only also-tag that category. Sidebar category names gain a dim-gold `#` prefix (aria-hidden) to read as tags rather than install-phase sections
- **Pristine-release cleanup** — Keyboard a11y generalized across card types via a `clickableProps` helper (Spell / Kit / Item / Portrait); filter pills unified into a `<Pill>` component with `:focus-visible` ring; Spells and Kits filter state now persists in localStorage matching Items/Portraits; `<PanelBoundary>` wraps every top-level tab so a single bad mod entry no longer takes the whole app down (Planner keeps its existing boundary); narrow-viewport tooltip CSS caps `max-width` to `calc(100vw - 24px)` below 400px
- **Config externalization** — Tooltip content extracted to `data/config.json::ui.tips`; item type colors (49) and Unicode glyphs (49) lifted from hardcoded maps into `config.json::itemColors` / `itemGlyphs` with code-level fallbacks; scattered URL constants consolidated to `config.json::urls`
- **Virtual list scroll anchor fix** — Clicking a component inside a long expanded mod (Tweaks Anthology) no longer snaps scrollTop back to the mod's top. Root cause was the expand-anchor `useLayoutEffect` firing on every `tops` change (each `measuredH` update from the click re-render re-applied the anchor). Fix: one-shot on `expId` change, clear the anchor after apply
- **Portrait picker modal portalization** — Character Planner's portrait selector was trapped by `.planner-left`'s `position:sticky; overflow-y:auto` (which creates a containing block for `position:fixed`). Modal now renders via `ReactDOM.createPortal(..., document.body)` so the backdrop escapes the sticky container and covers the full viewport
- **Data layer: `games` field** — New optional per-component field tagging which Infinity Engine variants each component targets. Derived from tp2 `REQUIRE_PREDICATE GAME_IS` (and both `NOT GAME_IS` and `!GAME_IS` exclamation-form, expanded to the positive complement) via `scripts/scan_game_targets.py`; 2,500+ components across 290+ mods tagged after v2 regex caught additional `!GAME_IS` cases v1 missed. Mod-level `games` is the component union; new `coGames` parallel array in `mods-index.json`. Omitted = universal. Whitelist covers the EE family (`eet bgee bg2ee iwdee pstee sod`) plus classic engines (`bgt tutu ca iwd_in_bg2 how totlm` etc.); 200+ components are classic-only. `--only <stem>` flag for single-mod rescan. Pre-commit hook auto-populates on staged edits. Handoff doc: [`docs/GAMES_FIELD_HANDOFF.md`](docs/GAMES_FIELD_HANDOFF.md)
- **Data layer: subcomponent scanner** — `scripts/scan_subcomponents.py` extracts WeiDU `SUBCOMPONENT @ref` / `GROUP @ref` directives per BEGIN block, resolves `@ref`s via the TRA loader (shared with `scan_game_targets.py`), and populates `scn` / `grn` fields. Idempotent, fill-empty-only (never overwrites existing values), strictly additive. Pre-commit hook runs both scanners on staged mod edits. 2,000+ components gained `scn` across 200+ mods; 2,400+ gained `grn` across 60+ mods. Handoff doc: [`docs/SUBCOMPONENT_HANDOFF.md`](docs/SUBCOMPONENT_HANDOFF.md)
- **Schema versioning (`sv` field)** — New required field tagged on every mod detail file as its second property (after `i`). Anchors v1 semantics (`dep` as string-reason, `gone:true` for removed components mutually exclusive with `dep`, `tp2n` for drift detection, preset key format `modId-cn`, `wf` cross-contamination rule). Migration scaffold at `scripts/migrations/` with conventions for future bumps. Validator errors on missing/unknown `sv`. Full schema doc: [README § "Schema versioning"](#schema-versioning)
- **tp2n backfill** — `scripts/tp2n_backfill.py` populated 2,400+ components across 300+ mods from canonical v18 tp2 parser output. Strictly additive (never overwrites), idempotent, defends against `\ufffd` Unicode replacement characters from non-UTF-8 TRA files (a handful of components intentionally left empty: Polish/German/Korean TRAs that can't be cleanly decoded). Paired with `scripts/tp2n_backfill_dryrun.py` classifier (NEW/MATCH/DIFF/ORPHAN/NOTP2) and `scripts/tp2n_sample_inspect.py` for byte-level verification. tp2n coverage jumped from ~45% to ~80% of components
- **`audit_tp2_drift.py` parser hardening** — LANGUAGE priority fix (previously grabbed whichever language was declared first — LivingClara's Chinese-first LANGUAGE block was polluting English display names). Now prefers `setup.tra` / `setup-<wf>.tra` / `<wf>.tra` in that order, then alphabetical fallback. Block comment stripping, heredoc handling, multi-line BEGIN tolerance, LANGUAGE-declared tra priority. Zero drift vs v18 tp2 baseline across 600+ scannable mods
- **Validator v2** — Distinguishes **true duplicate wc** (same cn + same name + same pi → data bug) from **SUBCOMPONENT siblings** (same wc, different cn/name/pi → legitimate WeiDU FORCED_SUBCOMPONENT pattern). Legitimate sibling groups de-noised (keldorn_rom, proficiency, d2-party-adder). Also checks: `games` whitelist tokens, empty games array, games shape; `scn`/`grn` shape (non-empty strings, <200 chars); `sv` presence + known version; preset key format `modId-cn` with gone-component warning. Zero errors / zero warnings baseline
- **wc-dupe + preset-gone cleanup** — Fixed real data bugs: zstweaks co[253]/co[254] identical-duplicate pair (kept cat-override version), selphiratweaks co[11]/co[12] same, jtweaks co[19/20]/co[68/69] near-duplicate pairs collapsed, cdtweaks co[120] wc typo (2240→2280) + downstream co[118] typo (2280→2270). Removed stale references from Veteran's Challenge preset (Transitions components marked `gone:true` that the preset still pointed at)
- **Preset audit script** — `scripts/audit_presets.py`, report-only (exit 0 always, never modifies data). Detectors: invalid_mod_id, cn_not_in_mod, unparseable_keys (errors); points_to_gone, duplicate_keys (warnings); points_to_dep, suspicious_format (idx-vs-cn confusion heuristic), missing_essentials (info). JSON output via `--json` for tooling integration
- **Install-log-driven `ki` entries** — 10+ new per-mod known-issue entries + a global pattern in `data/known_issues.json` from an active install's debug output. Covers: **SFO/SFO2E `ALTER_SCRIPT.TPH` line 548 GLR parse error** (WeiDU 25201 regression affecting iwdification, mih_fr, mih_sp); dw_talents `ohtempus` class-compat with Tempus; EET_Tweaks Higher-Framerates-Support and Import-Party-Items BCS parse failures; SubtleD Cantrips cn:62 RH#ADR25.CRE patching conflict with Rogue Rebalancing + benign UI.MENU "pattern not found" warnings; ee_cosmetic_enhancements "no effects altered on X.itm" info entries
- **Tethyr Forest Patch install-order rework** — Mod relocated from RESTORATIONS ord=160 → QUEST MODS BG2 ord=710 per the mod's own readme ("Install Setup-TethyrForestPatch after you have installed CtB and TS-BP"). New `orderOnly: true, after: true` conflict entries pointing at CtB (i=505), Tortured Souls Lite (i=579), Tashia NPC (i=500) with readme citations. Reciprocal `before: true` conflicts added on all three target mods. Previous placement silently no-op'd TFP on any normal install order
- **Klatu Content Changes install order** — Most sibling components in the "Content Changes" group were missing the `cat: "SPELL MODS"` override that one component already had. Matched the existing convention so all Content Changes now install in SPELL MODS (before PRE-TACTICAL TWEAKS where cdtweaks lives), honoring Klatu's readme directive: "Components from Content Changes, as well as the Streamlined Spell Progression Tables, should be installed prior to other tweak, fix and rule collections"
- **Tactics Remix per-component split** — Components tagged `grn: "Add New Encounters"` now carry `cat: "PRE-TACTICAL TWEAKS"` override so they install BEFORE SCS; remaining components (Update Existing Encounters, Enemy Improvements, Spell and Item Changes, Cosmetic) stay in TACTICAL MODS per morpheus562's readme: "New encounters should be installed prior to SCS while updates to existing encounters should be installed after SCS." SCS↔TR conflict severity upgraded `partial` → `hard` (reciprocally on both mods) with revised reasoning reflecting forum feedback about TR v3.0+ being a comprehensive difficulty overhaul that substantially duplicates SCS's AI/encounter layer. New info-level `ki` entry framing the either-or tradeoff for users
- **Auto-compute `mod.cats` in index builder** — Previously hand-maintained in detail files; most multi-category mods had correct `cats` arrays only because someone remembered to update. TR and others silently stayed single-category in the index despite having per-component `cat` overrides. Both `scripts/lib/mods-io.js` and `scripts/build_index.py` now auto-derive `entry.cats = unique({mod.c} ∪ {co[].cat})` at index-build time. Stale/missing `cats` can no longer drift from the source of truth
- **Pre-commit hook orchestration** — Hook now runs in order: (1) populate `games` field on staged mods via `scan_game_targets.py --only <stem>`, (2) populate `scn`/`grn` via `scan_subcomponents.py --only <stem>`, (3) rebuild `mods-index.json`, (4) run full `validate_mods.js`, (5) run drift scan if any staged mod has a `tp2n` field. Any failure aborts the commit. Single-mod `--only` keeps commits fast
- **New mod: Jarl's BGT Tweak Pack** — 50+ components, NPC CUSTOMIZATION. Fully hydrated: `games`, `scn`, `grn`, `tp2n`, `langs` (de/en/ru with German primary), author attribution, phase tags, per-component install notes for BGT-only / BGT+EET-only / German-only components. Zero drift on add

### v4.0.0 (2026-04-08)
- **Character Planner** — New tab with a full interactive character sheet. Pick race, class/kit, set ability scores, and drag the level slider 1–40. 27 vanilla kit ability definitions with computed passive bonuses, activated abilities, and kit immunities. 11 equipment slots with searchable item dropdowns (2,716 items filtered by slot type and class restrictions). Combat stats (THAC0, AC, saves, HP, APR) aggregate equipment, proficiency pips, and kit bonuses with annotated breakdowns. Interactive proficiency allocation, specialist mage opposition school dimming, spell slot calculations with WIS/specialist bonuses. Supports single class, multiclass, and dual-class. New `data/chargen.json` and mod detail fields: `prof` (proficiency overrides), `kitAbilities` (kit abilities for the planner)
- **Full kitAbilities rollout** — 694 mod kits across 52 mods + 27 vanilla kits carry structured `kitAbilities` data (93.2% research-backed). Eight fields: `canDual`, `allowedMulticlass`, `canDualTo`, `hlaPool`, `spellRestrictions`, `statBonus`, `resistBonus`, `npcOnly`. Sphere systems tagged for F&P (92 kits), Deities of Faerun (54), Divine Remix (27), Talents of Faerun (21)
- **UI consolidation** — 9 tabs reduced to 6 (Mods, Portraits, Spells/Kits/Items, Character Planner, Community, Resources). Tools, Diagnostics, and Help merged into Resources. Order moved to a resizable footer overlay. Version Tracker split to its own Resources sub-tab
- **Spells, Kits & Items unified** — Combined Overview tab with SPELL.IDS, KIT.IDS, SPLSTATE.IDS engine limits, and item mod tracking plus active mod grids. Shared search bar and action badge row across sub-tabs
- **Redesigned footer** — Stats (mods/comps selected), engine limit indicator, Suggestions/Conflicts/Order overlay buttons with badge counts, version display
- **Conflict system split** — Required dependencies and missing essentials shown as fixed top banners. Conflicts (hard/soft/order/community) in a dedicated footer overlay with type filters. Suggestions in a separate overlay. All three overlays are mutually exclusive
- **Sidebar cleanup** — Meta-filters split into two rows (Selected + Active Only / Cross-Platform + Standalone). Tags collapsed into a single expandable section with grouped categories. App language moved to header dropdown
- **Multi-language UI (i18n)** — Full UI translation framework with `t()` and `tMod()` helpers. German, French, Polish, and Russian translations for 248 UI strings, 817 mod names, 803 mod summaries, and 27 tool descriptions generated via DeepL API. Translation overlay files loaded lazily on language switch with English fallback. Language selector in sidebar and onboarding wizard. In-app feedback button for community translation corrections. `scripts/translate.py` with hash-based caching, manual override protection, and don't-translate term list
- **Data externalization** — FAQ, categories, and app config extracted to `data/faq.json`, `data/categories.json`, and `data/config.json`. 15+ constants (engine limits, badges, mod type icons, kit class colors, wizard data, URLs) loaded from JSON at startup with code-level fallbacks
- **BWS-NG installer** — Big World Setup Next Generation added to Tools and Install Methods as Option C
- **Community telemetry** — Anonymized install reports from Infinity Mod Runner feed a crowdsourced compatibility database. Per-component stability indicators (green/yellow/red dots) and community-reported mod co-failures appear alongside hand-curated conflict data
- **Community builds** — New Community tab for browsing, loading, and merging user-published mod builds. Publish your own via the bottom toolbar — builds are submitted as GitHub Issues and reviewed before appearing
- **Guided build wizard** — 7-step preference-based flow replaces the old preset picker. Asks experience level, content interests, and difficulty preference, then scores all presets and community builds to recommend the best match
- **Telemetry infrastructure** — New [infinity-mod-telemetry](https://github.com/Anprionsa/infinity-mod-telemetry) repo with weekly GitHub Action aggregation pipeline. Fully transparent — all data is public GitHub Issues
- **Diagnostics sharing** — "Share on GitHub" button in the diagnostics tab submits anonymized error pattern data to the telemetry repo
- **Runner integration** — Install report generation, save-to-disk, and opt-in GitHub sharing added to Infinity Mod Runner's post-install summary
- **Item catalog** — New Items sub-tab with 2,716 vanilla BG2:EE items and 3,560 inventory icons extracted from BAM files. Seven category tabs (Weapons, Ranged, Armor, Accessories, Consumables, Miscellaneous, Internal) with clickable type filter pills and 4 sort modes. 37 item mods populated with `items`/`it`/`itC` fields via `scan_item_mods.js` and `populate_items.js`. New `coIT`/`coITC` index fields for item counts. Mod-added items show ADDED badges with mod attribution links. Overview tab displays item mod contributions alongside spells, kits, and SPLSTATE
- **Item card rendering** — Per-card stat badges show `THAC0+N`, `dmg+N`, `AC+N`, speed factor, 2H indicators, charges, class-restriction locks, and special-effect icons (immunities, resistances, regen, free-action, spell slots). Clean card names strip `+N` and ` AC N` suffixes (full text preserved in the modal). `<CHARNAME>`/`<PRO_HIMHER>` template tokens replaced with readable words in names and descriptions. `[Faulty]`-style bracket prefixes become a red badge on the type row. Descriptions truncate to 3 lines on cards via CSS `line-clamp` and show full text in the detail modal. Type-specific Unicode glyph fallback (⚔ 🛡 💍 🔨 …) renders when a BAM icon is missing or broken
- **Item detail modal** — Click any card to open a full-screen detail view with icon, name, type chip, reference code, price, weight, stats grid, grouped special abilities (Immunities / Resistances / Abilities / Regen / Extra spell slots), usability requirements, charge counts, full description, variants list (grouped by weapon type with per-variant source labels), and clickable mod attribution with go-to-mod navigation
- **Variant grouping** — Same-name + same-type items collapse into one card with a variants list. Enchantment ladders (`Aster's Edge +3/+4/+5`), AC ladders (`Bracers of Defense AC 8/7/5/4/3`), and mid-name enchantments (`Long Sword +3 'Purifier'`) all normalize to the same base name. Cross-source clones (vanilla `SW1H40` + modded `CMTSW10` both "Blade of Roses +3") merge into a single card with a `TWEAKED` action badge and both refs in the variants list. Primary variant picker prefers vanilla, then highest enchantment, then strongest AC
- **Creature & engine-item filtering** — Automated Internal-tab detection catches: items named "Attack" / "Claw Attack" / "Bite Attack" (163 vanilla creature strikes), dialogue-name misrouted strrefs (`?`, `!`, `. `, trailing `.` >15 chars, or >40 chars total), impossible stats (`dmgBonus > 50`, `thac0 == 32767` sentinel, `price > 1,000,000` cheat pricing), empty-shell items (no description AND no AC attribution), and companion-locked plot items (Hexxat's Amulet). Mirror rules applied to mod-added items at render time. 492 vanilla items + several hundred mod items filed under Internal, keeping the main tabs free of creature inventory data
- **Mod item hydration pipeline** — `enrich_item_data.py` now resolves names and descriptions for **97% of mod items** (from ~15% coverage in the initial draft). New resolution paths: `SAY DESC` / `SAY IDENTIFIED_DESC` / `SAY UNIDENTIFIED_DESC` patterns in `tp2/tph/tpa` files, per-item TRA files (`<resref>.tra` with `@0`/`@1`/`@10`/`@11` convention used by Wares of the Planes), `COPY_EXISTING` vanilla-source inheritance (DGITEMS, ruad), and vanilla `dialog.tlk` strref resolution for mods that ship pre-built `.itm` files with baked-in strrefs (Derats_Todd, Rolles, k0_iskp). UTF-8 decoding fixes (was reading TRAs as cp1252 on Windows) + double-encoding recovery (`latin-1 → utf-8` re-decode for mod-authored bugs like `FaerÃ»n` → `Faerûn`)
- **Scanner expansion** — `scan_item_mods.js` now substitutes `OUTER_SPRINT` variables when resolving `COPY ~%itm_resref%.itm~` patterns, letting us detect item files in mods that build paths dynamically. Wares of the Planes went from 4 → 115 items detected. `populate_items.js` gained a `--resync` flag for rebuilding existing `items.new` arrays when a fresh scan finds more items than the current state
- **Item icon fixes** — URL-encoding `#` in icon paths so mod items with resrefs like `CU#2H001` load correctly (browser was truncating at the fragment delimiter). Extraction pipeline now handles both vanilla BIFs and mod override directories; 2,166 icons extracted across 36 mods
- **Spell schema expansion** — All 301 vanilla spells now carry 9 new per-spell fields (`sph`, `cls`, `sv`, `ct`, `rng`, `aoe`, `dur`, `scr`, `si`) populated from authoritative SPL byte extraction. New `data/spell-tables.json` with BG2 sphere list, class level caps, scribe INT thresholds, sorcerer/bard pick tables. Character Planner deity filter reads per-spell `sph` directly (previously keyed by display name). Tooltips + Spells-tab cards show real casting time, range, save type, and duration. New scripts: `extract_vanilla_spells_spl.py` (BG2:EE backup → spell metadata), `extract_installed_mod_spells.py` (installed game override/ + TLK → real mod spell names + icons), `extract_mod_spell_icons.py` (mod source dir → icons only). First real-data rollout on Faiths and Powers: 1,281 D5 icons extracted, placeholder `YOURFNP01-05` entries replaced with real F&P spells
- **Data files** — New `data/items-vanilla.json` (2,716 items), `items/icons/` (3,560 PNGs). New extraction scripts: `extract_vanilla_items.py` (BIF/KEY/TLK parser), `extract_item_icons.py` (BAM→PNG for vanilla), `extract_mod_item_icons.py` (BAM→PNG from mod sources with COPY dest→src fallback), `populate_item_stats.py` / `populate_item_specials.py` / `populate_item_metadata.py` (vanilla `.itm` binary parsing for stats/specials/twoHanded/profType/usability/charges), `populate_mod_item_stats.py` / `populate_mod_item_specials.py` / `populate_mod_item_metadata.py` (mod-side equivalents), `apply_item_overrides.py` (idempotent patch + internal-item auto-detection)
- **Single source of truth** — Per-mod detail files are now the sole authority for all mod data. Five standalone data files (`recommendations.json`, `compat.json`, `github_mods.json`, `pi_weidu_map.json`, `portrait_extraction_results.json`) eliminated. Their data migrated into per-mod fields: `rec` (recommendations), `eet_compat` (EET compatibility), `gh` (GitHub repo identifiers). Index-only fields (`u`, `a`, `v`, `sum`, `tags`, `ph`, `ios`) moved into detail files. `mods-index.json` is now a pure build artifact rebuilt on commit. `version_cache.json` retained as the authority for dynamic API data (stars, push dates, releases), merged with static `gh` fields at runtime. New `scripts/scan_versions.py` and `scripts/scrape_weaselmods.py` replace missing `tools/` scripts. Contributing workflow simplified: edit one file, commit, done
- **Character Planner polish pass** — Rich equipment tooltips (name, mod attribution, enchantment, stat breakdown, usability). Weapon proficiency mod-replacement handling: when cdtweaks or CSP replaces the prof list, the planner shows attribution banners, ×N count chips with "Merged from" tooltips, and loadout-aware routing for combat bonuses. Divine sphere coverage refined: 57 vanilla priest spells gained secondary AD&D 2e spheres; mod-added priest spell sphere tagging via `scripts/tag_mod_spell_spheres.py` (254/255 tagged, 99.6%). Tooltip anchor and reload-persistence fixes
- **Panel standardization + Portrait refresh** — Spells, Kits, Items, and Portraits panels now share a single set of components (`ActiveModLine`, `CardFooter`, `EmptyGrid`, `RefChip`, `Tip`, `splitModEntries`) and layout classes (`.spell-card`, `.spell-grid`, `.spell-panel`, `.mo`/`.md` modals). Portrait panel rebuilt: fixed-width cards with action bars, per-phase tabs on NPCs whose portrait varies across BG1/SoD/BG2/ToB, phase-breakdown pills, Affected/Conflicts toggles with rich Tip tooltips, localStorage-persisted filters, and a standardized detail modal showing per-phase portrait comparison with winner/ACTIVE highlighting. Tooltip arrow math fixed to track the anchor when the tooltip box clamps to a viewport edge; arrow colors themed via CSS vars. Keyboard accessibility added to portrait cards, phase tabs, and player-portrait thumbnails (`role`, `tabIndex`, `aria-label`, `aria-selected`, Enter/Space activation). Overview tab gained rich hover tooltips with per-mod component lists and type breakdowns for Spell/Kit/Item mod cards

Earlier releases (v3.9.0 through v1.0.0) are in [CHANGELOG.md](CHANGELOG.md).

## License

MIT
