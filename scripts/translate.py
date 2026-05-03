#!/usr/bin/env python3
"""
Infinity Mod Forge Translation Script

Generates translation overlay files for the Infinity Mod Forge UI and mod data.
Uses DeepL API for European languages, with Claude API support for future use.

Usage:
    python scripts/translate.py --lang de --api deepl
    python scripts/translate.py --lang de --api deepl --scope ui
    python scripts/translate.py --lang de --api deepl --scope mods
    python scripts/translate.py --lang de --api deepl --force
    python scripts/translate.py --lang de --dry-run

Environment:
    DEEPL_API_KEY=xxx          # Required for --api deepl
    ANTHROPIC_API_KEY=xxx      # Required for --api claude (future)
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

# Project paths
PROJ_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJ_ROOT / "data"
LANG_DIR = DATA_DIR / "lang"
MODS_DIR = DATA_DIR / "mods"

# Supported languages and their DeepL target codes
LANG_MAP = {
    "de": "DE",
    "fr": "FR",
    "pl": "PL",
    "ru": "RU",
    # Future: add more as needed
    # "es": "ES", "it": "IT", "pt-br": "PT-BR",
    # "zh-cn": "ZH", "ko": "KO", "ja": "JA",
}

def sha256(text):
    """Compute SHA-256 hash of a string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_json(path):
    """Load a JSON file, return None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_json(path, data):
    """Save data as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Wrote {path.name} ({path.stat().st_size:,} bytes)")


def load_cache(lang):
    """Load translation cache for a language."""
    path = LANG_DIR / f".cache-{lang}.json"
    return load_json(path) or {}


def save_cache(lang, cache):
    """Save translation cache for a language."""
    path = LANG_DIR / f".cache-{lang}.json"
    save_json(path, cache)


def load_dnt():
    """Load don't-translate terms list."""
    data = load_json(LANG_DIR / "dnt.json")
    if not data:
        return []
    return data.get("terms", [])


def wrap_dnt(text, dnt_terms):
    """Wrap don't-translate terms in XML tags for DeepL.
    Also escapes XML special chars (&, <, >) in the text body."""
    # First escape XML special characters (but not our tags)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for term in sorted(dnt_terms, key=len, reverse=True):
        # Escape the term the same way for matching
        escaped_term = term.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        pattern = re.compile(re.escape(escaped_term), re.IGNORECASE)
        text = pattern.sub(lambda m: f"<keep>{m.group()}</keep>", text)
    return text


def unwrap_dnt(text):
    """Remove <keep> tags and unescape XML entities from translated text."""
    text = re.sub(r"<keep>(.*?)</keep>", r"\1", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return text


# ─── DeepL API ───

def translate_deepl(texts, target_lang, api_key, dnt_terms=None):
    """Translate a batch of texts using DeepL API."""
    import urllib.request
    import urllib.parse

    if not texts:
        return []

    # Determine API endpoint (free vs pro key)
    if ":fx" in api_key:
        url = "https://api-free.deepl.com/v2/translate"
    else:
        url = "https://api.deepl.com/v2/translate"

    # Wrap DNT terms
    processed = []
    for text in texts:
        if dnt_terms:
            processed.append(wrap_dnt(text, dnt_terms))
        else:
            processed.append(text)

    # DeepL supports max 50 texts per request, use 25 for reliability
    BATCH_SIZE = 25
    results = []

    for i in range(0, len(processed), BATCH_SIZE):
        batch = processed[i:i + BATCH_SIZE]

        params = {
            "target_lang": target_lang,
            "tag_handling": "xml",
            "ignore_tags": "keep",
        }

        # Build form data with multiple 'text' fields
        form_parts = []
        for key, value in params.items():
            form_parts.append(f"{urllib.parse.quote(key)}={urllib.parse.quote(str(value))}")
        for text in batch:
            form_parts.append(f"text={urllib.parse.quote(text)}")
        form_data = "&".join(form_parts).encode("utf-8")

        req = urllib.request.Request(url, data=form_data, method="POST")
        req.add_header("Authorization", f"DeepL-Auth-Key {api_key}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for tr in data.get("translations", []):
                    translated = tr.get("text", "")
                    # Unwrap DNT tags
                    translated = unwrap_dnt(translated)
                    results.append(translated)
        except Exception as e:
            print(f"  DeepL API error on batch {i // BATCH_SIZE + 1}: {e}")
            # Fill with empty strings for failed batch
            results.extend([""] * len(batch))

        # Rate limiting: small delay between batches
        if i + BATCH_SIZE < len(processed):
            time.sleep(0.3)

    return results


# ─── String Extraction ───

def extract_ui_strings():
    """Extract UI strings from the English source file."""
    path = LANG_DIR / "ui-en.json"
    data = load_json(path)
    if not data:
        print("ERROR: data/lang/ui-en.json not found. Create it first.")
        sys.exit(1)

    strings = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue
        strings[key] = value
    return strings


def extract_mod_strings():
    """Extract translatable strings from all mod data."""
    # Load index for summaries
    index = load_json(DATA_DIR / "mods-index.json") or []
    catalog = load_json(MODS_DIR / "_catalog.json") or {}

    strings = {}  # {mod_id: {field: value}}

    for mod in index:
        mod_id = str(mod.get("i", ""))
        if not mod_id:
            continue

        entry = {}

        # Index-level fields
        if mod.get("n"):
            entry["n"] = mod["n"]
        if mod.get("sum"):
            entry["sum"] = mod["sum"]

        # Component names from index
        comp_names = mod.get("coNames", [])
        if comp_names:
            entry["co"] = {}
            for ci, name in enumerate(comp_names):
                if name:
                    entry["co"][str(ci)] = {"n": name}

        # Load detail file for notes, conflicts, etc.
        if mod_id in catalog:
            detail = load_json(MODS_DIR / catalog[mod_id])
            if detail:
                # Mod-level notes
                if detail.get("no"):
                    entry["no"] = detail["no"]

                # Component notes from detail
                for ci, comp in enumerate(detail.get("co", [])):
                    if comp.get("no"):
                        if "co" not in entry:
                            entry["co"] = {}
                        if str(ci) not in entry["co"]:
                            entry["co"][str(ci)] = {}
                        entry["co"][str(ci)]["no"] = comp["no"]

                # Conflict reasons
                if detail.get("conflicts"):
                    entry["conflicts"] = {}
                    for idx, conflict in enumerate(detail["conflicts"]):
                        if conflict.get("reason"):
                            entry["conflicts"][str(idx)] = {"reason": conflict["reason"]}

                # Dependency reasons
                if detail.get("dependencies"):
                    entry["deps"] = {}
                    for idx, dep in enumerate(detail["dependencies"]):
                        if dep.get("reason"):
                            entry["deps"][str(idx)] = {"reason": dep["reason"]}

        if entry:
            strings[mod_id] = entry

    return strings


def extract_tool_strings():
    """Extract translatable strings from tools.json."""
    tools = load_json(DATA_DIR / "tools.json") or []
    strings = {}
    for tool in tools:
        tid = tool.get("t", tool.get("n", "")).lower().replace(" ", "_")
        if not tid:
            continue
        entry = {}
        if tool.get("n"):
            entry["n"] = tool["n"]
        if tool.get("desc"):
            entry["desc"] = tool["desc"]
        if entry:
            strings[tid] = entry
    return strings


# ─── Translation Pipeline ───

def flatten_strings(data, prefix=""):
    """Flatten nested dict to flat key-value pairs."""
    result = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_strings(value, full_key))
        elif isinstance(value, str):
            result[full_key] = value
    return result


def unflatten_strings(flat):
    """Unflatten dot-separated keys back to nested dict."""
    result = {}
    for key, value in flat.items():
        parts = key.split(".")
        d = result
        for p in parts[:-1]:
            if p not in d:
                d[p] = {}
            d = d[p]
        d[parts[-1]] = value
    return result


def translate_scope(scope_name, strings, lang, api, api_key, cache, dnt_terms, force=False, dry_run=False):
    """Translate a set of strings, using cache to skip unchanged ones."""
    flat = flatten_strings(strings) if scope_name != "ui" else dict(strings)

    # Determine what needs translation
    to_translate = {}
    skipped_manual = 0
    skipped_cached = 0

    for key, value in flat.items():
        cache_key = f"{scope_name}.{key}"
        src_hash = sha256(value)

        cached = cache.get(cache_key, {})

        # Skip manual overrides
        if cached.get("manual") and not force:
            skipped_manual += 1
            continue

        # Skip if source unchanged
        if cached.get("src_hash") == src_hash and not force:
            skipped_cached += 1
            continue

        to_translate[key] = value

    print(f"\n  [{scope_name}] {len(flat)} total, {len(to_translate)} to translate, "
          f"{skipped_cached} cached, {skipped_manual} manual overrides")

    if dry_run:
        if to_translate:
            print(f"  Would translate {len(to_translate)} strings:")
            for key in list(to_translate.keys())[:10]:
                print(f"    {key}: {to_translate[key][:80]}...")
            if len(to_translate) > 10:
                print(f"    ... and {len(to_translate) - 10} more")
        return None

    if not to_translate:
        return None

    # Translate
    keys = list(to_translate.keys())
    texts = [to_translate[k] for k in keys]

    target_code = LANG_MAP.get(lang, lang.upper())

    if api == "deepl":
        translated = translate_deepl(texts, target_code, api_key, dnt_terms)
    else:
        print(f"  API '{api}' not yet implemented")
        return None

    if len(translated) != len(keys):
        print(f"  WARNING: Got {len(translated)} translations for {len(keys)} strings")
        return None

    # Build result and update cache
    result = {}
    for key, original, trans in zip(keys, texts, translated):
        if trans:
            result[key] = trans
            cache_key = f"{scope_name}.{key}"
            cache[cache_key] = {
                "src_hash": sha256(original),
                "manual": False,
            }

    # Merge with existing overlay (to preserve manually edited strings)
    return result


def main():
    parser = argparse.ArgumentParser(description="Translate Infinity Mod Forge")
    parser.add_argument("--lang", required=True, help="Target language code (de, fr, pl)")
    parser.add_argument("--api", default="deepl", choices=["deepl", "claude"], help="Translation API")
    parser.add_argument("--scope", default="all", choices=["all", "ui", "mods", "tools"], help="What to translate")
    parser.add_argument("--force", action="store_true", help="Force retranslation of all strings")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be translated without calling API")
    args = parser.parse_args()

    lang = args.lang
    if lang not in LANG_MAP and not args.dry_run:
        print(f"WARNING: Language '{lang}' not in LANG_MAP. Will use '{lang.upper()}' as DeepL target.")

    # API key
    api_key = None
    if not args.dry_run:
        if args.api == "deepl":
            api_key = os.environ.get("DEEPL_API_KEY")
            if not api_key:
                print("ERROR: Set DEEPL_API_KEY environment variable")
                sys.exit(1)
        elif args.api == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                print("ERROR: Set ANTHROPIC_API_KEY environment variable")
                sys.exit(1)

    print(f"=== Infinity Mod Forge Translation ===")
    print(f"Language: {lang} | API: {args.api} | Scope: {args.scope} | Force: {args.force}")

    # Load cache and DNT list
    cache = load_cache(lang)
    dnt_terms = load_dnt()
    print(f"Cache entries: {len(cache)} | DNT terms: {len(dnt_terms)}")

    # ── UI Strings ──
    if args.scope in ("all", "ui"):
        ui_strings = extract_ui_strings()
        print(f"\nExtracted {len(ui_strings)} UI strings")

        result = translate_scope("ui", ui_strings, lang, args.api, api_key, cache, dnt_terms, args.force, args.dry_run)

        if result and not args.dry_run:
            # Load existing overlay to preserve manual edits
            existing = load_json(LANG_DIR / f"ui-{lang}.json") or {}
            meta = existing.get("_meta", {})
            meta.update({"lang": lang, "generated": time.strftime("%Y-%m-%d"), "version": meta.get("version", 0) + 1})

            # Merge: existing values are kept, new translations added/updated
            for key, value in result.items():
                cache_key = f"ui.{key}"
                if cache.get(cache_key, {}).get("manual"):
                    continue  # Don't overwrite manual edits
                existing[key] = value

            existing["_meta"] = meta
            save_json(LANG_DIR / f"ui-{lang}.json", existing)

    # ── Mod Data ──
    if args.scope in ("all", "mods"):
        mod_strings = extract_mod_strings()
        print(f"\nExtracted mod data for {len(mod_strings)} mods")

        result = translate_scope("mod", mod_strings, lang, args.api, api_key, cache, dnt_terms, args.force, args.dry_run)

        if result and not args.dry_run:
            # Unflatten back to nested structure
            nested = unflatten_strings(result)

            # Load existing overlay
            existing = load_json(LANG_DIR / f"mods-{lang}.json") or {}
            meta = existing.get("_meta", {})
            meta.update({"lang": lang, "generated": time.strftime("%Y-%m-%d"), "version": meta.get("version", 0) + 1})

            # Deep merge: preserve manual edits
            for mod_id, mod_data in nested.items():
                if mod_id not in existing:
                    existing[mod_id] = {}
                if isinstance(mod_data, dict):
                    for field, value in mod_data.items():
                        if isinstance(value, dict):
                            if field not in existing[mod_id]:
                                existing[mod_id][field] = {}
                            existing[mod_id][field].update(value)
                        else:
                            existing[mod_id][field] = value
                else:
                    existing[mod_id] = mod_data

            existing["_meta"] = meta
            save_json(LANG_DIR / f"mods-{lang}.json", existing)

    # ── Tools ──
    if args.scope in ("all", "tools"):
        tool_strings = extract_tool_strings()
        print(f"\nExtracted {len(tool_strings)} tool entries")

        result = translate_scope("tool", tool_strings, lang, args.api, api_key, cache, dnt_terms, args.force, args.dry_run)

        if result and not args.dry_run:
            nested = unflatten_strings(result)
            existing = load_json(LANG_DIR / f"tools-{lang}.json") or {}
            meta = existing.get("_meta", {})
            meta.update({"lang": lang, "generated": time.strftime("%Y-%m-%d"), "version": meta.get("version", 0) + 1})

            for tid, tdata in nested.items():
                if tid not in existing:
                    existing[tid] = {}
                if isinstance(tdata, dict):
                    existing[tid].update(tdata)
                else:
                    existing[tid] = tdata

            existing["_meta"] = meta
            save_json(LANG_DIR / f"tools-{lang}.json", existing)

    # Save cache
    if not args.dry_run:
        save_cache(lang, cache)
        print(f"\nCache updated: {len(cache)} entries")

    print("\nDone!")


if __name__ == "__main__":
    main()
