#!/usr/bin/env python3
"""
Import and merge author-provided mod-forge.json into the Mod Forge database.

Validates against the schema, then either creates a new detail file or merges
author-provided fields into an existing one — preserving curated fields like
install order (c, ord), sub-option structure (x), and editorial notes.

Usage:
    python scripts/import_author_json.py path/to/mod-forge.json          # preview
    python scripts/import_author_json.py path/to/mod-forge.json --write  # apply
    python scripts/import_author_json.py --scan-repos                    # scan GitHub repos
    python scripts/import_author_json.py --scan-repos --write            # scan + apply
"""

import argparse
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, '..')
DATA_DIR = os.path.join(ROOT_DIR, 'data')
MODS_DIR = os.path.join(DATA_DIR, 'mods')
SCHEMA_PATH = os.path.join(ROOT_DIR, 'schemas', 'mod-forge.schema.json')


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


# ---- Validation -------------------------------------------------------------

def validate_author_json(data):
    """Basic validation of author-provided mod-forge.json.

    Returns list of error strings (empty = valid).
    Does structural checks without requiring jsonschema library.
    """
    errors = []

    if not isinstance(data, dict):
        return ["Root must be a JSON object"]

    for field in ('tp2', 'name', 'author', 'components'):
        if field not in data:
            errors.append(f"Missing required field: {field}")

    if 'tp2' in data:
        if not isinstance(data['tp2'], str) or not re.match(r'^[A-Za-z0-9_#-]+$', data['tp2']):
            errors.append("'tp2' must be a string matching [A-Za-z0-9_#-]+")

    if 'components' in data:
        if not isinstance(data['components'], list) or len(data['components']) == 0:
            errors.append("'components' must be a non-empty array")
        else:
            seen_cn = set()
            for idx, comp in enumerate(data['components']):
                if not isinstance(comp, dict):
                    errors.append(f"components[{idx}]: must be an object")
                    continue
                if 'name' not in comp:
                    errors.append(f"components[{idx}]: missing 'name'")
                if 'number' not in comp:
                    errors.append(f"components[{idx}]: missing 'number'")
                elif not isinstance(comp['number'], int) or comp['number'] < 0:
                    errors.append(f"components[{idx}]: 'number' must be a non-negative integer")
                else:
                    if comp['number'] in seen_cn:
                        errors.append(f"components[{idx}]: duplicate number {comp['number']}")
                    seen_cn.add(comp['number'])

    if 'languages' in data:
        if not isinstance(data['languages'], dict):
            errors.append("'languages' must be an object")
        else:
            for code, idx in data['languages'].items():
                if not re.match(r'^[a-z]{2}(-[a-z]{2,4})?$', code):
                    errors.append(f"languages: invalid ISO code '{code}'")
                if not isinstance(idx, int) or idx < 0:
                    errors.append(f"languages[{code}]: index must be non-negative integer")

    if 'tags' in data:
        valid_tags = {
            "qol", "restore", "story", "class", "visual", "quest", "npc",
            "tweak", "tactical", "item", "spell", "portrait", "sound",
            "ui", "fix", "kit", "rule", "encounter", "romance"
        }
        if isinstance(data['tags'], list):
            for tag in data['tags']:
                if tag not in valid_tags:
                    errors.append(f"tags: unknown tag '{tag}' (valid: {', '.join(sorted(valid_tags))})")

    if 'games' in data:
        valid_phases = {"BG1", "SoD", "SoA", "ToB"}
        if isinstance(data['games'], list):
            for g in data['games']:
                if g not in valid_phases:
                    errors.append(f"games: unknown phase '{g}' (valid: {', '.join(sorted(valid_phases))})")

    if 'conflicts' in data and isinstance(data['conflicts'], list):
        valid_sev = {"hard", "partial", "soft"}
        for idx, c in enumerate(data['conflicts']):
            if isinstance(c, dict):
                if 'mod' not in c:
                    errors.append(f"conflicts[{idx}]: missing 'mod'")
                if 'severity' not in c:
                    errors.append(f"conflicts[{idx}]: missing 'severity'")
                elif c.get('severity') not in valid_sev:
                    errors.append(f"conflicts[{idx}]: invalid severity '{c['severity']}'")

    if 'knownIssues' in data and isinstance(data['knownIssues'], list):
        valid_ki_sev = {"critical", "error", "warning", "info"}
        for idx, ki in enumerate(data['knownIssues']):
            if isinstance(ki, dict):
                if 'description' not in ki:
                    errors.append(f"knownIssues[{idx}]: missing 'description'")
                if 'severity' not in ki:
                    errors.append(f"knownIssues[{idx}]: missing 'severity'")
                elif ki.get('severity') not in valid_ki_sev:
                    errors.append(f"knownIssues[{idx}]: invalid severity '{ki['severity']}'")

    return errors


# ---- Finding existing detail file -------------------------------------------

def find_detail_file(tp2_name):
    """Find the existing detail file for a tp2 name, if any."""
    # Direct filename match
    candidate = os.path.join(MODS_DIR, f"{tp2_name}.json")
    if os.path.isfile(candidate):
        return candidate

    # Search all detail files for matching 't' field
    for fname in os.listdir(MODS_DIR):
        if not fname.endswith('.json') or fname.startswith('_'):
            continue
        try:
            detail = load_json(os.path.join(MODS_DIR, fname))
            if detail.get('t', '').lower() == tp2_name.lower():
                return os.path.join(MODS_DIR, fname)
        except (json.JSONDecodeError, OSError):
            continue
    return None


# ---- Component merging ------------------------------------------------------

def build_cn_to_index(co_array):
    """Build a map of component number → array index for existing co[]."""
    return {c.get('cn', c.get('wc', i)): i for i, c in enumerate(co_array)}


def merge_component(existing_comp, author_comp):
    """Merge author-provided component data into an existing component.

    Author fields that are safe to update:
    - n (name), no (notes), dep (deprecated), gone (removed)
    - k (kits), sp (spells), ss (splstates), it (items)

    Curated fields preserved from existing:
    - x, g, rd, rd2, cat, sg, wb, wf, wp, wc, wq, pi, tg
    """
    updated = dict(existing_comp)

    # Always update name from author
    if author_comp.get('name'):
        updated['n'] = author_comp['name']

    # Notes: author notes supplement existing, don't replace
    if author_comp.get('notes'):
        if updated.get('no'):
            # Only add if substantially different
            if author_comp['notes'].strip() not in updated['no']:
                updated['no'] = updated['no'] + ' | AUTHOR: ' + author_comp['notes']
        else:
            updated['no'] = author_comp['notes']

    # Boolean flags
    if author_comp.get('deprecated'):
        updated['dep'] = True
    if author_comp.get('removed'):
        updated['gone'] = True

    # Engine resource counts
    if 'kits' in author_comp and author_comp['kits']:
        updated['k'] = author_comp['kits']
    if 'spells' in author_comp and author_comp['spells']:
        updated['sp'] = author_comp['spells']
    if 'splstates' in author_comp and author_comp['splstates']:
        updated['ss'] = author_comp['splstates']
    if 'items' in author_comp and author_comp['items']:
        updated['it'] = author_comp['items']

    # Label → pi (permanent ID)
    if author_comp.get('label') and not updated.get('pi'):
        updated['pi'] = author_comp['label']

    return updated


def build_new_component(author_comp):
    """Create a new internal component entry from author data."""
    comp = {
        'n': author_comp.get('name', ''),
        'cn': author_comp['number'],
    }
    if author_comp.get('group'):
        comp['g'] = author_comp['group']
    if author_comp.get('label'):
        comp['pi'] = author_comp['label']
    if author_comp.get('notes'):
        comp['no'] = author_comp['notes']
    if author_comp.get('deprecated'):
        comp['dep'] = True
    if author_comp.get('removed'):
        comp['gone'] = True
    if author_comp.get('kits'):
        comp['k'] = author_comp['kits']
    if author_comp.get('spells'):
        comp['sp'] = author_comp['spells']
    if author_comp.get('splstates'):
        comp['ss'] = author_comp['splstates']
    if author_comp.get('items'):
        comp['it'] = author_comp['items']
    return comp


# ---- Conflict / dependency merging ------------------------------------------

def merge_conflicts(existing, author_conflicts, tp2_name):
    """Merge author-provided conflicts into existing conflicts array."""
    existing_conflicts = existing.get('conflicts', [])
    existing_mods = {c.get('with', '').lower() for c in existing_conflicts}

    for ac in author_conflicts:
        if ac['mod'].lower() in existing_mods:
            # Update existing conflict
            for ec in existing_conflicts:
                if ec.get('with', '').lower() == ac['mod'].lower():
                    if ac.get('reason'):
                        ec['reason'] = ac['reason']
                    ec['severity'] = ac['severity']
                    if ac.get('myComponents'):
                        ec['myComps'] = ac['myComponents']
                    if ac.get('theirComponents'):
                        ec['theirComps'] = ac['theirComponents']
                    ec['source'] = f"mod-forge.json ({tp2_name})"
                    break
        else:
            new_conflict = {
                'with': ac['mod'],
                'severity': ac['severity'],
                'source': f"mod-forge.json ({tp2_name})",
            }
            if ac.get('reason'):
                new_conflict['reason'] = ac['reason']
            if ac.get('myComponents'):
                new_conflict['myComps'] = ac['myComponents']
            if ac.get('theirComponents'):
                new_conflict['theirComps'] = ac['theirComponents']
            existing_conflicts.append(new_conflict)

    return existing_conflicts


def merge_dependencies(existing, author_deps, tp2_name):
    """Merge author-provided dependencies into existing."""
    existing_deps = existing.get('dependencies', [])
    existing_mods = {d.get('requires', '').lower() for d in existing_deps}

    for ad in author_deps:
        if ad['mod'].lower() not in existing_mods:
            new_dep = {
                'requires': ad['mod'],
                'type': ad.get('type', 'soft'),
            }
            if ad.get('reason'):
                new_dep['reason'] = ad['reason']
            existing_deps.append(new_dep)

    return existing_deps


def merge_known_issues(existing, author_kis):
    """Merge author-provided known issues into existing ki array."""
    existing_ki = existing.get('ki', [])
    existing_patterns = {ki.get('pattern', '') for ki in existing_ki}

    for aki in author_kis:
        pattern = aki.get('pattern', '')
        if pattern and pattern in existing_patterns:
            continue  # Already have this pattern
        new_ki = {
            'severity': aki['severity'],
            'description': aki['description'],
        }
        if pattern:
            new_ki['pattern'] = pattern
        if aki.get('workaround'):
            new_ki['workaround'] = aki['workaround']
        if aki.get('components'):
            new_ki['components'] = aki['components']
        if aki.get('forum'):
            new_ki['forum'] = aki['forum']
        existing_ki.append(new_ki)

    return existing_ki


# ---- Main merge logic -------------------------------------------------------

def merge_into_existing(existing, author_data):
    """Merge author data into an existing detail file. Returns (updated, changes)."""
    changes = []

    # Update simple metadata (author is authoritative for these)
    if author_data.get('name') and author_data['name'] != existing.get('n'):
        changes.append(f"  name: {existing.get('n', '?')} -> {author_data['name']}")
        existing['n'] = author_data['name']

    if author_data.get('author') and author_data['author'] != existing.get('a'):
        changes.append(f"  author: {existing.get('a', '?')} -> {author_data['author']}")
        existing['a'] = author_data['author']

    if author_data.get('version') and author_data['version'] != existing.get('v'):
        changes.append(f"  version: {existing.get('v', '?')} -> {author_data['version']}")
        existing['v'] = author_data['version']

    if author_data.get('homepage') and author_data['homepage'] != existing.get('u'):
        changes.append(f"  homepage: {existing.get('u', '?')} -> {author_data['homepage']}")
        existing['u'] = author_data['homepage']

    if author_data.get('summary') and author_data['summary'] != existing.get('sum'):
        changes.append(f"  summary updated")
        existing['sum'] = author_data['summary']

    if author_data.get('tags'):
        existing['tags'] = author_data['tags']
        changes.append(f"  tags: {author_data['tags']}")

    if author_data.get('games'):
        existing['ph'] = author_data['games']
        changes.append(f"  phases: {author_data['games']}")

    if author_data.get('languages'):
        existing['langs'] = author_data['languages']
        changes.append(f"  languages: {list(author_data['languages'].keys())}")

    # Merge components
    existing_co = existing.get('co', [])
    cn_to_idx = build_cn_to_index(existing_co)

    new_components = 0
    updated_components = 0

    for ac in author_data.get('components', []):
        cn = ac['number']
        if cn in cn_to_idx:
            idx = cn_to_idx[cn]
            merged = merge_component(existing_co[idx], ac)
            if merged != existing_co[idx]:
                existing_co[idx] = merged
                updated_components += 1
        else:
            existing_co.append(build_new_component(ac))
            new_components += 1

    if updated_components:
        changes.append(f"  components updated: {updated_components}")
    if new_components:
        changes.append(f"  components added: {new_components}")
    existing['co'] = existing_co

    # Merge conflicts, dependencies, known issues
    tp2 = author_data.get('tp2', existing.get('t', ''))

    if author_data.get('conflicts'):
        existing['conflicts'] = merge_conflicts(existing, author_data['conflicts'], tp2)
        changes.append(f"  conflicts merged: {len(author_data['conflicts'])}")

    if author_data.get('dependencies'):
        existing['dependencies'] = merge_dependencies(existing, author_data['dependencies'], tp2)
        changes.append(f"  dependencies merged: {len(author_data['dependencies'])}")

    if author_data.get('knownIssues'):
        existing['ki'] = merge_known_issues(existing, author_data['knownIssues'])
        changes.append(f"  known issues merged: {len(author_data['knownIssues'])}")

    return existing, changes


def create_new_detail(author_data, next_id):
    """Create a new detail file from author data."""
    detail = {
        'i': next_id,
        't': author_data['tp2'],
        'ord': 100,
        'c': 'UNCATEGORIZED',
        'n': author_data['name'],
    }

    if author_data.get('languages'):
        detail['langs'] = author_data['languages']
    if author_data.get('homepage'):
        detail['u'] = author_data['homepage']
    if author_data.get('author'):
        detail['a'] = author_data['author']
    if author_data.get('version'):
        detail['v'] = author_data['version']
    if author_data.get('summary'):
        detail['sum'] = author_data['summary']
    if author_data.get('tags'):
        detail['tags'] = author_data['tags']
    if author_data.get('games'):
        detail['ph'] = author_data['games']

    # Build components
    co = []
    for ac in author_data.get('components', []):
        co.append(build_new_component(ac))
    detail['co'] = co

    # Conflicts, dependencies, known issues
    if author_data.get('conflicts'):
        detail['conflicts'] = merge_conflicts({}, author_data['conflicts'], author_data['tp2'])
    if author_data.get('dependencies'):
        detail['dependencies'] = merge_dependencies({}, author_data['dependencies'], author_data['tp2'])
    if author_data.get('knownIssues'):
        detail['ki'] = merge_known_issues({}, author_data['knownIssues'])

    return detail


def get_next_mod_id():
    """Find the next available mod ID by scanning all detail files."""
    max_id = 0
    for fname in os.listdir(MODS_DIR):
        if not fname.endswith('.json') or fname.startswith('_'):
            continue
        try:
            detail = load_json(os.path.join(MODS_DIR, fname))
            mod_id = detail.get('i', 0)
            if mod_id > max_id:
                max_id = mod_id
        except (json.JSONDecodeError, OSError):
            continue
    return max_id + 1


# ---- GitHub scanning --------------------------------------------------------

def scan_github_repos():
    """Scan known GitHub repos for mod-forge.json files.

    Returns list of (repo_url, author_data) tuples for repos that have the file.
    """
    results = []
    repos = set()

    # Collect all GitHub repos from detail files
    for fname in os.listdir(MODS_DIR):
        if not fname.endswith('.json') or fname.startswith('_'):
            continue
        try:
            detail = load_json(os.path.join(MODS_DIR, fname))
            gh = detail.get('gh')
            if gh and 'o' in gh and 'r' in gh:
                repos.add((gh['o'], gh['r']))
        except (json.JSONDecodeError, OSError):
            continue

    print(f"Scanning {len(repos)} GitHub repos for mod-forge.json...", file=sys.stderr)

    for owner, repo in sorted(repos):
        try:
            result = subprocess.run(
                ['gh', 'api', f'repos/{owner}/{repo}/contents/mod-forge.json',
                 '--jq', '.content'],
                capture_output=True, text=True, timeout=15,
                encoding='utf-8', errors='replace'
            )
            if result.returncode != 0:
                continue

            import base64
            content = base64.b64decode(result.stdout.strip()).decode('utf-8')
            data = json.loads(content)
            results.append((f"{owner}/{repo}", data))
            print(f"  Found: {owner}/{repo}", file=sys.stderr)

        except Exception:
            continue

    return results


# ---- CLI --------------------------------------------------------------------

def import_one(author_path, write=False):
    """Import a single mod-forge.json file."""
    try:
        author_data = load_json(author_path)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading {author_path}: {e}", file=sys.stderr)
        return False

    errors = validate_author_json(author_data)
    if errors:
        print(f"Validation errors in {author_path}:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return False

    tp2_name = author_data['tp2']
    existing_path = find_detail_file(tp2_name)

    if existing_path:
        existing = load_json(existing_path)
        updated, changes = merge_into_existing(existing, author_data)

        if not changes:
            print(f"{tp2_name}: no changes needed")
            return True

        print(f"{tp2_name}: merging into {os.path.basename(existing_path)}")
        for c in changes:
            print(c)

        if write:
            save_json(existing_path, updated)
            print(f"  -> Written to {existing_path}")
    else:
        next_id = get_next_mod_id()
        detail = create_new_detail(author_data, next_id)
        out_path = os.path.join(MODS_DIR, f"{tp2_name}.json")

        print(f"{tp2_name}: NEW mod (id={next_id})")
        print(f"  name: {author_data['name']}")
        print(f"  components: {len(author_data.get('components', []))}")
        print(f"  *** NEEDS MANUAL CURATION: category (c) and install order (ord) ***")

        if write:
            save_json(out_path, detail)
            print(f"  -> Written to {out_path}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Import author-provided mod-forge.json into the Mod Forge database."
    )
    parser.add_argument("files", nargs='*', help="mod-forge.json file(s) to import")
    parser.add_argument("--write", action="store_true",
                        help="Actually write changes (default: dry run)")
    parser.add_argument("--scan-repos", action="store_true",
                        help="Scan known GitHub repos for mod-forge.json files")

    args = parser.parse_args()

    if not args.files and not args.scan_repos:
        parser.print_help()
        sys.exit(1)

    success = True

    # Import explicit files
    for path in args.files:
        if not import_one(path, args.write):
            success = False

    # Scan GitHub repos
    if args.scan_repos:
        found = scan_github_repos()
        if not found:
            print("No mod-forge.json files found in any tracked repos.")
        for repo_url, data in found:
            errors = validate_author_json(data)
            if errors:
                print(f"\n{repo_url}: validation errors")
                for err in errors:
                    print(f"  - {err}")
                success = False
                continue

            tp2_name = data['tp2']
            existing_path = find_detail_file(tp2_name)

            if existing_path:
                existing = load_json(existing_path)
                updated, changes = merge_into_existing(existing, data)

                if not changes:
                    continue  # No changes, skip silently

                print(f"\n{repo_url} ({tp2_name}): merging")
                for c in changes:
                    print(c)

                if args.write:
                    save_json(existing_path, updated)
                    print(f"  -> Written")
            else:
                next_id = get_next_mod_id()
                detail = create_new_detail(data, next_id)
                out_path = os.path.join(MODS_DIR, f"{tp2_name}.json")

                print(f"\n{repo_url} ({tp2_name}): NEW mod (id={next_id})")
                print(f"  *** NEEDS MANUAL CURATION: category (c) and install order (ord) ***")

                if args.write:
                    save_json(out_path, detail)
                    print(f"  -> Written")

    if not args.write and (args.files or args.scan_repos):
        print("\n(dry run — use --write to apply changes)")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
