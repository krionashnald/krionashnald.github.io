# Schema migrations

Each mod JSON file carries an `sv` (schema version) field. Current version: **1**.

This directory holds migration scripts that upgrade mod files from version `N` to `N+1`. See the main README's "Schema versioning" section for what v1 defines and when to bump.

## Conventions

- File name: `v<N>_to_v<N+1>.py` (e.g., `v1_to_v2.py`).
- Idempotent: running twice must produce the same result as running once.
- Additive where possible: prefer adding new fields over mutating existing ones.
- Read/write through `scripts/lib/mods-io.js` (or equivalent Python) so the index rebuild step stays consistent.
- After migration: rerun `scripts/build_index.py --write` and `node scripts/validate_mods.js`.

## Current migrations

None yet. The first schema bump will live here as `v1_to_v2.py`.

## Pre-v1 → v1

For historical context — this was applied manually (not via a script in this directory):

- `sv: 1` added as the second field of every mod file.
- `dep` finalized as a **string reason** (not boolean). Truthy means author-discouraged but still installable.
- `gone: true` finalized for fully-removed components (kept in DB for conflict-system validation only).
- `dep` and `gone` declared mutually exclusive. Validator enforces this.
- `tp2n` field introduced for drift detection against the canonical v18 tp2.
