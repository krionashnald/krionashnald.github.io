#!/usr/bin/env python3
"""
Populate mod detail files by fetching and parsing TP2 files from GitHub.

Reads data/lcc-candidates.json, finds candidates with GitHub URLs,
fetches their TP2 files via the GitHub API, parses components and
languages, and generates complete detail files.

Usage:
    python scripts/populate_from_github.py                # Dry run
    python scripts/populate_from_github.py --write        # Create files
    python scripts/populate_from_github.py --write --limit 10  # First 10 only
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, '..')
DATA_DIR = os.path.join(ROOT_DIR, 'data')
MODS_DIR = os.path.join(DATA_DIR, 'mods')
INDEX_PATH = os.path.join(DATA_DIR, 'mods-index.json')
CATALOG_PATH = os.path.join(MODS_DIR, '_catalog.json')
CANDIDATES_PATH = os.path.join(DATA_DIR, 'lcc-candidates.json')


# ---- Language parsing (from populate_langs.py) ----------------------------

FOLDER_TO_ISO = {
    "english": "en", "american": "en", "enus": "en",
    "englishrevision": "en", "englishoriginal": "en",
    "french": "fr", "francais": "fr", "frfr": "fr",
    "german": "de", "deutsch": "de", "dede": "de",
    "shgerman": "de", "germansh": "de",
    "spanish": "es", "espanol": "es", "eses": "es",
    "castilian": "es", "castellano": "es",
    "italian": "it", "italiano": "it",
    "polish": "pl", "polski": "pl", "plpl": "pl",
    "russian": "ru", "ruru": "ru",
    "czech": "cs", "cscz": "cs", "cesky": "cs",
    "korean": "ko",
    "japanese": "ja", "japan": "ja",
    "portuguese": "pt", "brazilian": "pt-br",
    "brazilian_portuguese": "pt-br", "brazilianportuguese": "pt-br",
    "ptbr": "pt-br",
    "chinese": "zh-cn", "schinese": "zh-cn", "simplifiedchinese": "zh-cn",
    "chinesesimplified": "zh-cn", "chinese(simplified)": "zh-cn",
    "chs": "zh-cn", "zhcn": "zh-cn",
    "tchinese": "zh-tw", "traditionalchinese": "zh-tw", "chineset": "zh-tw",
    "hungarian": "hu", "romanian": "ro",
    "turkish": "tr", "turkce": "tr",
    "dutch": "nl", "swedish": "sv", "norwegian": "no",
    "danish": "da", "finnish": "fi", "ukrainian": "uk",
    "catalan": "ca", "galician": "gl", "basque": "eu",
}


def normalize_folder(folder):
    """Map a WeiDU language folder name to an ISO code."""
    f = folder.lower().strip().replace(" ", "").replace("-", "").replace("_", "")
    parts = f.replace("\\", "/").split("/")
    for part in reversed(parts):
        if part in FOLDER_TO_ISO:
            return FOLDER_TO_ISO[part]
        if len(part) == 2 and part.isalpha():
            short_map = {
                "en": "en", "fr": "fr", "de": "de", "es": "es",
                "it": "it", "pl": "pl", "ru": "ru", "cs": "cs",
                "ko": "ko", "ja": "ja", "pt": "pt", "nl": "nl",
                "sv": "sv", "no": "no", "da": "da", "fi": "fi",
                "uk": "uk", "hu": "hu", "ro": "ro", "tr": "tr",
                "sp": "es", "jp": "ja", "po": "pl",
            }
            if part in short_map:
                return short_map[part]
    if f in FOLDER_TO_ISO:
        return FOLDER_TO_ISO[f]
    return None


# ---- TP2 parsing ----------------------------------------------------------

def strip_comments(text):
    """Remove WeiDU block comments /* ... */ and line comments //."""
    # Block comments (non-greedy, can span lines)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # Line comments (only outside strings — simplified: just strip // not inside ~)
    lines = []
    for line in text.split('\n'):
        # Don't strip // inside ~strings~
        if '//' in line:
            in_tilde = False
            result = []
            i = 0
            while i < len(line):
                if line[i] == '~':
                    in_tilde = not in_tilde
                    result.append(line[i])
                elif line[i:i+2] == '//' and not in_tilde:
                    break
                else:
                    result.append(line[i])
                i += 1
            lines.append(''.join(result))
        else:
            lines.append(line)
    return '\n'.join(lines)


def parse_tp2_languages(text):
    """Extract LANGUAGE entries. Returns list of (display, folder) tuples."""
    delim = r'(?:~([^~]*)~|"([^"]*)")'
    pattern = rf"^\s*LANGUAGE\s+{delim}\s+{delim}"
    langs = []
    for m in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
        display = (m.group(1) or m.group(2)).strip()
        folder = (m.group(3) or m.group(4)).strip()
        langs.append((display, folder))
    return langs


def parse_tp2_components(text):
    """Extract BEGIN/DESIGNATED components. Returns list of dicts."""
    components = []
    auto_num = 0  # auto-number for components without DESIGNATED

    # Match BEGIN with optional string delimiters and DESIGNATED/SUBCOMPONENT
    # Pattern: BEGIN ~name~ or BEGIN "name" or BEGIN @number
    begin_pattern = re.compile(
        r'^\s*BEGIN\s+(?:~([^~]*)~|"([^"]*)"|(@\d+))',
        re.MULTILINE | re.IGNORECASE
    )

    for m in begin_pattern.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3) or ''
        name = name.strip()

        # Look for DESIGNATED number after this BEGIN (within next ~200 chars)
        after = text[m.end():m.end() + 300]
        desig_m = re.search(r'DESIGNATED\s+(\d+)', after, re.IGNORECASE)

        if desig_m:
            cn = int(desig_m.group(1))
            auto_num = cn + 1  # Next auto-number follows this
        else:
            cn = auto_num
            auto_num += 1

        # Check for SUBCOMPONENT (group)
        sub_m = re.search(
            r'SUBCOMPONENT\s+(?:~([^~]*)~|"([^"]*)")',
            after, re.IGNORECASE
        )
        group = None
        if sub_m:
            group = (sub_m.group(1) or sub_m.group(2) or '').strip()

        # Check for LABEL
        label_m = re.search(r'LABEL\s+(?:~([^~]*)~|"([^"]*)")', after, re.IGNORECASE)
        label = None
        if label_m:
            label = (label_m.group(1) or label_m.group(2) or '').strip()

        components.append({
            'name': name,
            'cn': cn,
            'group': group,
            'label': label,
        })

    return components


def build_langs_dict(lang_tuples):
    """Convert (display, folder) tuples to our langs dict format."""
    langs = {}
    for idx, (display, folder) in enumerate(lang_tuples):
        iso = normalize_folder(folder)
        if iso and iso not in langs:
            langs[iso] = idx
    return langs


# ---- GitHub API -----------------------------------------------------------

def parse_github_url(url):
    """Extract owner/repo from a GitHub URL.
    Handles: github.com/owner/repo, github.com/owner/repo/anything"""
    m = re.match(r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?(?:/.*)?$', url)
    if m:
        return m.group(1), m.group(2)
    return None, None


def gh_api(endpoint, jq_filter=None):
    """Call GitHub API via gh CLI. Returns parsed JSON or None."""
    cmd = ['gh', 'api', endpoint]
    if jq_filter:
        cmd.extend(['--jq', jq_filter])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                encoding='utf-8', errors='replace')
        if result.returncode != 0:
            return None
        if jq_filter:
            return result.stdout.strip()
        return json.loads(result.stdout)
    except Exception:
        return None


def find_tp2_in_repo(owner, repo):
    """Find .tp2 and setup.tra files in a GitHub repo.
    Returns (tp2_files, tra_files) where tra_files are English setup.tra paths."""
    data = gh_api(f'repos/{owner}/{repo}/git/trees/HEAD?recursive=1')
    if not data or 'tree' not in data:
        return [], []

    tp2_files = []
    tra_files = []
    for item in data['tree']:
        if item.get('type') != 'blob':
            continue
        p = item['path']
        pl = p.lower()
        if pl.endswith('.tp2'):
            tp2_files.append(p)
        elif pl.endswith('setup.tra') and 'english' in pl:
            tra_files.append(p)
    return tp2_files, tra_files


def parse_tra_file(text):
    """Parse a WeiDU TRA file. Returns dict of @number -> string."""
    strings = {}
    # Pattern: @number = ~string~ or @number = "string"
    pattern = re.compile(r'@(\d+)\s*=\s*(?:~([^~]*)~|"([^"]*)")', re.MULTILINE)
    for m in pattern.finditer(text):
        num = int(m.group(1))
        value = (m.group(2) if m.group(2) is not None else m.group(3)).strip()
        strings[num] = value
    return strings


def resolve_at_refs(components, tra_strings):
    """Replace @N references in component names with TRA string values."""
    for comp in components:
        name = comp['name']
        if name.startswith('@') and name[1:].isdigit():
            ref_num = int(name[1:])
            if ref_num in tra_strings:
                resolved = tra_strings[ref_num]
                # Strip inline comments like // description
                if '//' in resolved:
                    resolved = resolved.split('//')[0].strip()
                comp['name'] = resolved
    return components


def pick_best_tp2(tp2_files, expected_folder):
    """Pick the most likely main TP2 file for a mod."""
    if not tp2_files:
        return None
    if len(tp2_files) == 1:
        return tp2_files[0]

    ef = expected_folder.lower()

    # Prefer setup-*.tp2 or mod-named *.tp2 in the expected folder
    scored = []
    for path in tp2_files:
        p = path.lower()
        bn = os.path.basename(p)
        score = 0

        # Boost: filename matches expected folder
        if ef in bn:
            score += 10
        # Boost: setup- prefix
        if bn.startswith('setup-'):
            score += 5
        # Boost: path contains expected folder
        if ef in p:
            score += 3
        # Penalize: deeply nested
        depth = p.count('/')
        score -= depth

        scored.append((score, path))

    scored.sort(key=lambda x: -x[0])
    return scored[0][1]


def fetch_tp2_content(owner, repo, path):
    """Download raw TP2 file content from GitHub."""
    # Try default branch names
    for branch in ['main', 'master', 'HEAD']:
        url = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}'
        cmd = ['curl', '-sL', '-f', url]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30,
                                    encoding='utf-8', errors='replace')
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
        except Exception:
            continue
    return None


# ---- Detail file generation -----------------------------------------------

def generate_detail(candidate, tp2_text, tp2_path, next_id, tra_strings=None):
    """Generate a mod detail dict from candidate data and parsed TP2."""
    tp2_folder = candidate['tp2']
    clean = strip_comments(tp2_text)

    # Parse languages
    lang_tuples = parse_tp2_languages(clean)
    langs = build_langs_dict(lang_tuples)

    # Parse components
    components = parse_tp2_components(clean)

    # Resolve @references from TRA file
    if tra_strings:
        resolve_at_refs(components, tra_strings)

    # Derive WeiDU folder and path
    # The tp2 path from GitHub tells us the actual folder structure
    tp2_basename = os.path.basename(tp2_path)
    tp2_dirname = os.path.dirname(tp2_path)
    # WeiDU folder is typically the directory containing the tp2
    wf = tp2_dirname.split('/')[-1] if '/' in tp2_path else tp2_folder
    # WeiDU path uses backslashes
    wp = tp2_path.replace('/', '\\')

    # Build component objects
    co = []
    for comp in components:
        name = comp['name']
        # Skip @reference names we can't resolve
        if name.startswith('@'):
            name = f"Component {comp['cn']}"

        entry = {
            'n': name,
            'cn': comp['cn'],
            'wf': wf,
            'wp': wp,
            'wc': comp['cn'],
            'wq': 'lcc-github',
        }

        if comp.get('group'):
            entry['g'] = comp['group']

        co.append(entry)

    # If no components found, create a single default component
    if not co:
        co = [{
            'n': candidate['name'],
            'cn': 0,
            'wf': wf,
            'wp': wp,
            'wc': 0,
            'wq': 'lcc-github-fallback',
        }]

    detail = {
        'i': next_id,
        't': tp2_folder,
        'ord': 900,
        'n': candidate['name'],
        'c': candidate['category_mapped'],
        'co': co,
    }

    if langs:
        detail['langs'] = langs

    return detail


# ---- Main -----------------------------------------------------------------

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data, indent=2):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser(description='Populate mod files from GitHub TP2s')
    parser.add_argument('--write', action='store_true', help='Create files (default: dry run)')
    parser.add_argument('--limit', type=int, default=0, help='Process only first N candidates')
    parser.add_argument('--safe1', action='store_true', help='Include safe=1 candidates too')
    args = parser.parse_args()

    if not args.write:
        print("=== DRY RUN (use --write to create files) ===\n")

    # Load candidates
    candidates = load_json(CANDIDATES_PATH)
    catalog = load_json(CATALOG_PATH)
    index = load_json(INDEX_PATH)

    # Filter to candidates with GitHub URLs
    gh_candidates = []
    for c in candidates:
        if args.safe1 or c['safe'] >= 2:
            gh_url = next((u for u in c.get('urls', []) if 'github.com' in u), None)
            if gh_url:
                owner, repo = parse_github_url(gh_url)
                if owner and repo:
                    c['_gh_owner'] = owner
                    c['_gh_repo'] = repo
                    gh_candidates.append(c)

    if args.limit:
        gh_candidates = gh_candidates[:args.limit]

    print(f"Candidates with GitHub URLs: {len(gh_candidates)}")

    # Track results
    next_id = max(int(k) for k in catalog.keys()) + 1
    created = 0
    skipped = 0
    failed = 0
    no_tp2 = 0
    results = {'created': [], 'failed': [], 'no_tp2': [], 'skipped': []}

    for i, cand in enumerate(gh_candidates):
        tp2_name = cand['tp2']
        owner = cand['_gh_owner']
        repo = cand['_gh_repo']

        # Skip if detail file already exists
        detail_path = os.path.join(MODS_DIR, f"{tp2_name}.json")
        if os.path.exists(detail_path):
            skipped += 1
            results['skipped'].append(tp2_name)
            continue

        # Also skip if already in catalog (by t value)
        existing_t = {load_json(os.path.join(MODS_DIR, fn)).get('t', '').lower()
                      for fn_id, fn in catalog.items()
                      if os.path.exists(os.path.join(MODS_DIR, fn))}
        if tp2_name.lower() in existing_t:
            skipped += 1
            results['skipped'].append(tp2_name)
            continue

        progress = f"[{i+1}/{len(gh_candidates)}]"
        safe_name = cand['name'][:50].encode('ascii', 'replace').decode('ascii')
        print(f"  {progress} {safe_name} ({owner}/{repo}) ...", end=' ', flush=True)

        # Rate limiting: ~0.5s between API calls
        if i > 0:
            time.sleep(0.5)

        # Find TP2 and TRA files
        tp2_files, tra_files = find_tp2_in_repo(owner, repo)
        if not tp2_files:
            print("no tp2 found")
            no_tp2 += 1
            results['no_tp2'].append(tp2_name)
            continue

        # Pick the best TP2
        tp2_path = pick_best_tp2(tp2_files, tp2_name)
        if not tp2_path:
            print("no suitable tp2")
            no_tp2 += 1
            results['no_tp2'].append(tp2_name)
            continue

        # Fetch TP2 content
        content = fetch_tp2_content(owner, repo, tp2_path)
        if not content:
            print("fetch failed")
            failed += 1
            results['failed'].append(tp2_name)
            continue

        # Fetch TRA file for @ref resolution (if available)
        tra_strings = {}
        if tra_files:
            # Pick setup.tra from English folder
            best_tra = tra_files[0]
            tra_content = fetch_tp2_content(owner, repo, best_tra)
            if tra_content:
                tra_strings = parse_tra_file(tra_content)

        # Parse and generate detail
        try:
            detail = generate_detail(cand, content, tp2_path, next_id, tra_strings)
        except Exception as e:
            print(f"parse error: {e}")
            failed += 1
            results['failed'].append(tp2_name)
            continue

        comp_count = len(detail.get('co', []))
        lang_count = len(detail.get('langs', {}))
        print(f"{comp_count} components, {lang_count} langs")

        if args.write:
            # Add metadata fields to detail file (single source of truth)
            detail['u'] = cand.get('url_best', '')
            detail['a'] = ', '.join(cand.get('authors', []))
            # Write detail file
            save_json(detail_path, detail)
            # Update catalog
            catalog[str(next_id)] = f"{tp2_name}.json"
            # Update index with minimal entry
            idx_entry = {
                'i': next_id,
                't': tp2_name,
                'n': cand['name'],
                'c': cand['category_mapped'],
                'ord': 900,
                'cc': comp_count,
                'u': detail['u'],
                'a': detail['a'],
            }
            if detail.get('langs'):
                idx_entry['langs'] = detail['langs']
            index.append(idx_entry)

        created += 1
        results['created'].append(tp2_name)
        next_id += 1

    # Save catalog and index
    if args.write and created > 0:
        save_json(CATALOG_PATH, catalog)
        save_json(INDEX_PATH, index)
        print(f"\nUpdated _catalog.json and mods-index.json")

    # Summary
    print(f"\n=== SUMMARY ===")
    print(f"  Processed: {len(gh_candidates)}")
    print(f"  Created:   {created}")
    print(f"  Skipped:   {skipped} (already exist)")
    print(f"  No TP2:    {no_tp2}")
    print(f"  Failed:    {failed}")

    if results['no_tp2']:
        print(f"\n  No TP2 found for: {', '.join(results['no_tp2'][:20])}")
        if len(results['no_tp2']) > 20:
            print(f"    ... and {len(results['no_tp2']) - 20} more")

    if results['failed']:
        print(f"\n  Failed: {', '.join(results['failed'][:20])}")

    if not args.write and created > 0:
        print(f"\nRun with --write to create {created} detail files.")


if __name__ == '__main__':
    main()
