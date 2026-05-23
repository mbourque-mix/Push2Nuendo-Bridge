#!/usr/bin/env python3
"""
Push 2 / Nuendo Bridge - Windows System Tray App

Runs as a tray icon (no console) with:
- Connection status in the tooltip + status menu item
- Open Plugin Mapper / Show Log / Quit
- Logs to %LOCALAPPDATA%/Push2NuendoBridge/bridge.log

Use `--terminal` to run the console version instead.
"""

import sys
import os
import time
import threading
import webbrowser
from datetime import datetime

if sys.platform != "win32":
    print("This tray app is Windows only. Use: python main.py --terminal")
    sys.exit(1)

import pystray
from PIL import Image, ImageDraw

from state import AppState, BRIDGE_VERSION
from nuendo_link import NuendoLink
from push2_controller import Push2Controller


# ─────────────────────────────────────────────
# Log file (no console in windowed mode)
# ─────────────────────────────────────────────

_LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                        "Push2NuendoBridge")
_LOG_FILE = os.path.join(_LOG_DIR, "bridge.log")
_LOG_MAX_BYTES = 5 * 1024 * 1024


def blog(msg):
    """Append a line to the log file. Rotates at 5 MB."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts}  {msg}"
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        try:
            if os.path.getsize(_LOG_FILE) > _LOG_MAX_BYTES:
                with open(_LOG_FILE, "r") as f:
                    content = f.read()
                trimmed = content[-(_LOG_MAX_BYTES // 2):]
                nl = trimmed.find("\n")
                if nl >= 0:
                    trimmed = trimmed[nl + 1:]
                with open(_LOG_FILE, "w") as f:
                    f.write(f"{ts}  --- Log trimmed ---\n{trimmed}")
        except FileNotFoundError:
            pass
        with open(_LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


class _PrintToLog:
    """Redirect print()/stderr to the log file (no console in windowed mode)."""
    def __init__(self):
        self._guard = False

    def write(self, msg):
        if self._guard:
            return
        msg = msg.strip()
        if msg:
            self._guard = True
            try:
                blog(msg)
            finally:
                self._guard = False

    def flush(self):
        pass

    def isatty(self):
        return False


# ─────────────────────────────────────────────
# Plugin Mapper server (optional)
# ─────────────────────────────────────────────

def _start_plugin_mapper():
    """Start the Plugin Mapper web server in a daemon thread. Returns a status string."""
    import sys as _sys
    # Bundled deps live on the frozen app's own sys.path; never inject system paths.
    if getattr(_sys, "frozen", False):
        base = getattr(_sys, "_MEIPASS", "")
        if base and base not in _sys.path:
            _sys.path.insert(0, base)
    try:
        import uvicorn
        import fastapi  # noqa: F401
    except ImportError:
        return "not available (install: pip install fastapi uvicorn)"

    mapper_app = None
    try:
        from mapper.server import app as mapper_app
    except ImportError:
        pass
    if mapper_app is None:
        return "not available (mapper files not found)"

    pedalboard_status = ""
    try:
        import pedalboard  # noqa: F401
        pedalboard_status = ", scanner ready"
    except ImportError:
        pedalboard_status = ", scanner unavailable"

    def _run_server():
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            config = uvicorn.Config(mapper_app, host="127.0.0.1", port=8100,
                                    log_level="warning", log_config=None)
            server = uvicorn.Server(config)
            server.install_signal_handlers = False
            loop.run_until_complete(server.serve())
        except Exception as e:
            blog(f"Plugin Mapper server error: {e}")

    threading.Thread(target=_run_server, daemon=True).start()

    import socket
    for _ in range(20):
        time.sleep(0.1)
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            ok = s.connect_ex(("127.0.0.1", 8100)) == 0
            s.close()
            if ok:
                return f"running at http://localhost:8100{pedalboard_status}"
        except Exception:
            pass
    return f"failed to start (check log){pedalboard_status}"


# ─────────────────────────────────────────────
# Tray icon image (generated)
# ─────────────────────────────────────────────

def _make_icon(connected=False, error=False):
    """A simple 64x64 icon: dark rounded square + a 4x4 grid of pads.

    Pads are green when fully connected, amber while waiting, red on error.
    """
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, size - 2, size - 2], radius=12, fill=(24, 24, 30))
    if error:
        pad = (220, 60, 60)
    elif connected:
        pad = (0, 200, 110)
    else:
        pad = (150, 150, 160)
    # 4x4 grid of pads
    margin, gap = 12, 4
    cell = (size - 2 * margin - 3 * gap) / 4
    for r in range(4):
        for c in range(4):
            x0 = margin + c * (cell + gap)
            y0 = margin + r * (cell + gap)
            d.rounded_rectangle([x0, y0, x0 + cell, y0 + cell], radius=2, fill=pad)
    return img


# ─────────────────────────────────────────────
# Tray app
# ─────────────────────────────────────────────

class TrayApp:
    def __init__(self):
        self.state = None
        self.link = None
        self.ctrl = None
        self.bridge_running = False
        self._waiting_for_push = False
        self._error = False
        self._mapper_status = "not started"

        self.icon = pystray.Icon(
            "Push2Bridge",
            _make_icon(False),
            f"Push 2 Bridge v{BRIDGE_VERSION}",
            menu=pystray.Menu(
                pystray.MenuItem(self._status_text, None, enabled=False),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Open Plugin Mapper", self.on_open_mapper),
                pystray.MenuItem("Show Log", self.on_show_log),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self.on_quit),
            ),
        )

    # ── Status helpers ──

    def _connected(self):
        nuendo_ok = getattr(self.state, "nuendo_connected", False) if self.state else False
        push_ok = self.ctrl is not None and getattr(self.ctrl, "push", None) is not None
        return push_ok, nuendo_ok

    def _status_text(self, _item=None):
        if self._error:
            return "Status: Error - see Show Log"
        if self._waiting_for_push:
            return "Status: Waiting for Push 2..."
        if not self.bridge_running:
            return "Status: Starting..."
        push_ok, nuendo_ok = self._connected()
        if push_ok and nuendo_ok:
            return "Status: Connected"
        if push_ok:
            return "Status: Waiting for Nuendo..."
        return "Status: Push 2 disconnected"

    # ── Worker thread (no UI) ──

    def _start_bridge_worker(self):
        blog("Worker: starting...")
        try:
            self._mapper_status = _start_plugin_mapper()
            blog(f"Worker: Plugin Mapper: {self._mapper_status}")
            time.sleep(0.5)

            self.state = AppState()
            self.link = NuendoLink(self.state)
            blog("Worker: NuendoLink created, calling start()...")
            if not self.link.start():
                blog("Worker: MIDI ports FAILED")
                self._error = True
                return
            blog("Worker: MIDI ports connected")

            blog("Worker: waiting for Push 2...")
            self._waiting_for_push = True
            while self._waiting_for_push:
                try:
                    self.ctrl = Push2Controller(self.state, self.link)
                    if self.ctrl.start():
                        blog("Worker: Push 2 connected!")
                        self._waiting_for_push = False
                        break
                    self.ctrl = None
                except Exception as e:
                    blog(f"Worker: Push 2 attempt error: {e}")
                    self.ctrl = None
                for _ in range(50):  # 5 s
                    if not self._waiting_for_push:
                        return
                    time.sleep(0.1)

            self.bridge_running = True
            blog("Worker: bridge running!")
        except Exception as e:
            blog(f"Worker CRASH: {e}")
            import traceback
            blog(traceback.format_exc())
            self._error = True

    def _status_loop(self):
        """Refresh the tray icon colour + tooltip periodically."""
        while True:
            try:
                push_ok, nuendo_ok = self._connected()
                self.icon.icon = _make_icon(push_ok and nuendo_ok, self._error)
                self.icon.title = f"Push 2 Bridge - {self._status_text()}"
                self.icon.update_menu()
            except Exception:
                pass
            time.sleep(2)

    # ── Menu callbacks ──

    def on_open_mapper(self, icon, item):
        if "running" in self._mapper_status:
            webbrowser.open("http://localhost:8100")
        else:
            try:
                icon.notify(f"Plugin Mapper: {self._mapper_status}", "Push 2 Bridge")
            except Exception:
                pass

    def on_show_log(self, icon, item):
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
            if not os.path.exists(_LOG_FILE):
                open(_LOG_FILE, "a").close()
            os.startfile(_LOG_FILE)  # noqa: S606 (Windows-only)
        except Exception as e:
            blog(f"Show Log failed: {e}")

    def on_quit(self, icon, item):
        blog("Quit requested")
        self._waiting_for_push = False
        try:
            if self.ctrl:
                self.ctrl.stop()
        except Exception:
            pass
        try:
            if self.link:
                self.link.stop()
        except Exception:
            pass
        icon.stop()

    def run(self):
        threading.Thread(target=self._start_bridge_worker, daemon=True).start()
        threading.Thread(target=self._status_loop, daemon=True).start()
        self.icon.run()  # blocks on the main thread


def main():
    sys.stdout = _PrintToLog()
    sys.stderr = _PrintToLog()
    blog(f"=== Tray app starting (v{BRIDGE_VERSION}) ===")
    try:
        TrayApp().run()
    except Exception as e:
        blog(f"CRASH: {e}")
        import traceback
        blog(traceback.format_exc())


if __name__ == "__main__":
    main()
