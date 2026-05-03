#!/usr/bin/env python3
"""Audit tp2 drift for any mod with `tp2n` field populated.

Usage:
    python scripts/audit_tp2_drift.py              # all mods with tp2n populated
    python scripts/audit_tp2_drift.py <mod_stem>   # single mod
    python scripts/audit_tp2_drift.py --repair     # update tp2n in place
    python scripts/audit_tp2_drift.py --verbose    # show every entry

Compares each component's stored `tp2n` field against the raw name currently
in the extracted tp2 (priority tra order: weidu.tra, game.tra, ee.tra,
dw_components.tra, then others).

Exit codes:
    0 - no drift
    1 - drift detected (changes expected in tp2, `tp2n` needs refresh)
    2 - error (missing tp2 / parse failure)
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODS = ROOT / "data" / "mods"
EXTRACTED = Path("F:/BGMods/Extracted")

# Priority tra filenames — when multiple tra files declare the same @NNNN,
# these take precedence (they hold installer labels, not gameplay strings).
TRA_PRIORITY = ["weidu.tra", "game.tra", "ee.tra", "dw_components.tra"]


def find_tp2(mod_stem: str, wf: str) -> Path | None:
    """Search Extracted/ for setup-<wf>.tp2 or <wf>.tp2."""
    # Try the wf directly as a folder name first
    for candidate in EXTRACTED.rglob(f"setup-{wf}.tp2"):
        return candidate
    for candidate in EXTRACTED.rglob(f"{wf}.tp2"):
        return candidate
    return None


def find_tra_dir(tp2: Path) -> Path | None:
    """Find the English tra dir. Mods use varying conventions."""
    mod_folder = tp2.parent
    candidates = [
        mod_folder / "languages" / "english",
        mod_folder / "language" / "english",
        mod_folder / "lang" / "english",
        mod_folder / "lang" / "en",
        mod_folder / "lang" / "en_US",
        mod_folder / "lang" / "en_us",
        mod_folder / "tra" / "english",
        mod_folder / "tra" / "en_us",
        mod_folder / "translations" / "english",  # e.g. LivingClara
        mod_folder / "translations" / "en_US",
        mod_folder / "english",
        mod_folder / "en_US",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _load_single_tra(f: Path, tra_map: dict[int, str]) -> None:
    """Load one tra file.
    Semantics: LAST-WINS within the file (matches WeiDU), FIRST-WINS across
    files (caller controls priority). Keys already in tra_map are not updated."""
    try:
        txt = f.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return
    # Collect all @NNNN definitions, keeping the LAST occurrence per key
    local: dict[int, str] = {}
    for pattern in (r"@(\d+)\s*=\s*~([^~]*)~", r'@(\d+)\s*=\s*"([^"]*)"'):
        for m in re.finditer(pattern, txt, re.S):
            key = int(m.group(1))
            local[key] = m.group(2).strip()  # overwrites: last-wins
    # Merge into global map with first-wins across files
    for key, val in local.items():
        if key not in tra_map:
            tra_map[key] = val


def load_tra_map(tra_dir: Path | None, tp2: Path | None = None) -> dict[int, str]:
    """Load @NNNN labels from tra files.

    Priority order (first-wins across files):
      1. Files declared in the tp2's first LANGUAGE block (resolved relative to
         the tp2's parent directory, since those paths are mod-root-relative).
         This is what WeiDU itself uses for component-name @ref resolution.
      2. `setup.tra`, `setup-<wf>.tra`, `<wf>.tra` in tra_dir — the conventional
         filename for installer-facing strings when a mod doesn't declare
         LANGUAGE tra paths. **Critical fix:** before this addition, the parser
         fell through to alphabetical glob on Pass 4 below, which caused
         dialogue tras (e.g. `YF_botsmith.tra` < `setup.tra`) to win @ref
         resolution when they happened to redefine the same numeric key.
      3. TRA_PRIORITY constants (weidu.tra, game.tra, ee.tra, dw_components.tra)
      4. All other .tra files in tra_dir (non-recursive)
      5. All other .tra files recursively under the mod folder (english-scoped)
    """
    tra_map: dict[int, str] = {}

    # Pass 1: tp2 LANGUAGE block paths (mod-root-relative)
    declared: list[Path] = []
    mod_root = tp2.parent.parent if tp2 is not None else None  # mod folder's parent (containing wf folder)
    if tp2 is not None and tp2.exists():
        try:
            tp2_txt = tp2.read_text(encoding="utf-8", errors="replace")
            lang_match = re.search(
                r"^LANGUAGE\s+~[^~]+~\s+~[^~]+~\s+((?:\s*~[^~]+\.tra~\s*)+)",
                tp2_txt, re.M | re.I,
            )
            if lang_match:
                for tm in re.finditer(r"~([^~]+\.tra)~", lang_match.group(1)):
                    raw = tm.group(1).replace("\\", "/")
                    # Try mod_root relative first (WeiDU-style), then tra_dir
                    candidates = []
                    if mod_root:
                        candidates.append(mod_root / raw)
                    if tra_dir:
                        candidates.append(tra_dir / raw.rsplit("/", 1)[-1])
                    for cand in candidates:
                        if cand.exists():
                            declared.append(cand)
                            break
        except Exception:
            pass

    for f in declared:
        _load_single_tra(f, tra_map)
    loaded_names = {f.name.lower() for f in declared}

    # Pass 2: `setup.tra` / `setup-<wf>.tra` / `<wf>.tra` — conventional
    # installer-string filenames. Gives these priority over alphabetical
    # glob order, so dialogue tras can't win @ref resolution anymore.
    if tra_dir:
        wf_stem = tp2.stem if tp2 else None
        if wf_stem and wf_stem.lower().startswith("setup-"):
            wf_stem = wf_stem[6:]
        conv_names = ["setup.tra"]
        if wf_stem:
            conv_names += [f"setup-{wf_stem}.tra", f"{wf_stem}.tra"]
        # Case-insensitive filesystem match (Windows is case-insensitive but
        # Path comparisons can still miss case variants)
        existing = {f.name.lower(): f for f in tra_dir.glob("*.tra")}
        for name in conv_names:
            key = name.lower()
            if key in existing and key not in loaded_names:
                _load_single_tra(existing[key], tra_map)
                loaded_names.add(key)

    # Pass 3: priority files in tra_dir
    if tra_dir:
        for name in TRA_PRIORITY:
            f = tra_dir / name
            if f.exists() and f.name.lower() not in loaded_names:
                _load_single_tra(f, tra_map)
                loaded_names.add(name.lower())

    # Pass 4: other tras in tra_dir (non-recursive)
    if tra_dir:
        for f in tra_dir.glob("*.tra"):
            if f.name.lower() not in loaded_names:
                _load_single_tra(f, tra_map)
                loaded_names.add(f.name.lower())

    # Pass 5: recursive search under mod folder — for mods with nested tra dirs
    if tp2 is not None:
        wf_folder = tp2.parent
        for f in wf_folder.rglob("*.tra"):
            # Prefer english variants
            if "english" not in str(f).lower() and "en_us" not in str(f).lower():
                continue
            _load_single_tra(f, tra_map)

    return tra_map


def _strip_heredocs(txt: str) -> str:
    """Remove WeiDU `<<<<<<<<` ... `>>>>>>>>` heredoc blocks.

    Used for embedded .d dialog files, raw 2DA content, etc. Content between
    these markers is NOT tp2 syntax and can contain `BEGIN <identifier>` that
    looks like components but aren't.

    Preserves line numbering by replacing heredoc bodies with blank lines.
    """
    out = []
    in_hd = False
    open_re = re.compile(r'<{4,}')
    close_re = re.compile(r'>{4,}')
    for line in txt.split("\n"):
        if in_hd:
            if close_re.search(line):
                in_hd = False
            out.append("")
        else:
            if open_re.search(line):
                in_hd = True
                out.append("")
            else:
                out.append(line)
    return "\n".join(out)


def _strip_block_comments(txt: str) -> str:
    """Remove /* ... */ block comments so BEGINs inside them aren't parsed.
    Preserves line numbering by replacing comment contents with blank characters.

    Handles the `//**...` gotcha: a `//` line comment that happens to contain
    `/*` as a substring (e.g. `//*****` banners) should NOT be treated as a
    block-comment open. We strip `//` line comments first, then scan for
    real `/* ... */` spans.

    Note: does NOT handle `/*` inside strings (tp2 uses ~...~ and "..." but
    those rarely contain `/*` so this simplification is safe in practice).
    """
    out = []
    in_block = False
    for raw_line in txt.split("\n"):
        # Step 1: handle open block state from previous line
        if in_block:
            close = raw_line.find("*/")
            if close == -1:
                out.append("")
                continue
            line = raw_line[close + 2:]
            in_block = False
        else:
            line = raw_line
        # Step 2: strip `//...` line comments from `line`. Do it carefully:
        # find the earliest `//` NOT inside a `/* ... */` that we're currently
        # scanning. For simplicity, scan char-by-char with a mini state machine.
        result_chars = []
        i = 0
        while i < len(line):
            # Check for /* first — but only if not preceded by /
            if not in_block and line.startswith("//", i):
                # Line comment to end-of-line
                break
            if not in_block and line.startswith("/*", i):
                in_block = True
                i += 2
                continue
            if in_block:
                # Look for closing */ on this line
                close = line.find("*/", i)
                if close == -1:
                    break  # remains in block, rest of line is comment
                in_block = False
                i = close + 2
                continue
            result_chars.append(line[i])
            i += 1
        out.append("".join(result_chars))
    return "\n".join(out)


def parse_tp2_components(tp2: Path, tra_map: dict[int, str]) -> dict[int, str]:
    """Return {cn: tp2_name} for each real component in tp2.

    A component BEGIN is identified by:
      - Line starts with `BEGIN` at column 0 (no leading whitespace), AND
      - Next token is `@<num>` or `~<name>~` (not a bare `BEGIN` inside a block).

    Block comments /* ... */ are stripped before parsing so commented-out
    components (deprecated but left in source) are not counted.

    The DESIGNATED directive may be on the same line or within the first 15
    lines of the component block (before the next component BEGIN). If no
    DESIGNATED, fall back to BEGIN-order index (WeiDU's default numbering).
    """
    try:
        txt = tp2.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return {}
    txt = _strip_heredocs(txt)
    txt = _strip_block_comments(txt)
    lines = txt.split("\n")
    # Component BEGIN patterns handled:
    #   (a) BEGIN @num [DESIGNATED cn] [LABEL foo] ...        — same line, tra-keyed
    #   (b) BEGIN ~name~ [DESIGNATED cn] ...                  — same line, tilde name
    #   (c) BEGIN "name" [DESIGNATED cn] ...                  — same line, quoted name
    #   (d) BEGIN bare_identifier ...                         — unquoted name (ExpandedClasses)
    #   (e) BEGIN\n@num / BEGIN\n~name~ / BEGIN\n"name"       — split across lines
    # Excludes bare `BEGIN` followed by NOTHING (block scoping from ACTION_IF etc.)
    # or followed by ACTION-only tokens.

    # Component BEGIN regex — two flavors:
    # (A) BEGIN @num / ~name~ / "name" — tra-keyed or quoted, which are
    #     UNAMBIGUOUSLY components. May have more content after (DESIGNATED, LABEL).
    # (B) BEGIN bare_identifier — only if followed by nothing else on same line
    #     (optionally a comment). Otherwise it's a statement like
    #     `BEGIN OUTER_SPRINT var "path" END` inside an ACTION_IF block.
    begin_full_re = re.compile(
        r'^\s*BEGIN\s+(?:'
        r'@(\d+)'              # group 1: @NNN
        r'|~([^~]+)~'          # group 2: ~name~
        r'|"([^"]+)"'          # group 3: "name"
        r'|([A-Za-z_][\w#-]*)\s*(?://.*)?$'  # group 4: bare identifier + line-end/comment
        r')'
    )
    # Bare BEGIN on its own line (multiline split): look ahead for next non-blank non-comment line
    begin_bare_re = re.compile(r'^\s*BEGIN\s*$')

    # Block-exclusion keywords — BEGIN followed by these are NOT components
    BLOCK_KEYWORDS = {"END", "ELSE", "THEN"}

    def next_nonblank(start_idx):
        for k in range(start_idx, min(start_idx + 10, len(lines))):
            stripped = lines[k].strip()
            if not stripped:
                continue
            if stripped.startswith("//"):
                continue
            return k, stripped
        return None, None

    result: dict[int, str] = {}
    order = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        is_begin_full = begin_full_re.match(line)
        is_begin_bare = begin_bare_re.match(line)

        if not is_begin_full and not is_begin_bare:
            i += 1
            continue

        begin_id = None
        inline_name = None

        if is_begin_full:
            # Has argument on same line
            begin_id = int(is_begin_full.group(1)) if is_begin_full.group(1) else None
            tilde_name = is_begin_full.group(2)
            quoted_name = is_begin_full.group(3)
            bare_name = is_begin_full.group(4)
            inline_name = tilde_name or quoted_name or bare_name
            # If bare identifier matches a block keyword, this is NOT a component
            if bare_name and bare_name.upper() in BLOCK_KEYWORDS:
                i += 1
                continue
        else:
            # BEGIN alone on line — component only if next non-blank line is
            # EXCLUSIVELY `@num` or `~name~` with no other tokens (except
            # trailing whitespace/comment). This filters out false positives
            # like `OUTER_FOR (...) BEGIN\nCOPY_EXISTING ~file.ext~ ~override~`
            # where my old regex wrongly matched the `~file.ext~` as a name.
            k, next_line = next_nonblank(i + 1)
            if k is None:
                i += 1
                continue
            stripped = next_line.strip()
            # Strict: whole next line must be @num or ~text~ (comment allowed)
            strict_re = re.compile(
                r'^(?:@(\d+)|~([^~]+)~)\s*(?://.*)?$'
            )
            m = strict_re.match(stripped)
            if not m:
                i += 1
                continue
            begin_id = int(m.group(1)) if m.group(1) else None
            inline_name = m.group(2)
        # Scan next 15 lines for DESIGNATED, stopping at next component BEGIN
        cn = None
        for j in range(i, min(i + 16, len(lines))):
            if j > i and (begin_full_re.match(lines[j]) or begin_bare_re.match(lines[j])):
                break
            des_m = re.search(r'\bDESIGNATED\s+(\d+)', lines[j])
            if des_m and cn is None:
                cn = int(des_m.group(1))
        if cn is None:
            cn = order
        # Resolve display name: tra lookup first, then inline ~name~ fallback
        name = tra_map.get(begin_id, "") if begin_id is not None else ""
        if not name and inline_name:
            name = inline_name.strip()
        # Always record the component — empty string is fine if name unresolved.
        # Drift scan compares cn sets; callers can check for empty names separately.
        result[cn] = name
        order += 1
        i += 1
    return result


def audit_mod(mod_json: Path, verbose: bool = False, repair: bool = False) -> tuple[int, int, int]:
    """Audit one mod. Returns (drift_count, no_tp2n_count, missing_in_tp2_count)."""
    try:
        d = json.loads(mod_json.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  PARSE ERROR: {e}", file=sys.stderr)
        return 0, 0, 0

    co = d.get("co", [])
    tagged = [c for c in co if "tp2n" in c]
    if not tagged:
        if verbose:
            print(f"  {mod_json.stem}: no tp2n field populated — skipped")
        return 0, 0, 0

    wf = None
    for c in co:
        if c.get("wf"):
            wf = c["wf"]
            break
    if not wf:
        if verbose:
            print(f"  {mod_json.stem}: no wf found — skipped")
        return 0, 0, 0

    tp2 = find_tp2(mod_json.stem, wf)
    if not tp2:
        print(f"  {mod_json.stem}: tp2 not found in Extracted/", file=sys.stderr)
        return 0, 0, 0

    tra_dir = find_tra_dir(tp2)
    tra_map = load_tra_map(tra_dir, tp2) if tra_dir else {}
    current = parse_tp2_components(tp2, tra_map)

    drift = []
    missing = []
    for c in co:
        cn = c.get("cn")
        stored = c.get("tp2n")
        if stored is None:
            continue
        live = current.get(cn)
        if live is None:
            missing.append(cn)
        elif live != stored:
            drift.append((cn, stored, live))

    if drift:
        print(f"  {mod_json.stem}: {len(drift)} drifted tp2n (tp2 changed since last backfill)")
        for cn, old, new in drift[:5]:
            print(f"    cn={cn}")
            print(f"      stored: {old!r}")
            print(f"      current: {new!r}")
        if len(drift) > 5:
            print(f"    ... +{len(drift) - 5} more")
        if repair:
            for cn, _, new in drift:
                for c in co:
                    if c.get("cn") == cn and "tp2n" in c:
                        c["tp2n"] = new
            mod_json.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"    → repaired")
    if missing:
        print(f"  {mod_json.stem}: {len(missing)} components no longer in v18 tp2 (may be deprecated)")
        if verbose:
            print(f"    cns: {missing[:20]}")
    if verbose and not drift and not missing:
        print(f"  {mod_json.stem}: clean ({len(tagged)} entries checked)")

    return len(drift), 0, len(missing)


def main():
    args = sys.argv[1:]
    verbose = "--verbose" in args
    repair = "--repair" in args
    targets = [a for a in args if not a.startswith("--")]

    if targets:
        mods = [MODS / f"{t}.json" for t in targets if (MODS / f"{t}.json").exists()]
    else:
        mods = sorted(MODS.glob("*.json"))

    total_drift = 0
    total_missing = 0
    for m in mods:
        if m.name.startswith("_"):
            continue
        drift, _, missing = audit_mod(m, verbose=verbose, repair=repair)
        total_drift += drift
        total_missing += missing

    print(f"\nTotal drift: {total_drift}")
    print(f"Total missing-in-tp2 (possibly deprecated): {total_missing}")
    sys.exit(0 if total_drift == 0 else 1)


if __name__ == "__main__":
    main()
