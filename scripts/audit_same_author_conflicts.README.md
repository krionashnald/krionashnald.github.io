# Same-author conflict audit — 2026-04-21

Automated run of `scripts/audit_same_author_conflicts.py` against
`data/mods/*.json`. Surfaces every `conflicts[]` entry where both the parent
mod and the target mod are attributed to the same `au` (or `a`) handle.

Raw results: `scripts/audit_same_author_conflicts.result.tsv` (62 entries
across 813 mod files).

## Why this matters

Triggered by a 2026-04-21 pushback from morpheus562 on the Stormlord↔EPS
entry (both mods his, framed as a soft conflict through a third mod's cleanup,
zero session evidence). Same-author entries are the most visible and most
embarrassing when wrong — the author is uniquely qualified to call out
fabricated claims about their own work.

## Triage categories

### A. Legitimate hard conflicts (keep, low priority)
Authors shipping mutually-exclusive versions or supersession relationships.
These are documented in the author's own readme/tp2 with FORBID_COMPONENT or
explicit "choose one" language. Keep as `conflicts[]` entries but verify
`severity: "hard"` and add `evidenceLevel: "observed"` with a source citation
pointing to the tp2 FORBID_COMPONENT or readme line.

- `LEUI-BG1EE`/`LeUI`/`LeUI-SoD` — lefreut UI overhaul exclusivity (6 entries)
- `DarkHorizons`/`darkhorizonsbgee` — kova/roxanne legacy vs EE packaging (2)
- `JanQuest`/`JanQuestRemix` — akadis/kasumi supersession (2)
- `ZS_Consumables`/`ZS_WeaponOils` — zed nocear supersession (2)
- `Item_Pack`/`Rolles` — edvin Bag of Holding pick-one (2)
- `c#anotherfinehell`/`c#sodtweaks` — jastey SoD ending mutex, FORBID_COMPONENT enforced (2)

### B. Hard conflicts with author-managed detection (keep, verify)
Author ships mutual detection code (REQUIRE_PREDICATE, FORBID_COMPONENT) and
the conflict is surface-level documentation of what the tp2 already enforces.

- `dw_talents`↔`stratagems` — davidw, 4 entries with FORBID_COMPONENT details
- `Ascension`↔`wheels`/`stratagems` — davidw, managed via FORBID_COMPONENT
- `MESpells`↔`METweaks` — olvynchuru, FORBID_COMPONENT on ranger/paladin progression

### C. Internal component exclusions — DATA BUG, restructure (18 entries)
`cdtweaks.json` has 18 entries with `with: "cdtweaks"` pointing to itself.
These aren't cross-mod conflicts — they're within-mod component redundancies
("Multiple Strongholds makes individual stronghold unlocks redundant", etc.).
Should move out of `conflicts[]` into a new `componentExclusions[]` or similar
schema feature, OR into per-component `notes` fields. Same pattern in
`aTweaks.json` (1 entry: cn:155 requires cn:150/152/153 base).

**Phase 2 action:** schema additions + migration of 19 entries. Do NOT delete
the content — the information is useful, it's just in the wrong array.

### D. Soft speculative, suspect — DEMOTE (candidates for Phase 2 cleanup)
These read like reasoned speculation with no evidence citation. Same pattern
as the Stormlord↔EPS case that started this audit. The content may be valid
advisory, but presenting as `conflicts[]` overstates certainty.

- `ArtisansKitpack`↔`HouseTweaks` — artemius_i, "pick one if using both" ↳ advisory
- `morpheus562-s-kitpack`↔`enhanced-powergaming-scripts` — morpheus562 ✅ **already demoted 2026-04-21**
- `TPoJ`↔`lfgp` — bucketfulofsunshine, "may conflict" ↳ advisory
- `imoen_forever`↔`jtweaks` — jastey, "complementary" (not a conflict at all) ↳ remove or move to `notes`
- `mih_fr`↔`mih_sp` — mulan, "supersede where they overlap" ↳ advisory
- `k0_iskp`↔`sod2bg2_iu` — k4thos, "Reported incompatible by LCC-docs" ↳ advisory with that source citation

### E. Cross-mod but marginal — review individually
- `rr`↔`tnt` — wisp, "functionality provided by TnT" ↳ advisory
- `atweaks`↔`aTweaks` (id=290, self-reference) — **DATA BUG**, same as cdtweaks pattern

## Action summary for Phase 1.2 (this PR)

- [x] EPS↔Stormlord both sides demoted to `advisories[]` with
  `evidenceLevel: "mechanism-verified"`, full trace in reason, mirror reference
  in source.
- [x] Audit script checked in as `scripts/audit_same_author_conflicts.py`.
- [x] Raw result checked in as `scripts/audit_same_author_conflicts.result.tsv`.
- [x] This README as triage reference for Phase 2.

## Action summary for Phase 2

- [ ] Migrate cdtweaks + aTweaks self-references (19 entries) to a new
      `componentExclusions[]` schema feature or to per-component `notes` —
      they do not belong in `conflicts[]`.
- [ ] Demote remaining category-D entries (5 pairs = 10 entries) to
      `advisories[]` with `evidenceLevel: "speculative"` or `"mechanism-verified"`.
- [ ] Upgrade category-A entries to `evidenceLevel: "observed"` with source
      citations pointing to tp2 FORBID_COMPONENT lines or readme paragraphs.
- [ ] Run the upcoming `scripts/grade_conflicts.py` (Phase 2.1) and let its
      automated grading catch any we missed.

## Re-running the audit

```
python scripts/audit_same_author_conflicts.py > scripts/audit_same_author_conflicts.result.tsv
```

Exit status is the hit count; a clean run should decrease across successive
audits as category-D entries get demoted out of `conflicts[]` into
`advisories[]`. Category A/B/C entries are expected to remain until Phase 2.
