# Changelog Archive

Older release notes for Infinity Mod Forge (formerly EET Mod Forge). The current release is documented in the [README](README.md#changelog).

### v3.9.0 (2026-04-07)
- **Kits tab** — New browsable kit system mirroring the Spells tab. 37 vanilla kits + 616 mod-added kits across 49 mods, all with names, classes, and descriptions. Organized by 14 class subtabs: Fighter, Ranger, Paladin, Cleric, Druid, Thief, Bard, Mage, Sorcerer, Monk, Shaman, Multi-class, and Non-Player
- **Kit Cap moved to Kits tab** — Kit Cap progress bar (320 engine limit) relocated from Diagnostics to the Kits overview, alongside per-class breakdowns and active kit mod cards
- **Class overhauls** — Kits overview tracks mods that modify base classes (not just add kits), with conflict detection when multiple mods overhaul the same class
- **Kit modification tracking** — 21 vanilla kit modifications tracked (TWEAKED/REPLACED) across Bardic Wonders, Might & Guile, Sword and Fist, Talents of Faerun, Faiths and Powers, and Song and Silence
- **Card action bars** — Replaced floating corner badges with full-width colored top bars on spell and kit cards. Action types: ADDED (green), MODIFIED (blue), REPLACED (purple), TWEAKED (gold), REMOVED (red), VANILLA (gray). Consistent across Spells and Kits tabs
- **Kit data enrichment** — Real kit names extracted from tp2/tra source files for Talents of Faerun (120 kits), Deities of Faerun (69), Faiths and Powers (96), Morpheus562 (33), Might & Guile (28), Divine Remix (32), Monastic Orders (19), Song and Silence (9), Eldritch Magic (10), I Hate Undead (11), D2 Workshop Kits (23), and more. 100% description coverage
- **Non-Player kits** — Dedicated subtab for NPC companion kits, creature kits, and internal mod kits. Two-line card display: kit name + NPC name subtitle
- **Prefix Registry** — New Help subtab with a searchable, sortable, filterable table of WeiDU file prefixes loaded from `data/prefix-registry.json`. Filter tabs: All, Conflicts, Project, Personal. Cross-references prefixes to mods in the database. New `pfx` field on mod detail files
- **Multi-language export support** — Export modal now includes an Install Language selector with 15 languages. The exported WeiDU.log uses the correct per-mod `#lang` index. Language choice persists across sessions
- **Language data for 351 mods** — New `langs` field maps ISO language codes to WeiDU LANGUAGE indices per mod, auto-populated via `scripts/populate_langs.py`
- **196 new mods** — Major catalog expansion from SHS, PPG, Beamdog, and community sources
- **12 new mods** — Edwin Bromance, A Party to Die For, Arcane Archetypes, BuffBot, The Pursuit of Justice, Edwina Dialogue Tweaks, M'Khiin for BG2EE, Reflection, Golden Horse Mercenary Company, and 3 existing mods updated
- **Missing components restored** — Crucible (was phantom cn:0, now correct cn:1/3/4), EE Cosmetic Enhancements (7→23 components), BG1 NPC in SoA (23→30 components), Of Paths and Ways (+Decay Overseer cn:10), Iylos NPC (+4 timer components), Kiara Zaiya (+5 components)
- **Expandable import results** — "... and more" in WeiDU.log import results is now clickable, expanding to show the full uncatalogued mod list with a collapse toggle
- **15 acronym renames** — EMAD → Every Mod and Dog, II → Infinity Innovations:, BP → Bonus Pack in Baldur's Gate, BS → Balduran's Seatower, etc.
- **Known issues (ki)** — Added ki entries for Animal Companions (DestroySelf parse error + ACTION_READLN blocking) and Thalantyr Item Upgrade (TRA reload after charset conversion)
- **Conflict audit** — New bidirectional conflicts: EdwinBromance ↔ Edwin Romance, lfgp ↔ TPoJ, Deepgnomes ↔ Aurora's Shoes and Boots. IWD EET Integration updated for HoW_EET compatibility
- **Mod cleanup** — Errant Justice marked abandoned, An Unusual Wish renamed from French, Detailed Description moved to EET Finalization with English translations, BuffBot moved to INTERFACE with EEex dependency, duplicate Aura catalog entry removed
- **Portrait expansion** — 106 new portrait directories added, 15 legacy portraits removed
- **11 new tools** — A7-TextureConvert, DLC Builder, Mirror Game Maps, Stutter Debug Tool, BG2 Radar Overlay, Moebius Toolkit, Portrait Grabber, IE-EE Configuration, Post Infinity, Bidules pour moddeurs, EETLauncher
- **Data files** — New `data/kits-vanilla.json` (37 vanilla kits), `data/classes-vanilla.json` (12 base classes), `data/prefix-registry.json`. `coKC` field added to index for per-component kit class breakdowns
- **Code cleanup** — Extracted `LIMITS` constant for engine caps, `VANILLA_SPELLS` baseline, shared `renderActionBadge()`, lifted `catMap` memo to AppInner
- 804 mods, 6,400+ components, 1,069 conflicts, 120 dependencies, 11 presets

### v3.7.0 (2026-04-05)
- **Spells tab overhaul** — Spell.IDS tracking merged from Diagnostics into Spells tab. Per-level breakdown, conflict detection, and mod contributor views integrated into spell browsing
- **Diagnostics tab cleanup** — Spell.IDS section removed (merged into Spells). Focused on WSETUP.DEBUG analysis, SPLSTATE.IDS, and ADD_KIT tracking
- **Help system rewrite** — Complete overhaul with 7 tabbed sections: Quick Start, Install Methods, Using the App, Tabs Guide, Badges & Status, Troubleshooting, and Resources. Live search across all tabs
- **Conflict database audit** — Full bidirectionality pass: 47 missing reciprocal entries added, 8 severity mismatches reconciled, 3 undocumented conflicts from install testing documented. 1,066 conflict rules across 220+ mods, all bidirectional
- **Known issues expansion** — 21 mods now have `ki` (known issues) entries with regex patterns, severity levels, and workarounds for the debug log analyzer. New entries for EPS (MOSTL02.SPL dependency), Tidings (post-install WeiDU crash), MiH mods (COPY_EXISTING_REGEXP memory), themed_tweaks and A7-MagicStore (BD0120.BCS corruption)
- **Preset cleanup** — Removed 32 impossible/losing components from Mod Forge Ultimate: subcomponent losers (cdtweaks), EET-incompatible components (PaintBG, jtweaks), unmet prerequisites (aTweaks PnP Fiends, jimfix SCS, FAREN Angelo), UI conflicts (eeuitweaks vs LeUI-SoD). Removed cdtweaks cn:250/252 (Colorize NPC Names — corrupts name strrefs in large installs)
- **User-facing documentation** — All component notes rewritten to explain dependencies, conflicts, and game-type restrictions for users. Removed internal test references from all mod JSON files
- **New mods** — 11 new mods added to catalog, various mod metadata updates
- **Build system** — Tooling reorganized from `tools/` to `scripts/`. Pre-commit hook auto-rebuilds mods-index.json via `build_index.py`
- 612 mods, 5,100+ components, 1,066 conflicts, 120 dependencies, 11 presets

### v3.3.0 (2026-04-01)
- **Conflict panel UX overhaul** — Reason text now renders on a second line below mod names for better scannability. Long notes wrap properly instead of causing horizontal scroll.
- **Default visibility** — Only hard and soft/partial conflicts shown by default. Order notes, suggestions, dependencies, and essentials are counted in the header but hidden until the user clicks their filter button.
- **New "order" category** — Install order notes, cosmetic "last installed wins" overlaps, complementary mods, and managed coexistence entries are tagged with `"orderOnly": true` and display as a distinct teal category. ~220 conflict entries reclassified across 50+ mod files. Bottom status bar excludes order-only entries from the conflict warning count.
- **Grouped suggestions** — Suggestions from the same source mod are grouped into one row (e.g., "Faren NPC suggests Tylas NPC, Ninde NPC, Xulaye NPC") with individual "+" buttons per mod and a "+ Add All" button for the group.
- **Per-level SPELL.IDS tracking** — The game has a 50-slot-per-level cap for wizard and priest spells. The Diagnostics SPELL.IDS tab now shows a compact per-level grid (Wizard L1–L9, Priest L1–L7) with current/50 counts, warning colors when approaching the cap, and click-to-expand per-level contributor breakdowns. Engine badge and Diagnostics tab badge updated to detect per-level overflows.
- **spLv data for 20+ mods** — New `spLv` field on components tracks per-level SPELL.IDS consumption. Comprehensive audit of 43 mods that APPEND to SPELL.IDS via tp2/tpa/tph analysis, with manual research for dynamic mods (SCS, FnP, IWDification, MiH, ToF). Incorrect `sp` values fixed across multiple mods.
- **Header redesign** — Left/right split layout, search bar centered and wider, engine badge (green/yellow/red), Diagnostics tab over-cap badges with counter identity colors (SpSt=cyan, SPL=purple, KIT=blue). Progress bars moved to Diagnostics only.
- **New CSS variable** `--cyn` (#67e8f9) and `.alert-order` class for teal styling.
- **New tool** — `tools/scan_spell_ids.js` for extracting SPELL.IDS additions from extracted mod tp2 files.
- **README** — Documented `orderOnly`, `sp`, and `spLv` fields in contributor guide.

### v3.2.0 (2026-03-30)
- **Spell Catalog** — New Spells tab with complete vanilla BG2:EE spell database:
  - 301 vanilla spells cataloged across Wizard (L1-9), Priest (L1-7), Innate, and HLA categories with names, schools, levels, and descriptions
  - 301 spell icons extracted from BG2:EE game files (BAM V1 format with RLE decompression), displayed as 48x48 pixel-art thumbnails in a responsive grid layout
  - Sub-tabs: Overview (badge legend + active spell mod summary), Wizard, Priest, Innate
  - Level selector pills with per-level modification counts
  - Search by spell name, school, or mod name
  - "Affected" filter shows only spells touched by selected mods; "Conflicts" shows all cross-mod spell conflicts across all levels in a single view
- **Spell mod tracking** — Per-mod `spl` field (analogous to `pt` for portraits) tracks spell modifications and additions:
  - 737 spell entries across 21 mods: 471 modifications + 174 new spells (SPELL MODS category) plus 92 new spells from SCS IWD components
  - Action badges: REPLACED (purple, complete overhaul), MODIFIED (blue, significant change), ADDED (green, new spell), TWEAKED (gold, minor adjustment), REMOVED (red, spell disabled)
  - Badges display as corner overlays on spell cards with mod name and change summary inline
  - Conflict detection when 2+ selected mods modify the same vanilla spell
  - New spells merge into the main Wizard/Priest/Innate spell tables at their proper level
- **Mods with spell data**: Spell Revisions (241 modifications), IWDification (85 new), SCS (92 new), MiH Spell Pack (59 new + 6 tweaks), SubtleD's Spell Tweaks (72 tweaks across 58 components), Spell-50 (22 scaling mods), Wild Mage Additions (4), B_Spells (10 new), and 12 additional mods
- **README: spell contribution guide** — New "Adding spell data" section documenting the `spl` field format and tuple conventions

### v3.1.0 (2026-03-30)
- **Portrait data merged into per-mod files** — Replaced the standalone `portraits.json` with per-mod `pt` fields in 101 mod files. NPC definitions (name, game scope, default images) moved to `data/npcs.json`. This completes the per-mod architecture: all mod-specific data now lives in individual files
- **Portrait resolution bug fix** — Fixed a bug where ~23% of portrait mappings (182 of 801 entries) silently failed. The old code built a reverse index using WeiDU component numbers (`cn` values like 2000) but looked them up by array index. Mods like The Picture Standard, eportraits, and BG1Aerie were affected. The new design reads portrait data directly by array index, making the mismatch structurally impossible
- **Stale portrait data cleanup** — Identified and removed 127 orphaned portrait entries: 74 from 5 mods no longer in the catalog, 53 from component numbers that don't exist in their mod's component list
- **README: portrait contribution guide** — New "Adding portrait data" section documenting the `pt` field format, `npcs.json` structure, and the three-step process for contributors

### v3.0.1 (2026-03-28)
- Bug fixes, data corrections, and new mods

### v3.0.0 (2026-03-27)
- **Per-mod data architecture** — Replaced monolithic `mods.json` with individual JSON files under `data/mods/` (~595 files). Each file contains the full mod record including components, conflicts, and dependencies. `data/mods-index.json` serves as a lightweight index for the browse list; `data/mods/_catalog.json` maps IDs to filenames for lazy loading on expand
- **Conflicts migrated into per-mod files** — The standalone `conflicts.json` is retired. All 994 conflict rules and 118 dependency rules now live inside their respective mod files, co-located with the data they describe
- **Mod merging** — 45 mods that were previously split into multiple catalog entries sharing the same tp2 are now single entries with per-component category overrides (`cats` array). Key merges: SCS (4 entries to 1), Tweaks Anthology, EET Tweaks, cdtweaks, and others
- **Explicit install order** — Every mod carries an `ord` field. Category subheaders show install context ("after X / before Y"). No more implicit ordering by array position
- **Category reorganization** — "AFTER NEW NPCS" renamed to "NPC EXPANSIONS". New "NPC CROSSMOD" category for crossmod banter/romance content (15+ mods moved). "KIT MODS" renamed to "KIT & CLASS MODS". 22 categories total
- **Version tracker: folder scan** — New "Scan Mod Folder" button (Chrome/Edge) uses the `showDirectoryPicker` API to read your local mod directory and compare installed tp2 VERSION strings against GitHub releases and the `v` field in the mod index. Timestamp-based fallback for stale tp2 VERSION strings. "STALE VERSION" badge for mods where the author never updates the version string. Scan results persist in sessionStorage
- **Deep-dived component notes** — 80+ mods received detailed tp2 analysis with component-level notes covering conflicts, choose-one groups, dependencies, and recommendations
- **Preset audit** — Mod Forge Ultimate preset extensively reviewed: removed EET-incompatible mods, fixed choose-one violations, resolved overlaps between Talents of Faerun, IWDification, and Spell Revisions
- **UI improvements** — Truncated notes with "more..." toggle for long descriptions. Gold border fix on expanded cards. Scroll position anchoring on expand. Search clear button
- **New tools** — `split_mods.js` (split mods.json into per-mod files), `verify_split.js` (verify split integrity), `migrate_conflicts.js` (move conflicts into per-mod files), `scan_versions.js` (GitHub API version scanner), `backfill_github.js` (backfill GitHub repo URLs), `scrape_weaselmods.js` (scrape Weaselmods.net metadata)
- 612 mods across ~612 per-mod files, 5,100+ components, 1,066 conflicts, 120 dependencies, 11 presets, 22 categories

<details><summary><b>Earlier versions (v1.0–v2.1)</b></summary>

### v2.1.0 (2026-03-21)
- **Installation guide** — Step-by-step instructions for Project Infinity, mod_installer, and manual installation
- **WeiDU export fix** — Fixed 489 incorrect `wc=0` values across 53 mods
- **Mod_installer compatibility** — Identified and documented 9 failure modes from live testing
- **Data quality** — Deep research on 8 major mods, 6 SUBCOMPONENT group fixes, 12 cn/wc corrections, 33 conflict scoping improvements

### v2.0.0 (2026-03-19)
- **NPC Portrait Viewer** — New Portraits tab with 3 sub-tabs (124 Companions, 104 Other NPCs, 171 Player Portraits), phase tracking, conflict detection
- **Mod Forge Ultimate preset** — Overhauled mega-install preset (418 mods, 1,867 components)
- **Kit Cap tracking**, **1-OF badge**, collapsible categories, conflict database deep clean
- 629 mods, 476 conflicts, 117 dependencies, 11 presets

### v1.0.0–v1.6.0 (2026-03-09 to 2026-03-15)
- Initial release with 630+ mods and 3,500+ components
- WeiDU.log import/export, five install presets, debug log analyzer, GitHub version checker, EET compatibility badges, conflict detection
- Path quality audit, conflict data expansion (168 rules from EE-Mod-Setup), bulk note enrichment (167 mods from Infinity Insanity guide), cross-platform presets, dead link sweep

</details>
