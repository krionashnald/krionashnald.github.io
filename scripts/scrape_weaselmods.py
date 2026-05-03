#!/usr/bin/env python3
"""
Scrape Weasel Mods download pages for version info and update version_cache.json.

Reads mod URLs from mods-index.json, finds entries pointing to weaselmods.net,
and scrapes each download page for the latest version string.

Usage:
    python scripts/scrape_weaselmods.py                # dry run
    python scripts/scrape_weaselmods.py --write        # update version_cache.json
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, '..', 'data')
INDEX_PATH = os.path.join(DATA_DIR, 'mods-index.json')
CACHE_PATH = os.path.join(DATA_DIR, 'version_cache.json')


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_page(url):
    """Fetch a URL and return the HTML as a string."""
    headers = {'User-Agent': 'infinity-mod-forge/1.0'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None


def extract_version(html):
    """Try to extract a version string from a Weasel Mods download page."""
    # Look for common patterns: "Version: X.Y", "v1.2.3", etc.
    patterns = [
        r'[Vv]ersion[:\s]+([0-9][0-9a-zA-Z._-]*)',
        r'\bv(\d+(?:\.\d+)+[a-zA-Z0-9._-]*)\b',
    ]
    for pat in patterns:
        m = re.search(pat, html)
        if m:
            return m.group(1) if m.group(1)[0].isdigit() else m.group(1)
    return ''


def main():
    write = '--write' in sys.argv

    index = load_json(INDEX_PATH)
    cache = load_json(CACHE_PATH) if os.path.exists(CACHE_PATH) else {}

    # Find mods with weaselmods URLs
    weasel_mods = []
    for entry in index:
        url = entry.get('u', '')
        if 'weaselmods.net' in url:
            weasel_mods.append(entry)

    print(f"Found {len(weasel_mods)} mods with Weasel Mods URLs")

    updated = 0
    errors = 0

    for mod in weasel_mods:
        url = mod['u']
        cache_key = f"weaselmods:{mod['t']}"

        html = fetch_page(url)
        if html is None:
            print(f"  ERROR {mod['t']}: failed to fetch {url}")
            errors += 1
            continue

        version = extract_version(html)
        existing = cache.get(cache_key, {})
        old_ver = existing.get('tag', '')

        entry = {
            'tag': version,
            'release_url': url,
            'mod_id': mod['i'],
            'checked': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        }

        # Preserve existing fields
        for k in ('stars', 'pushed', 'archived', 'description', 'release_name',
                   'release_date', 'body', 'installed'):
            if k in existing:
                entry[k] = existing[k]

        cache[cache_key] = entry
        updated += 1

        if old_ver != version and version:
            print(f"  {mod['t']}: {old_ver or '(none)'} -> {version}")

    print(f"\nScraped: {updated}, Errors: {errors}")

    if write:
        save_json(CACHE_PATH, cache)
        print(f"Wrote {CACHE_PATH}")
    else:
        print("Dry run. Use --write to update.")


if __name__ == '__main__':
    main()
