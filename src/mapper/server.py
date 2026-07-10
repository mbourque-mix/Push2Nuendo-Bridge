"""
server.py — Plugin Mapper API Server

REST API for the Plugin Mapper frontend.
Endpoints:
  GET  /api/plugins          — List all scanned plugins
  GET  /api/plugins/{name}   — Get plugin details + parameters
  POST /api/scan             — Trigger a full scan (or rescan)
  GET  /api/mappings         — List all saved mappings
  GET  /api/mappings/{name}  — Get mapping for a plugin
  POST /api/mappings/{name}  — Save mapping for a plugin
  DELETE /api/mappings/{name} — Delete mapping for a plugin
  GET  /api/settings         — Get scanner settings (directories)
  POST /api/settings         — Update scanner settings
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from . import scanner  # Submodule import (when used as src/mapper/)
except ImportError:
    import scanner  # Standalone import (when run directly)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── Settings ──

SETTINGS_FILE = scanner.CACHE_DIR / "mapper_settings.json"

def load_settings():
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return {"extra_vst3_dirs": [], "auto_scan_on_start": True}

def save_settings(settings):
    scanner.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2))

# ── App ──

scan_status = {"scanning": False, "progress": 0, "total": 0, "current": "", "cancelled": False}
_scan_cancel = {"flag": False}
_scan_skip = {"flag": False}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """On startup, load cache (and optionally scan)."""
    settings = load_settings()
    if settings.get("auto_scan_on_start", True):
        logger.info("Loading plugin cache...")
        cache = scanner.get_cached_plugins()
        if not cache:
            logger.info("No cache found — run POST /api/scan to scan plugins")
    yield

app = FastAPI(
    title="Push2 Plugin Mapper",
    description="Map VST3/AU plugin parameters for Push 2 / Nuendo Bridge",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow CORS for React frontend (dev mode on different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ──

class MappingPage(BaseModel):
    name: str = ""
    params: List[int] = []  # parameter indices
    labels: List[str] = []  # optional short labels for Push 2 display

class MappingData(BaseModel):
    pages: List[MappingPage] = []

class SettingsData(BaseModel):
    extra_vst3_dirs: List[str] = []
    auto_scan_on_start: bool = True

class ScanRequest(BaseModel):
    force: bool = False
    retry_errors: bool = False
    extra_dirs: List[str] = []


# ── Plugin endpoints ──

@app.get("/api/plugins")
def list_plugins(search: Optional[str] = None, type: Optional[str] = None):
    """List all scanned plugins with basic info."""
    cache = scanner.get_cached_plugins()
    
    plugins = []
    for name, info in sorted(cache.items(), key=lambda x: x[0].lower()):
        # Skip internal multi-plugin shell markers (not real plugins)
        if info.get("is_shell"):
            continue
        # Filter by search term
        if search and search.lower() not in name.lower():
            continue
        # Filter by type (effect/instrument)
        if type == "effect" and info.get("is_instrument"):
            continue
        if type == "instrument" and not info.get("is_instrument"):
            continue
        
        # Check if mapping exists
        has_mapping = scanner.get_mapping(name) is not None
        
        # Source/type label: captured-from-Nuendo entries are tagged
        ptype = "DirectAccess" if info.get("source") == "directaccess" else info.get("type", "VST3")
        plugins.append({
            "name": name,
            "type": ptype,
            "manufacturer": info.get("manufacturer", "") or "",
            "is_instrument": info.get("is_instrument", False),
            "parameter_count": info.get("parameter_count", 0),
            "has_mapping": has_mapping,
            "error": info.get("error"),
        })

    return {"plugins": plugins, "total": len(plugins)}


@app.delete("/api/plugins/{name}")
def delete_plugin(name: str):
    """Remove a plugin from the cache (e.g. a stale error or duplicate entry)."""
    if scanner.delete_plugin(name):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")


@app.get("/api/plugins/{name}")
def get_plugin(name: str):
    """Get full plugin details including all parameters."""
    import math
    cache = scanner.get_cached_plugins()
    
    if name not in cache:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    
    info = cache[name]
    
    # Sanitize float values (some plugins report -inf/inf/nan)
    for param in info.get("parameters", []):
        for key in ("default_value", "min_value", "max_value"):
            v = param.get(key)
            if v is not None and (math.isinf(v) or math.isnan(v)):
                param[key] = 0.0 if key != "max_value" else 1.0
    
    mapping = scanner.get_mapping(name)
    
    return {
        "plugin": info,
        "mapping": mapping,
    }


# ── Scan endpoints ──

@app.post("/api/scan")
def trigger_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Trigger a plugin scan."""
    if scan_status["scanning"]:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    
    settings = load_settings()
    extra_dirs = request.extra_dirs or settings.get("extra_vst3_dirs", [])
    
    def do_scan():
        _scan_cancel["flag"] = False
        _scan_skip["flag"] = False
        scan_status.update({"scanning": True, "progress": 0, "total": 0,
                            "current": "Discovering plugins...", "cancelled": False})

        def prog(done, total, name):
            scan_status["progress"] = done
            scan_status["total"] = total
            scan_status["current"] = name

        def should_skip():
            if _scan_skip["flag"]:
                _scan_skip["flag"] = False  # consume — skip only the current one
                return True
            return False

        try:
            scanner.full_scan(
                extra_dirs=extra_dirs, force=request.force,
                retry_errors=request.retry_errors,
                progress_cb=prog, should_cancel=lambda: _scan_cancel["flag"],
                should_skip=should_skip)
        except Exception as e:
            logger.error(f"Scan failed: {e}")
        finally:
            scan_status["cancelled"] = _scan_cancel["flag"]
            scan_status["scanning"] = False
            scan_status["current"] = ""

    background_tasks.add_task(do_scan)
    return {"status": "scan_started"}


@app.post("/api/scan/cancel")
def cancel_scan():
    """Request the in-progress scan to stop (partial results are kept)."""
    if not scan_status["scanning"]:
        return {"status": "idle"}
    _scan_cancel["flag"] = True
    return {"status": "cancelling"}


@app.post("/api/scan/skip")
def skip_current_plugin():
    """Skip the plugin currently being scanned and continue with the next."""
    if not scan_status["scanning"]:
        return {"status": "idle"}
    _scan_skip["flag"] = True
    return {"status": "skipping"}


@app.post("/api/scan/plugin/{name}")
def rescan_one_plugin(name: str, background_tasks: BackgroundTasks):
    """Re-scan a single plugin (e.g. retry one that errored/timed out)."""
    if scan_status["scanning"]:
        raise HTTPException(status_code=409, detail="Scan already in progress")
    cache = scanner.get_cached_plugins()
    if name not in cache:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    def do_rescan():
        _scan_skip["flag"] = False
        scan_status.update({"scanning": True, "progress": 0, "total": 1,
                            "current": name, "cancelled": False})
        try:
            # Generous timeout for a single targeted retry (the user waits for
            # just this one — useful for slow-loading plugins like FabFilter).
            scanner.rescan_plugin(name, timeout=300, should_skip=lambda: _scan_skip["flag"])
        except Exception as e:
            logger.error(f"Rescan failed: {e}")
        finally:
            scan_status["progress"] = 1
            scan_status["scanning"] = False
            scan_status["current"] = ""

    background_tasks.add_task(do_rescan)
    return {"status": "scan_started"}


@app.get("/api/scan/status")
def get_scan_status():
    """Get the current scan status."""
    return scan_status


# ── Mapping endpoints ──

@app.get("/api/mappings")
def list_all_mappings():
    """List all saved mappings."""
    return {"mappings": scanner.list_mappings()}


@app.get("/api/mappings/export")
def export_mappings():
    """Download all mappings as a single JSON backup file."""
    from fastapi.responses import JSONResponse
    bundle = scanner.export_all_mappings()
    return JSONResponse(
        content=bundle,
        headers={"Content-Disposition": 'attachment; filename="push2_mappings.json"'},
    )


@app.post("/api/mappings/import")
def import_mappings(bundle: dict):
    """Restore mappings from an exported bundle (or a bare {plugin: mapping})."""
    imported, skipped = scanner.import_mappings(bundle, overwrite=True)
    return {"imported": imported, "skipped": skipped}


@app.get("/api/mappings/{name}")
def get_mapping(name: str):
    """Get the mapping for a specific plugin."""
    mapping = scanner.get_mapping(name)
    if not mapping:
        raise HTTPException(status_code=404, detail=f"No mapping for '{name}'")
    return mapping


@app.post("/api/mappings/{name}")
def save_mapping(name: str, data: MappingData):
    """Save a mapping for a plugin."""
    # Validate that the plugin exists
    cache = scanner.get_cached_plugins()
    if name not in cache:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")
    
    plugin_info = cache[name]
    param_count = plugin_info.get("parameter_count", 0)
    
    # Validate parameter indices
    for page in data.pages:
        for idx in page.params:
            if idx < 0 or idx >= param_count:
                raise HTTPException(
                    status_code=400,
                    detail=f"Parameter index {idx} out of range (0-{param_count-1})"
                )
    
    mapping = scanner.save_mapping(name, data.model_dump())
    return mapping


@app.delete("/api/mappings/{name}")
def delete_mapping(name: str):
    """Delete a mapping for a plugin."""
    if scanner.delete_mapping(name):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail=f"No mapping for '{name}'")


# ── Settings endpoints ──

@app.get("/api/settings")
def get_settings():
    """Get scanner settings."""
    settings = load_settings()
    settings["default_vst3_dirs"] = scanner.get_default_vst3_dirs()
    return settings


@app.post("/api/settings")
def update_settings(data: SettingsData):
    """Update scanner settings."""
    settings = data.model_dump()
    save_settings(settings)
    return settings


# ── Key Command endpoints ──
# Stores labels + a per-page colour for the note-value buttons (CC 36-43). The
# actual key command bound to each slot lives in Nuendo's MIDI Remote Mapping
# Assistant; we only persist display metadata, read by the bridge for the Push
# screen and button LEDs.

KC_FILE = scanner.CACHE_DIR / "keycommands.json"
KC_PAGES = 8
KC_SLOTS = 8
KC_PALETTE = ["red", "coral", "yellow", "green", "cyan", "blue", "purple", "fuchsia"]

class KCSlot(BaseModel):
    command: str = ""     # Nuendo command name (default label)
    category: str = ""    # its command category (needed to bind it in the script)
    label: str = ""       # optional short label shown on the Push

class KCPage(BaseModel):
    color: str = "cyan"
    slots: List[KCSlot] = []

class KCData(BaseModel):
    pages: List[KCPage] = []

def _kc_default():
    return {"pages": [
        {"color": KC_PALETTE[p % len(KC_PALETTE)],
         "slots": [{"command": "", "category": "", "label": ""} for _ in range(KC_SLOTS)]}
        for p in range(KC_PAGES)
    ]}

def _kc_normalize(payload):
    """Coerce arbitrary input to exactly KC_PAGES x KC_SLOTS with valid colours."""
    base = _kc_default()
    pages = payload.get("pages", []) if isinstance(payload, dict) else []
    for p in range(min(KC_PAGES, len(pages))):
        pg = pages[p] or {}
        if pg.get("color") in KC_PALETTE:
            base["pages"][p]["color"] = pg["color"]
        slots = pg.get("slots", []) or []
        for s in range(min(KC_SLOTS, len(slots))):
            sl = slots[s] or {}
            base["pages"][p]["slots"][s] = {
                "command": str(sl.get("command", "") or "")[:80],
                "category": str(sl.get("category", "") or "")[:64],
                "label": str(sl.get("label", "") or "")[:24],
            }
    return base

@app.get("/api/keycommands")
def get_key_commands():
    """Return the saved Key Command labels/colours (defaults if none yet)."""
    if KC_FILE.exists():
        try:
            return _kc_normalize(json.loads(KC_FILE.read_text()))
        except (json.JSONDecodeError, IOError):
            pass
    return _kc_default()

@app.post("/api/keycommands")
def save_key_commands(data: KCData):
    """Persist Key Command labels/colours to ~/.push2bridge/keycommands.json."""
    base = _kc_normalize(data.model_dump())
    scanner.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    KC_FILE.write_text(json.dumps(base, indent=2))
    return base

@app.get("/api/keycommands/export")
def export_key_commands():
    """Download the Key Command config as a JSON backup file."""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=get_key_commands(),
        headers={"Content-Disposition": 'attachment; filename="push2_keycommands.json"'},
    )

@app.post("/api/keycommands/import")
def import_key_commands(bundle: dict):
    """Restore Key Command config from an exported backup, then save it."""
    if not isinstance(bundle, dict) or not isinstance(bundle.get("pages"), list):
        raise HTTPException(status_code=400, detail="Invalid backup: missing 'pages'")
    base = _kc_normalize(bundle)
    scanner.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    KC_FILE.write_text(json.dumps(base, indent=2))
    return base


# ── Nuendo function list (for the Key Command editor's function picker) ──
# A bundled default list ships in mapper/nuendo_functions.json; the user can
# import their own Nuendo "Key Commands" XML to get their exact list + macros,
# stored as an override in ~/.push2bridge/nuendo_functions.json.

NUENDO_FUNCTIONS_OVERRIDE = scanner.CACHE_DIR / "nuendo_functions.json"
_bundled_functions_path = Path(__file__).parent / "nuendo_functions.json"
# Categories that are machine-specific noise; dropped when importing an XML.
_FN_DROP_CATEGORIES = {'Process Plug-in'}

def _parse_keycommands_xml(raw):
    """Parse a Nuendo 'Key Commands' preset XML into {source, categories:[{category, commands:[...]}]}."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(raw)
    cats = None
    for l in root.iter('list'):
        if l.get('name') == 'Categories':
            cats = l
            break
    if cats is None:
        raise ValueError("not a Key Commands preset (no Categories list)")
    out = []
    for item in cats.findall('item'):
        nm = next((s.get('value') for s in item.findall('string') if s.get('name') == 'Name'), None)
        if not nm or nm in _FN_DROP_CATEGORIES:
            continue
        cmds = []
        for l in item.findall('list'):
            if l.get('name') == 'Commands':
                for ci in l.findall('item'):
                    v = next((s.get('value') for s in ci.findall('string') if s.get('name') == 'Name'), None)
                    if v:
                        cmds.append(v)
        if cmds:
            out.append({'category': nm, 'commands': cmds})
    return {'source': 'Nuendo (imported)', 'categories': out}

@app.get("/api/functions")
def get_functions():
    """Return the Nuendo function list (user override if imported, else bundled)."""
    for p in (NUENDO_FUNCTIONS_OVERRIDE, _bundled_functions_path):
        try:
            if p.exists():
                return json.loads(p.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, IOError):
            continue
    return {"source": "", "categories": []}

@app.post("/api/functions/import")
async def import_functions(request: Request):
    """Parse an uploaded Nuendo Key Commands XML (raw body), save it as the user
    override, and return a summary."""
    raw = await request.body()
    try:
        data = _parse_keycommands_xml(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Key Commands XML: {e}")
    scanner.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    NUENDO_FUNCTIONS_OVERRIDE.write_text(
        json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return {"source": data['source'], "categories": len(data['categories']),
            "commands": sum(len(c['commands']) for c in data['categories'])}


# ── Backup / Restore of all bridge preference files ──
# One zip of everything the bridge persists in ~/.push2bridge: settings.json,
# keycommands.json, nuendo_functions.json, mapper_settings.json and the
# mappings/ folder. Regenerable artifacts (plugin_cache.json — a per-machine
# scan cache — and the generated script) are deliberately excluded.

BACKUP_FILES = ["settings.json", "keycommands.json",
                "nuendo_functions.json", "mapper_settings.json"]
BACKUP_DIRS = ["mappings"]

@app.get("/api/backup")
def download_backup():
    """Download all bridge settings as a single zip."""
    import io, zipfile
    from datetime import date
    from fastapi.responses import Response
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name in BACKUP_FILES:
            p = scanner.CACHE_DIR / name
            if p.exists():
                z.write(p, name)
                count += 1
        for d in BACKUP_DIRS:
            dp = scanner.CACHE_DIR / d
            if dp.is_dir():
                for f in sorted(dp.glob("*.json")):
                    z.write(f, f"{d}/{f.name}")
                    count += 1
    if count == 0:
        raise HTTPException(status_code=404, detail="No settings files found to back up")
    fname = f"push2bridge_backup_{date.today().strftime('%Y%m%d')}.zip"
    return Response(content=buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})

@app.post("/api/backup/restore")
async def restore_backup(request: Request):
    """Restore settings from an uploaded backup zip (raw body). Only known
    file names are accepted (no path traversal). Restart the bridge (or use
    the Push's Reload) so everything is picked up."""
    import io, zipfile
    raw = await request.body()
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Not a valid zip file")
    restored = []
    for info in z.infolist():
        if info.is_dir():
            continue
        name = info.filename.replace("\\", "/")
        parts = name.split("/")
        # Accept only the exact layout we produce
        if len(parts) == 1 and parts[0] in BACKUP_FILES:
            target = scanner.CACHE_DIR / parts[0]
        elif len(parts) == 2 and parts[0] in BACKUP_DIRS and \
                parts[1].endswith(".json") and "/" not in parts[1] and ".." not in parts[1]:
            target = scanner.CACHE_DIR / parts[0] / parts[1]
        else:
            continue  # unknown/unsafe member — skip
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(z.read(info))
        restored.append(name)
    if not restored:
        raise HTTPException(status_code=400,
                            detail="No recognized settings files in this zip")
    return {"restored": restored,
            "note": "Restart the bridge so all restored settings are applied."}


# ── Key Command script generation (Path A) ──
# Bakes a makeCommandBinding per configured slot into Ableton_Push2.js so the
# buttons trigger their Nuendo commands directly (no Mapping Assistant). The
# generated script is written into the user's installed script if we can find
# it; otherwise it's offered for download.
import sys as _sys

KC_MARK_START = "// === GENERATED KEY COMMAND BINDINGS START ==="
KC_MARK_END = "// === GENERATED KEY COMMAND BINDINGS END ==="

def _base_script_path():
    """Locate the Ableton_Push2.js template (bundled beside the mapper in a
    frozen app, else the repo root in dev)."""
    cands = [Path(__file__).parent / "Ableton_Push2.js",
             Path(__file__).resolve().parents[2] / "Ableton_Push2.js"]
    mei = getattr(_sys, "_MEIPASS", None)
    if mei:
        cands.insert(0, Path(mei) / "mapper" / "Ableton_Push2.js")
    return next((c for c in cands if c.exists()), None)

def _js_str(s):
    return str(s).replace("\\", "\\\\").replace("'", "\\'")

def _generate_bindings():
    cfg = get_key_commands()
    lines = []
    for p, page in enumerate(cfg.get("pages", [])):
        for s, slot in enumerate(page.get("slots", [])):
            cmd = (slot.get("command") or "").strip()
            cat = (slot.get("category") or "").strip()
            if cmd and cat:
                idx = p * KC_SLOTS + s
                # try/catch so one unbindable command can't break the whole script
                lines.append("try { page.makeCommandBinding(keyCmdButtons[%d].mSurfaceValue, '%s', '%s'); } catch (e) {}"
                             % (idx, _js_str(cat), _js_str(cmd)))
    return lines

def _render_script():
    base = _base_script_path()
    if base is None:
        raise HTTPException(status_code=500, detail="Base Ableton_Push2.js not found")
    text = base.read_text(encoding="utf-8")
    if KC_MARK_START not in text or KC_MARK_END not in text:
        raise HTTPException(status_code=500, detail="Script markers missing in Ableton_Push2.js")
    lines = _generate_bindings()
    body = "\n".join(lines) if lines else "// (no key commands assigned yet)"
    block = KC_MARK_START + "\n" + body + "\n" + KC_MARK_END
    start = text.index(KC_MARK_START)
    end = text.index(KC_MARK_END) + len(KC_MARK_END)
    return text[:start] + block + text[end:], len(lines)

def _find_installed_scripts():
    """Find ALL installed copies of our script under the MIDI Remote 'Driver
    Scripts/Local' folders of every Steinberg app (Nuendo AND Cubase), matched
    by our device id in the file content.

    Returns (found, total_js): the list of matching script paths, and the total
    number of .js files seen anywhere under ~/Documents/Steinberg. The latter
    lets the caller tell "no Steinberg folder / genuinely not there" apart from
    "folder is present but macOS TCC returned it empty" (the frozen, unsigned
    menu-bar app hasn't been granted Documents access) — in the TCC case the
    walk yields ZERO .js even though a real Nuendo/Cubase install always has
    device.js and friends."""
    # ~/Documents/Steinberg holds a subfolder per app (Nuendo N, Cubase NN) on
    # both macOS and Windows; rglob walks whichever app(s) are installed.
    docs = Path.home() / "Documents" / "Steinberg"
    found = []
    total_js = 0
    if not docs.exists():
        return found, total_js
    for js in docs.rglob("*.js"):
        total_js += 1
        parts = " / ".join(js.parts).lower()
        if "driver scripts" not in parts or "local" not in parts:
            continue
        try:
            if "Push2-Nuendo-Bridge" in js.read_text(encoding="utf-8", errors="ignore")[:3000]:
                found.append(js)
        except Exception:
            continue
    return found, total_js

@app.post("/api/keycommands/generate")
def generate_script():
    """Regenerate the script with the current bindings, install it into every
    Nuendo/Cubase copy found, and always cache it for download."""
    text, count = _render_script()
    scanner.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (scanner.CACHE_DIR / "Ableton_Push2.generated.js").write_text(text, encoding="utf-8")
    targets, total_js = _find_installed_scripts()
    installed = []
    for target in targets:
        try:
            target.write_text(text, encoding="utf-8")
            installed.append(str(target))
        except Exception:
            pass
    # Distinguish a genuine "not installed" from a macOS TCC permission block:
    # the Steinberg folder exists but the walk saw zero .js (macOS handed the
    # unsigned menu-bar app an empty directory because Documents access was
    # never granted).
    steinberg = Path.home() / "Documents" / "Steinberg"
    permission_blocked = bool(
        not installed and steinberg.exists() and total_js == 0 and _sys.platform == "darwin"
    )
    return {"bindings": count, "installed": installed,
            "permission_blocked": permission_blocked}

@app.get("/api/keycommands/script")
def download_script():
    from fastapi.responses import PlainTextResponse
    text, _ = _render_script()
    return PlainTextResponse(text, headers={
        "Content-Disposition": 'attachment; filename="Ableton_Push2.js"'})


# ── Serve frontend ──

from fastapi.responses import HTMLResponse

_index_html_path = None

# Check for index.html in the same directory as server.py (integrated layout)
_local_index = Path(__file__).parent / "index.html"
if _local_index.exists():
    _index_html_path = _local_index
else:
    # Fallback: check old standalone layout (../frontend/)
    _standalone = Path(__file__).parent.parent / "frontend" / "index.html"
    if _standalone.exists():
        _index_html_path = _standalone

if _index_html_path:
    @app.get("/", response_class=HTMLResponse)
    def serve_frontend():
        return _index_html_path.read_text(encoding="utf-8")

# Key Command config page (separate, lightweight UI)
_keycmd_html_path = Path(__file__).parent / "keycmd.html"
if _keycmd_html_path.exists():
    @app.get("/keycmd", response_class=HTMLResponse)
    def serve_keycmd():
        return _keycmd_html_path.read_text(encoding="utf-8")


if __name__ == "__main__":
    import uvicorn
    print()
    print("╔═══════════════════════════════════════════════╗")
    print("║        Push2 Plugin Mapper  v1.0.0            ║")
    print("╚═══════════════════════════════════════════════╝")
    print()
    print("  API:      http://localhost:8100/docs")
    print("  Frontend: http://localhost:8100")
    print()
    uvicorn.run(app, host="0.0.0.0", port=8100)
