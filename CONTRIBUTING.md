# Contributing Mod Metadata to Infinity Mod Forge

> **Note:** Renamed from EET Mod Forge to Infinity Mod Forge as of v4.0.0. The EET *mod* (EET.tp2) is unrelated to this rename.

Infinity Mod Forge tracks 800+ mods with component details, compatibility info, and install order guidance. Mod authors can help keep their entries accurate by including a `mod-forge.json` file in their mod repository.

## Quick Start

1. **Generate a scaffold** from your tp2:
   ```bash
   python scripts/tp2_to_modjson.py path/to/setup-mymod.tp2 -o mod-forge.json
   ```
2. **Fill in the blanks** — the scaffold pre-populates components and languages from your tp2. You add the summary, tags, and any known issues.
3. **Commit `mod-forge.json`** to the root of your mod repository.

That's it. The Mod Forge maintainers periodically scan GitHub repos for this file and merge updates.

## The `mod-forge.json` Format

Add this to the root of your mod repo. VS Code and other editors will provide autocompletion if you include the `$schema` line.

### Minimal Example

```json
{
  "$schema": "https://raw.githubusercontent.com/Anprionsa/infinity-mod-forge/main/schemas/mod-forge.schema.json",
  "tp2": "MyMod",
  "name": "My Cool Mod",
  "author": "YourName",
  "version": "2.0",
  "homepage": "https://github.com/you/mymod/releases",
  "summary": "Adds three new quests and a joinable NPC to SoA.",
  "games": ["SoA", "ToB"],
  "tags": ["quest", "npc"],
  "languages": {
    "en": 0,
    "fr": 1,
    "de": 2
  },
  "components": [
    { "name": "Main component", "number": 0 },
    { "name": "Optional portraits", "number": 10 }
  ]
}
```

### Full Example (with conflicts, known issues)

```json
{
  "$schema": "https://raw.githubusercontent.com/Anprionsa/infinity-mod-forge/main/schemas/mod-forge.schema.json",
  "tp2": "MyMod",
  "name": "My Cool Mod",
  "author": "YourName",
  "version": "2.0",
  "homepage": "https://github.com/you/mymod/releases",
  "summary": "Adds three new quests and a joinable NPC to SoA.",
  "games": ["SoA", "ToB"],
  "tags": ["quest", "npc"],
  "languages": {
    "en": 0,
    "fr": 1,
    "de": 2
  },
  "components": [
    {
      "name": "Main component",
      "number": 0,
      "label": "mymod_main",
      "kits": 0,
      "spells": 2,
      "items": 5
    },
    {
      "name": "Optional portraits",
      "number": 10,
      "label": "mymod_portraits",
      "notes": "Requires EET Realistic Portraits Extended for best results."
    },
    {
      "name": "Old crossmod (deprecated)",
      "number": 20,
      "deprecated": true,
      "notes": "Use the built-in crossmod in v2.0+ instead."
    }
  ],
  "conflicts": [
    {
      "mod": "OtherMod",
      "severity": "partial",
      "reason": "Both mods edit BALDUR.BCS with incompatible script blocks.",
      "myComponents": "#0",
      "theirComponents": "#100 #200"
    }
  ],
  "dependencies": [
    {
      "mod": "EET",
      "type": "hard",
      "reason": "Requires EET journal system."
    }
  ],
  "knownIssues": [
    {
      "pattern": "ERROR Installing \\[Main component\\].*cannot open.*mymod_portrait",
      "severity": "warning",
      "description": "Portrait file not found on first install attempt.",
      "workaround": "Re-run the installer; the file is created by a pre-install script.",
      "components": [0],
      "forum": "https://forums.example.com/thread/12345"
    }
  ]
}
```

## Field Reference

### Required Fields

| Field | Description |
|-------|-------------|
| `tp2` | Your WeiDU tp2 folder name, case-sensitive (e.g. `"stratagems"`) |
| `name` | Human-readable mod name |
| `author` | Author name(s), comma-separated if multiple |
| `components` | Array of your mod's installable components |

### Optional Metadata

| Field | Description |
|-------|-------------|
| `version` | Current version string |
| `homepage` | URL to releases page or forum thread |
| `summary` | One-sentence description (max ~200 chars) |
| `games` | Game phases: `"BG1"`, `"SoD"`, `"SoA"`, `"ToB"` |
| `tags` | Content tags (see below) |
| `languages` | Map of ISO language code to WeiDU LANGUAGE index |
| `conflicts` | Known incompatibilities with other mods |
| `dependencies` | Required or recommended prerequisite mods |
| `knownIssues` | Known installation errors with workarounds |

### Available Tags

`qol` `restore` `story` `class` `visual` `quest` `npc` `tweak` `tactical` `item` `spell` `portrait` `sound` `ui` `fix` `kit` `rule` `encounter` `romance`

### Component Fields

Each component needs at minimum `name` and `number`:

| Field | Description |
|-------|-------------|
| `name` | Display name (as shown by WeiDU) |
| `number` | DESIGNATED number (or auto-numbered position) |
| `group` | SUBCOMPONENT group name (for mutually exclusive choices) |
| `label` | WeiDU LABEL identifier |
| `deprecated` | Set `true` if no longer recommended |
| `removed` | Set `true` if removed from tp2 (kept for compat tracking) |
| `notes` | Installation caveats or special instructions |
| `kits` | Number of ADD_KIT calls (for engine kit-cap tracking) |
| `spells` | Number of new SPELL.IDS entries |
| `splstates` | Number of new SPLSTATE.IDS entries |
| `items` | Number of new items added |

### What You Don't Need to Provide

The following fields are curated by Mod Forge maintainers and will **not** be overwritten by your `mod-forge.json`:

- **Install order** (`c`, `ord`) — category and position in the install guide
- **Sub-option structure** (`x`) — parent/child component relationships in the UI
- **Internal IDs** (`i`) — unique database IDs
- **Split groups** (`sg`) — cross-category component grouping

## Engine Resource Tracking

If your mod adds kits, spells, or uses SPLSTATE.IDS, please include the counts. The IE engine has hard limits:

- **ADD_KIT**: 320 total across all mods
- **SPELL.IDS**: ~256 entries per spell level
- **SPLSTATE.IDS**: 256 entries total

Infinity Mod Forge uses these counts to warn users when they're approaching engine limits.

## How Merging Works

When we import your `mod-forge.json`:

1. If your mod is already in the database, we **merge** your data — updating names, versions, languages, and adding new components. Curated fields (install order, sub-option structure) are preserved.
2. If your mod is new, we create a stub entry marked `UNCATEGORIZED` for manual review. A maintainer will assign the correct category and install position.
3. Conflicts and known issues are merged additively — your entries supplement existing data.

## Generating from Your TP2

The scaffold generator reads your tp2 and pre-fills components and languages:

```bash
# Print to stdout
python scripts/tp2_to_modjson.py setup-mymod.tp2

# Write to file
python scripts/tp2_to_modjson.py setup-mymod.tp2 -o mod-forge.json
```

Review the output and fill in `name`, `author`, `summary`, `tags`, and `games` before committing.

## Questions?

Open an issue at [github.com/Anprionsa/infinity-mod-forge](https://github.com/Anprionsa/infinity-mod-forge/issues).
