#!/usr/bin/env python3
"""
Generate a mod-forge.json scaffold from a WeiDU tp2 file.

Parses LANGUAGE and BEGIN/DESIGNATED/SUBCOMPONENT/LABEL blocks from a tp2
and produces a mod-forge.json that mod authors can review, fill in missing
fields (summary, tags, conflicts, etc.), and commit to their repository.

Usage:
    python tp2_to_modjson.py path/to/setup-mymod.tp2
    python tp2_to_modjson.py path/to/setup-mymod.tp2 -o mod-forge.json
    python tp2_to_modjson.py path/to/setup-mymod.tp2 --pretty

The output includes the $schema reference so VS Code provides autocompletion.
"""

import argparse
import json
import os
import re
import sys

SCHEMA_URL = "https://raw.githubusercontent.com/Anprionsa/infinity-mod-forge/main/schemas/mod-forge.schema.json"

# ---- Language mapping (shared with populate_from_github.py) -----------------

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


# ---- TP2 parsing (shared with populate_from_github.py) ----------------------

def strip_comments(text):
    """Remove WeiDU block comments /* ... */ and line comments //."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    lines = []
    for line in text.split('\n'):
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
    auto_num = 0

    begin_pattern = re.compile(
        r'^\s*BEGIN\s+(?:~([^~]*)~|"([^"]*)"|(@\d+))',
        re.MULTILINE | re.IGNORECASE
    )

    for m in begin_pattern.finditer(text):
        name = m.group(1) or m.group(2) or m.group(3) or ''
        name = name.strip()

        after = text[m.end():m.end() + 300]
        desig_m = re.search(r'DESIGNATED\s+(\d+)', after, re.IGNORECASE)

        if desig_m:
            cn = int(desig_m.group(1))
            auto_num = cn + 1
        else:
            cn = auto_num
            auto_num += 1

        sub_m = re.search(
            r'SUBCOMPONENT\s+(?:~([^~]*)~|"([^"]*)")',
            after, re.IGNORECASE
        )
        group = None
        if sub_m:
            group = (sub_m.group(1) or sub_m.group(2) or '').strip()

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


# ---- Version extraction -----------------------------------------------------

def extract_version(text):
    """Try to extract VERSION from the tp2."""
    m = re.search(
        r'^\s*VERSION\s+(?:~([^~]*)~|"([^"]*)")',
        text, re.MULTILINE | re.IGNORECASE
    )
    if m:
        return (m.group(1) or m.group(2) or '').strip()
    return None


# ---- TP2 folder name extraction ---------------------------------------------

def extract_tp2_folder(text, filename):
    """Determine the tp2 folder name from BACKUP or filename."""
    # Try BACKUP directive
    m = re.search(
        r'^\s*BACKUP\s+(?:~([^~]*)~|"([^"]*)")',
        text, re.MULTILINE | re.IGNORECASE
    )
    if m:
        backup_path = (m.group(1) or m.group(2) or '').strip()
        parts = backup_path.replace("\\", "/").split("/")
        if parts:
            return parts[0]

    # Fall back to filename: setup-MODNAME.tp2 → MODNAME
    base = os.path.basename(filename)
    m2 = re.match(r'setup[_-]?(.+)\.tp2$', base, re.IGNORECASE)
    if m2:
        return m2.group(1)

    return os.path.splitext(base)[0]


# ---- Main -------------------------------------------------------------------

def generate_modjson(tp2_path):
    """Parse a tp2 file and generate a mod-forge.json dict."""
    with open(tp2_path, 'r', encoding='utf-8', errors='replace') as f:
        raw = f.read()

    text = strip_comments(raw)
    tp2_folder = extract_tp2_folder(text, tp2_path)
    version = extract_version(text)
    lang_tuples = parse_tp2_languages(text)
    langs = build_langs_dict(lang_tuples)
    parsed_comps = parse_tp2_components(text)

    result = {
        "$schema": SCHEMA_URL,
        "tp2": tp2_folder,
        "name": "",
        "author": "",
    }

    if version:
        result["version"] = version

    result["homepage"] = ""
    result["summary"] = ""
    result["games"] = []
    result["tags"] = []

    if langs:
        result["languages"] = langs

    components = []
    for comp in parsed_comps:
        entry = {
            "name": comp['name'],
            "number": comp['cn'],
        }
        if comp.get('group'):
            entry["group"] = comp['group']
        if comp.get('label'):
            entry["label"] = comp['label']
        components.append(entry)

    result["components"] = components

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Generate a mod-forge.json scaffold from a WeiDU tp2 file."
    )
    parser.add_argument("tp2", help="Path to the tp2 file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--pretty", action="store_true",
                        help="Pretty-print with 2-space indent (default)")

    args = parser.parse_args()

    if not os.path.isfile(args.tp2):
        print(f"Error: {args.tp2} not found", file=sys.stderr)
        sys.exit(1)

    result = generate_modjson(args.tp2)

    output = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output + '\n')
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == '__main__':
    main()
