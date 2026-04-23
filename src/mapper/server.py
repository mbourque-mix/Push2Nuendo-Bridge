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

from fastapi import FastAPI, HTTPException, BackgroundTasks
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

scan_status = {"scanning": False, "progress": 0, "total": 0, "current": ""}

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
        
        plugins.append({
            "name": name,
            "type": info.get("type", "VST3"),
            "is_instrument": info.get("is_instrument", False),
            "parameter_count": info.get("parameter_count", 0),
            "has_mapping": has_mapping,
            "error": info.get("error"),
        })
    
    return {"plugins": plugins, "total": len(plugins)}


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
        scan_status["scanning"] = True
        scan_status["current"] = "Discovering plugins..."
        try:
            result = scanner.full_scan(extra_dirs=extra_dirs, force=request.force, retry_errors=request.retry_errors)
            scan_status["total"] = len(result)
        except Exception as e:
            logger.error(f"Scan failed: {e}")
        finally:
            scan_status["scanning"] = False
            scan_status["current"] = ""
    
    background_tasks.add_task(do_scan)
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
