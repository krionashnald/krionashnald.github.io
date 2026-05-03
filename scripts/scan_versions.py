#!/usr/bin/env python3
"""
Scan GitHub repos for release/push info and update version_cache.json.

Reads gh.o (owner) and gh.r (repo) from per-mod detail files via _catalog.json,
then queries the GitHub API for stars, pushed date, archive status, and latest
release info.  Merges results into version_cache.json.

Usage:
    python scripts/scan_versions.py                          # dry run
    python scripts/scan_versions.py --write                  # update version_cache.json

Requires GITHUB_TOKEN env var for API access (avoids rate limits).
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
MODS_DIR = os.path.join(DATA_DIR, 'mods')
CATALOG_PATH = os.path.join(MODS_DIR, '_catalog.json')
CACHE_PATH = os.path.join(DATA_DIR, 'version_cache.json')

GITHUB_API = 'https://api.github.com'
TOKEN = os.environ.get('GITHUB_TOKEN', '')


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def gh_get(url):
    """Make an authenticated GitHub API GET request."""
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'infinity-mod-forge'}
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except urllib.error.URLError:
        return None


def scan_repo(owner, repo):
    """Fetch repo metadata and latest release from GitHub API."""
    # Repo info
    info = gh_get(f'{GITHUB_API}/repos/{owner}/{repo}')
    if not info:
        return None

    result = {
        'stars': info.get('stargazers_count', 0),
        'pushed': (info.get('pushed_at') or '')[:10],
        'archived': info.get('archived', False),
        'description': (info.get('description') or '')[:200],
    }

    # Latest release
    release = gh_get(f'{GITHUB_API}/repos/{owner}/{repo}/releases/latest')
    if release and not release.get('draft'):
        result['tag'] = release.get('tag_name', '')
        result['release_name'] = release.get('name', '')
        result['release_date'] = (release.get('published_at') or '')[:10]
        result['body'] = (release.get('body') or '')[:2000]
        result['release_url'] = release.get('html_url', '')
    else:
        result['tag'] = ''
        result['release_name'] = ''
        result['release_date'] = ''
        result['body'] = ''
        result['release_url'] = ''

    result['checked'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return result


def collect_gh_repos():
    """Read all gh.o/gh.r pairs from per-mod detail files."""
    catalog = load_json(CATALOG_PATH)
    repos = {}  # "owner/repo" -> mod_id

    for mod_id_str, filename in catalog.items():
        fp = os.path.join(MODS_DIR, filename)
        if not os.path.exists(fp):
            continue
        detail = load_json(fp)
        gh = detail.get('gh')
        if not gh or not gh.get('o') or not gh.get('r'):
            continue
        key = f"{gh['o']}/{gh['r']}"
        repos[key] = detail.get('i', int(mod_id_str))

    return repos


def main():
    write = '--write' in sys.argv

    if not TOKEN:
        print("WARNING: GITHUB_TOKEN not set — API rate limit is 60 req/hr")

    repos = collect_gh_repos()
    print(f"Found {len(repos)} GitHub repos from detail files")

    cache = load_json(CACHE_PATH) if os.path.exists(CACHE_PATH) else {}
    updated = 0
    errors = 0

    for key, mod_id in sorted(repos.items()):
        owner, repo = key.split('/', 1)
        try:
            result = scan_repo(owner, repo)
        except Exception as e:
            print(f"  ERROR {key}: {e}")
            errors += 1
            continue

        if result is None:
            print(f"  SKIP {key}: 404 or unreachable")
            errors += 1
            continue

        result['mod_id'] = mod_id

        # Preserve fields from existing cache entry
        existing = cache.get(key, {})
        if 'installed' in existing:
            result['installed'] = existing['installed']

        old_tag = existing.get('tag', '')
        new_tag = result.get('tag', '')
        changed = old_tag != new_tag

        cache[key] = result
        updated += 1

        if changed and new_tag:
            print(f"  {key}: {old_tag or '(none)'} -> {new_tag}")

    print(f"\nScanned: {updated}, Errors: {errors}")

    if write:
        save_json(CACHE_PATH, cache)
        print(f"Wrote {CACHE_PATH}")
    else:
        print("Dry run. Use --write to update.")


if __name__ == '__main__':
    main()
