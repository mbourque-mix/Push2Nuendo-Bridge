"""
scanner.py — VST3/AU Plugin Scanner

Scans plugin directories to discover plugins and extract their parameters.
Uses Spotify's pedalboard library to load each plugin and read its parameter list.

Default plugin directories:
  macOS VST3:  /Library/Audio/Plug-Ins/VST3/, ~/Library/Audio/Plug-Ins/VST3/
  macOS AU:    (handled by pedalboard automatically)
  Windows VST3: C:/Program Files/Common Files/VST3/
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
    ],
    "win32": [
        "C:/Program Files/Common Files/VST3",
    ],
    "linux": [
        "/usr/lib/vst3",
        os.path.expanduser("~/.vst3"),
    ],
}

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
    dirs = get_default_vst3_dirs()
    if extra_dirs:
        dirs.extend(extra_dirs)
    
    plugins = []
    for d in dirs:
        d = Path(d)
        if not d.exists():
            logger.info(f"Skipping non-existent directory: {d}")
            continue
        # VST3 plugins are .vst3 bundles (directories on macOS, files on Windows)
        for item in d.rglob("*.vst3"):
            plugins.append(str(item))
            logger.debug(f"Found: {item.name}")
    
    # Deduplicate
    seen = set()
    unique = []
    for p in plugins:
        name = Path(p).name
        if name not in seen:
            seen.add(name)
            unique.append(p)
    
    return sorted(unique, key=lambda p: Path(p).stem.lower())


def scan_plugin_parameters(plugin_path, timeout=30):
    """Load a plugin with pedalboard and extract its parameters.
    
    Uses a subprocess with timeout to prevent hanging on badly-behaved plugins.
    Returns a dict with plugin info and parameters, or None if loading fails.
    """
    import subprocess
    
    path = Path(plugin_path)
    plugin_name = path.stem
    
    # Use a subprocess to isolate plugin loading (prevents crashes and hangs)
    script = f'''
import json, sys, os, math
os.environ["QT_QPA_PLATFORM"] = "offscreen"
def safe_float(v, default=0.0):
    try:
        f = float(v)
        if math.isinf(f) or math.isnan(f):
            return default
        return f
    except:
        return default
try:
    from pedalboard import load_plugin
    plugin = load_plugin("{path}")
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
    result = {{
        "name": "{plugin_name}",
        "path": "{path}",
        "type": "VST3",
        "is_instrument": bool(getattr(plugin, "is_instrument", False)),
        "is_effect": bool(getattr(plugin, "is_effect", True)),
        "parameter_count": len(params),
        "parameters": params,
    }}
    del plugin
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({{"error": str(e)}}))
'''
    
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"}
        )
        
        stdout = result.stdout.strip()
        if not stdout:
            return {
                "name": plugin_name, "path": str(path), "type": "VST3",
                "error": "No output from scanner subprocess",
                "parameter_count": 0, "parameters": [], "scanned_at": time.time(),
            }
        
        # Parse the last line of JSON (skip any plugin debug output)
        for line in reversed(stdout.split("\n")):
            line = line.strip()
            if line.startswith("{"):
                data = json.loads(line)
                if "error" in data and "name" not in data:
                    return {
                        "name": plugin_name, "path": str(path), "type": "VST3",
                        "error": data["error"],
                        "parameter_count": 0, "parameters": [], "scanned_at": time.time(),
                    }
                data["scanned_at"] = time.time()
                return data
        
        return {
            "name": plugin_name, "path": str(path), "type": "VST3",
            "error": "Could not parse scanner output",
            "parameter_count": 0, "parameters": [], "scanned_at": time.time(),
        }
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Timeout scanning {plugin_name} ({timeout}s)")
        return {
            "name": plugin_name, "path": str(path), "type": "VST3",
            "error": f"Timeout ({timeout}s)",
            "parameter_count": 0, "parameters": [], "scanned_at": time.time(),
        }
    except Exception as e:
        logger.warning(f"Failed to scan {plugin_name}: {e}")
        return {
            "name": plugin_name, "path": str(path), "type": "VST3",
            "error": str(e),
            "parameter_count": 0, "parameters": [], "scanned_at": time.time(),
        }


def full_scan(extra_dirs=None, force=False, retry_errors=False):
    """Scan all plugins and cache the results.
    
    If force=False, only scans plugins not already in cache.
    If retry_errors=True, re-scans plugins that previously had errors.
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
    for idx, path in enumerate(plugin_paths):
        name = Path(path).stem
        
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
        result = scan_plugin_parameters(path)
        if result:
            cache[name] = result
            if result.get("error"):
                failed += 1
                logger.warning(f"  ✗ {name}: {result['error']}")
            else:
                scanned += 1
                logger.info(f"  ✓ {name}: {result['parameter_count']} params")
    
    # Save cache
    try:
        CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except IOError as e:
        logger.error(f"Failed to save cache: {e}")
    
    total = len(cache)
    logger.info(f"Scan complete: {scanned} new, {failed} failed, {total} total")
    
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
