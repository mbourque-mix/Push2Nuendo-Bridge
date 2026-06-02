"""
scanner.py — VST3/AU Plugin Scanner

Scans plugin directories to discover plugins and extract their parameters.
Uses Spotify's pedalboard library to load each plugin and read its parameter list.

Default plugin directories:
  macOS VST3:  /Library/Audio/Plug-Ins/VST3/, ~/Library/Audio/Plug-Ins/VST3/
               + Steinberg factory location (/Library/Application Support/Steinberg)
  macOS AU:    (handled by pedalboard automatically)
  Windows VST3: C:/Program Files/Common Files/VST3/
                + Steinberg factory plugins bundled with Cubase/Nuendo
                  (C:/Program Files/Steinberg, C:/Program Files/Common Files/Steinberg/VST3)

Steinberg ships its factory plugins (Frequency, Compressor, Retrologue,
Padshop, Groove Agent SE, HALion Sonic, …) inside the application install
tree, NOT in the shared third-party VST3 folder, so those roots are scanned
recursively as well. Non-existent directories are skipped silently.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default VST3 directories per platform
DEFAULT_VST3_DIRS = {
    "darwin": [
        "/Library/Audio/Plug-Ins/VST3",
        os.path.expanduser("~/Library/Audio/Plug-Ins/VST3"),
        # Stock Cubase/Nuendo plug-ins ship INSIDE the app bundle on macOS:
        #   /Applications/Nuendo 15.app/Contents/VST3
        # The "*" makes the path version-independent (Nuendo 14/15/…, Cubase …,
        # even an un-numbered "Nuendo.app"). Glob patterns are expanded below.
        "/Applications/Nuendo*.app/Contents/VST3",
        "/Applications/Cubase*.app/Contents/VST3",
        # Other Steinberg factory locations (presets/components).
        "/Library/Application Support/Steinberg/Components",
        "/Library/Application Support/Steinberg/VST3",
    ],
    "win32": [
        "C:/Program Files/Common Files/VST3",
        # Steinberg factory plugins bundled with Cubase/Nuendo — these live
        # in the app install tree, not the shared VST3 folder. The root is
        # scanned recursively so any version (Cubase 13/14/15, Nuendo …) works.
        "C:/Program Files/Steinberg",
        "C:/Program Files/Common Files/Steinberg/VST3",
    ],
    "linux": [
        "/usr/lib/vst3",
        os.path.expanduser("~/.vst3"),
    ],
}

# Filenames to skip during discovery: multi-plugin "shells" that pedalboard
# cannot enumerate standalone (they require the host/activation and crash the
# scanner). Their individual plugins are mappable via the bridge's DirectAccess
# capture (Shift+Browse in Inserts mode) instead. Matched case-insensitively as
# a substring of the file name.
SKIP_FILENAME_PATTERNS = ("WaveShell",)

# Cache directory
CACHE_DIR = Path.home() / ".push2bridge"
CACHE_FILE = CACHE_DIR / "plugin_cache.json"
MAPPINGS_DIR = CACHE_DIR / "mappings"


def get_default_vst3_dirs():
    """Return default VST3 directories for the current platform."""
    return DEFAULT_VST3_DIRS.get(sys.platform, [])


def discover_vst3_plugins(extra_dirs=None):
    """Discover all .vst3 files in the given directories.
    
    Returns a list of absolute paths to .vst3 bundles/files.
    """
    raw_dirs = list(get_default_vst3_dirs())  # copy — never mutate the module list
    if extra_dirs:
        raw_dirs.extend(extra_dirs)

    # Expand glob patterns (e.g. version-independent app-bundle paths like
    # "/Applications/Nuendo*.app/Contents/VST3"). glob only returns existing
    # matches, so non-pattern entries pass through unchanged.
    import glob as _glob
    dirs = []
    for d in raw_dirs:
        if any(ch in d for ch in "*?["):
            matches = sorted(_glob.glob(d))
            if matches:
                dirs.extend(matches)
            else:
                logger.info(f"No match for pattern: {d}")
        else:
            dirs.append(d)

    plugins = []
    for d in dirs:
        d = Path(d)
        if not d.exists():
            logger.info(f"Skipping non-existent directory: {d}")
            continue
        # VST3 plugins are .vst3 bundles (directories on macOS, files on Windows)
        for item in d.rglob("*.vst3"):
            low = item.name.lower()
            if any(pat.lower() in low for pat in SKIP_FILENAME_PATTERNS):
                logger.info(f"Skipping un-scannable shell: {item.name} "
                            f"(use DirectAccess capture to map its plugins)")
                continue
            plugins.append(str(item))
            logger.debug(f"Found: {item.name}")
    
    # Deduplicate by filename (a plugin can appear in several scanned roots,
    # e.g. Steinberg factory copy + Common Files copy). Keep the first hit and
    # log the rest so the count is explainable.
    seen = {}
    unique = []
    for p in plugins:
        name = Path(p).name
        if name not in seen:
            seen[name] = p
            unique.append(p)
        else:
            logger.info(f"Skipping duplicate '{name}': {p} "
                        f"(already found at {seen[name]})")

    return sorted(unique, key=lambda p: Path(p).stem.lower())


def scan_plugin_parameters(plugin_path, timeout=60):
    """Load a plugin file with pedalboard and extract its parameters.

    Handles multi-plugin VST3 "shells" (e.g. Waves WaveShell): each contained
    plugin is enumerated and loaded by name. Returns a LIST of plugin dicts
    (one per contained plugin; a normal single-plugin file yields a 1-item list
    named after the file). Uses a subprocess with timeout to isolate crashes.
    """
    import subprocess

    path = Path(plugin_path)
    stem = path.stem

    # Subprocess script: enumerate sub-plugins, scan each, output a JSON LIST.
    script = f'''
import json, sys, os, math
os.environ["QT_QPA_PLATFORM"] = "offscreen"
PATH = {str(path)!r}
STEM = {stem!r}
def safe_float(v, default=0.0):
    try:
        f = float(v)
        return default if (math.isinf(f) or math.isnan(f)) else f
    except:
        return default
def scan_one(nm):
    from pedalboard import load_plugin
    plugin = load_plugin(PATH, plugin_name=nm) if nm else load_plugin(PATH)
    params = []
    for i, (name, param) in enumerate(plugin.parameters.items()):
        p = {{"index": i, "name": name}}
        p["label"] = getattr(param, "label", name)
        p["default_value"] = safe_float(getattr(param, "default_raw_value", 0.0))
        p["min_value"] = safe_float(getattr(param, "min_value", 0.0))
        p["max_value"] = safe_float(getattr(param, "max_value", 1.0), 1.0)
        p["units"] = getattr(param, "units", "") or ""
        p["is_boolean"] = bool(getattr(param, "is_boolean", False))
        p["is_discrete"] = bool(getattr(param, "is_discrete", False))
        params.append(p)
    r = {{"name": nm or STEM, "path": PATH, "type": "VST3",
          "is_instrument": bool(getattr(plugin, "is_instrument", False)),
          "is_effect": bool(getattr(plugin, "is_effect", True)),
          "parameter_count": len(params), "parameters": params}}
    del plugin
    return r
names = []
try:
    from pedalboard import VST3Plugin
    names = VST3Plugin.get_plugin_names_for_file(PATH)
except Exception:
    names = []
results = []
if names and len(names) > 1:
    for nm in names:
        try:
            results.append(scan_one(nm))
        except Exception as e:
            results.append({{"name": nm, "path": PATH, "type": "VST3",
                             "error": str(e), "parameter_count": 0, "parameters": []}})
else:
    try:
        results.append(scan_one(None))
    except Exception as e:
        results.append({{"name": STEM, "path": PATH, "type": "VST3",
                         "error": str(e), "parameter_count": 0, "parameters": []}})
print("@@JSON@@" + json.dumps(results))
'''

    def _err_list(msg):
        return [{
            "name": stem, "path": str(path), "type": "VST3", "error": msg,
            "parameter_count": 0, "parameters": [], "scanned_at": time.time(),
        }]

    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        )
        stdout = proc.stdout.strip()
        # Find our tagged JSON line (skip plugin debug spam)
        for line in reversed(stdout.split("\n")):
            line = line.strip()
            if line.startswith("@@JSON@@"):
                data = json.loads(line[len("@@JSON@@"):])
                now = time.time()
                for d in data:
                    d["scanned_at"] = now
                return data
        return _err_list("Could not parse scanner output")
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout scanning {stem} ({timeout}s)")
        return _err_list(f"Timeout ({timeout}s)")
    except Exception as e:
        logger.warning(f"Failed to scan {stem}: {e}")
        return _err_list(str(e))


def full_scan(extra_dirs=None, force=False, retry_errors=False,
              progress_cb=None, should_cancel=None):
    """Scan all plugins and cache the results.

    If force=False, only scans plugins not already in cache.
    If retry_errors=True, re-scans plugins that previously had errors.
    progress_cb(done, total, name): optional callback after each plugin.
    should_cancel(): optional callable; if it returns True the scan stops
                     early (partial results are still cached).
    Returns the complete plugin database.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing cache
    cache = {}
    if CACHE_FILE.exists() and not force:
        try:
            cache = json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            cache = {}
    
    # Discover plugins
    plugin_paths = discover_vst3_plugins(extra_dirs)
    logger.info(f"Found {len(plugin_paths)} VST3 plugins")
    
    # Scan new or updated plugins
    scanned = 0
    failed = 0
    skipped = 0
    total_to_scan = len(plugin_paths)
    cancelled = False
    for idx, path in enumerate(plugin_paths):
        name = Path(path).stem

        # Cooperative cancellation between plugins
        if should_cancel and should_cancel():
            logger.info("Scan cancelled by user")
            cancelled = True
            break

        if progress_cb:
            try:
                progress_cb(idx, total_to_scan, name)
            except Exception:
                pass

        # Skip if already cached and not forced
        if name in cache and not force:
            # Retry errors if requested
            if retry_errors and cache[name].get("error"):
                pass  # Fall through to rescan
            else:
                try:
                    mtime = os.path.getmtime(path)
                    if mtime <= cache[name].get("scanned_at", 0):
                        skipped += 1
                        continue
                except OSError:
                    skipped += 1
                    continue
        
        logger.info(f"Scanning [{idx+1}/{total_to_scan}]: {name}...")
        results = scan_plugin_parameters(path)  # list (1 item, or N for shells)
        for result in results:
            rname = result.get("name", name)
            cache[rname] = result
            if result.get("error"):
                failed += 1
                logger.warning(f"  ✗ {rname}: {result['error']}")
            else:
                scanned += 1
                logger.info(f"  ✓ {rname}: {result['parameter_count']} params")
        # For a multi-plugin shell the sub-plugins are keyed by their own names,
        # so leave a marker under the file stem to allow skipping next time.
        if len(results) > 1 and name not in cache:
            cache[name] = {
                "name": name, "is_shell": True, "path": str(path),
                "members": [r.get("name") for r in results],
                "parameter_count": 0, "parameters": [], "scanned_at": time.time(),
            }
    
    # Save cache
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except IOError as e:
        logger.error(f"Failed to save cache: {e}")
    
    if progress_cb:
        try:
            progress_cb(total_to_scan, total_to_scan, "")
        except Exception:
            pass

    total = len(cache)
    status = "cancelled" if cancelled else "complete"
    logger.info(f"Scan {status}: {scanned} new, {failed} failed, {total} total")

    return cache


def get_cached_plugins():
    """Return the cached plugin database without scanning."""
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {}


# ── Mapping management ──

def get_mapping(plugin_name):
    """Load a mapping for a plugin, or None if it doesn't exist."""
    mapping_file = MAPPINGS_DIR / f"{plugin_name}.json"
    if mapping_file.exists():
        try:
            return json.loads(mapping_file.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_mapping(plugin_name, mapping_data):
    """Save a mapping for a plugin."""
    MAPPINGS_DIR.mkdir(parents=True, exist_ok=True)
    mapping_file = MAPPINGS_DIR / f"{plugin_name}.json"
    mapping_data["plugin"] = plugin_name
    mapping_data["updated_at"] = time.time()
    mapping_file.write_text(json.dumps(mapping_data, indent=2))
    return mapping_data


def delete_mapping(plugin_name):
    """Delete a mapping for a plugin."""
    mapping_file = MAPPINGS_DIR / f"{plugin_name}.json"
    if mapping_file.exists():
        mapping_file.unlink()
        return True
    return False


def export_all_mappings():
    """Return all saved mappings as a single bundle dict:
    { "version": 1, "mappings": { plugin_name: mapping_data, ... } }."""
    out = {}
    if MAPPINGS_DIR.exists():
        for f in MAPPINGS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text())
                out[data.get("plugin", f.stem)] = data
            except (json.JSONDecodeError, IOError):
                pass
    return {"version": 1, "mappings": out}


def import_mappings(bundle, overwrite=True):
    """Import mappings from a bundle (as produced by export_all_mappings, or a
    bare {plugin: mapping} dict). Returns (imported, skipped) counts."""
    mappings = bundle.get("mappings", bundle) if isinstance(bundle, dict) else {}
    imported = skipped = 0
    for name, data in mappings.items():
        if not isinstance(data, dict):
            skipped += 1
            continue
        if not overwrite and get_mapping(name) is not None:
            skipped += 1
            continue
        try:
            save_mapping(name, dict(data))
            imported += 1
        except Exception:
            skipped += 1
    return imported, skipped


def list_mappings():
    """List all saved mappings."""
    if not MAPPINGS_DIR.exists():
        return []
    mappings = []
    for f in MAPPINGS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            mappings.append({
                "plugin": data.get("plugin", f.stem),
                "pages": len(data.get("pages", [])),
                "updated_at": data.get("updated_at", 0),
            })
        except (json.JSONDecodeError, IOError):
            pass
    return sorted(mappings, key=lambda m: m["plugin"].lower())


if __name__ == "__main__":
    import argparse
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    parser = argparse.ArgumentParser(description="Push2 Plugin Scanner")
    parser.add_argument("--force", action="store_true", help="Force rescan all plugins")
    parser.add_argument("--retry", action="store_true", help="Retry plugins that had errors")
    parser.add_argument("--extra-dir", action="append", help="Additional VST3 directory to scan")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics only")
    args = parser.parse_args()
    
    if args.stats:
        db = get_cached_plugins()
        total = len(db)
        with_params = sum(1 for p in db.values() if p.get('parameter_count', 0) > 0)
        with_error = sum(1 for p in db.values() if p.get('error'))
        print(f"\nPlugin Cache Statistics:")
        print(f"  Total:       {total}")
        print(f"  With params: {with_params}")
        print(f"  Errors:      {with_error}")
        print(f"  No params:   {total - with_params - with_error}")
        if with_error > 0:
            print(f"\nPlugins with errors:")
            for name, p in sorted(db.items()):
                if p.get('error'):
                    err = p['error'][:60]
                    print(f"  ✗ {name}: {err}")
    else:
        print("Scanning plugins...")
        db = full_scan(extra_dirs=args.extra_dir, force=args.force, retry_errors=args.retry)
        total = len(db)
        with_params = sum(1 for p in db.values() if p.get('parameter_count', 0) > 0)
        with_error = sum(1 for p in db.values() if p.get('error'))
        print(f"\nDone: {with_params} scanned, {with_error} errors, {total} total")
