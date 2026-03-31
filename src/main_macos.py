#!/usr/bin/env python3
"""
Push 2 / Nuendo Bridge — macOS Menu Bar App

Runs as a menu bar icon with:
- Connection status indicator (Push 2 + Nuendo)
- Status window with live logs
- Notifications on connection/disconnection
- Auto-start at login option
"""

import sys
import os
import time
import threading

import plistlib
from datetime import datetime

if sys.platform != "darwin":
    print("This menu bar app is macOS only. Use: python main.py --terminal")
    sys.exit(1)

import rumps

from state import AppState
from nuendo_link import NuendoLink
from push2_controller import Push2Controller


# ─────────────────────────────────────────────
# Simple log buffer (no logging module, no locks)
# ─────────────────────────────────────────────

_LOG_LINES = []
_LOG_FILE = os.path.expanduser("~/Library/Logs/Push2NuendoBridge.log")
_LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

def blog(msg):
    """Bridge log — append to memory buffer and file. Rotates at 5 MB."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"{ts}  {msg}"
    _LOG_LINES.append(line)
    if len(_LOG_LINES) > 200:
        _LOG_LINES[:] = _LOG_LINES[-200:]
    try:
        # Rotate: if file exceeds 5 MB, keep only the last half
        try:
            size = os.path.getsize(_LOG_FILE)
            if size > _LOG_MAX_BYTES:
                with open(_LOG_FILE, "r") as f:
                    content = f.read()
                # Keep the last 2.5 MB
                trimmed = content[-(_LOG_MAX_BYTES // 2):]
                # Find the first complete line
                nl = trimmed.find("\n")
                if nl >= 0:
                    trimmed = trimmed[nl + 1:]
                with open(_LOG_FILE, "w") as f:
                    f.write(f"{ts}  --- Log trimmed ---\n")
                    f.write(trimmed)
        except FileNotFoundError:
            pass
        with open(_LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

def get_log_text():
    try:
        return "\n".join(_LOG_LINES[-50:])
    except Exception:
        return ""

# Redirect print() to blog
class PrintToLog:
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

sys.stdout = PrintToLog()


# ─────────────────────────────────────────────
# Auto-start at login (Launch Agent)
# ─────────────────────────────────────────────

LAUNCH_AGENT_LABEL = "com.push2nuendo.bridge"
LAUNCH_AGENT_PATH = os.path.expanduser(
    f"~/Library/LaunchAgents/{LAUNCH_AGENT_LABEL}.plist"
)

def is_auto_start_enabled():
    return os.path.exists(LAUNCH_AGENT_PATH)

def set_auto_start(enabled):
    try:
        if enabled:
            if getattr(sys, 'frozen', False):
                args = [sys.executable]
            else:
                args = [sys.executable, os.path.abspath(__file__)]
            
            plist = {
                "Label": LAUNCH_AGENT_LABEL,
                "ProgramArguments": args,
                "RunAtLoad": True,
                "KeepAlive": False,
            }
            os.makedirs(os.path.dirname(LAUNCH_AGENT_PATH), exist_ok=True)
            with open(LAUNCH_AGENT_PATH, "wb") as f:
                plistlib.dump(plist, f)
            blog("Auto-start at login: enabled")
        else:
            if os.path.exists(LAUNCH_AGENT_PATH):
                os.remove(LAUNCH_AGENT_PATH)
            blog("Auto-start at login: disabled")
    except Exception as e:
        blog(f"Auto-start failed: {e}")


# ─────────────────────────────────────────────
# Menu Bar App
# ─────────────────────────────────────────────

class Push2BridgeApp(rumps.App):
    
    def __init__(self):
        super().__init__(
            name="Push 2 Bridge",
            title="P2",
            quit_button=None,
        )
        
        # Bridge state
        self.state = None
        self.link = None
        self.ctrl = None
        self.bridge_running = False
        self._prev_nuendo = False
        self._waiting_for_push = False
        
        # Pending notifications (set from worker thread, consumed on main)
        self._pending_notification = None
        
        # Menu
        self.status_item = rumps.MenuItem("Status: Starting...")
        self.status_item.set_callback(None)
        
        self.push_status = rumps.MenuItem("  Push 2: —")
        self.push_status.set_callback(None)
        
        self.nuendo_status = rumps.MenuItem("  Nuendo: —")
        self.nuendo_status.set_callback(None)
        
        self.start_stop_item = rumps.MenuItem("Stop Bridge", callback=self.on_start_stop)
        
        self.show_logs_item = rumps.MenuItem("Show Logs", callback=self.on_show_logs)
        
        self.auto_start_item = rumps.MenuItem("Start at Login", callback=self.on_toggle_auto_start)
        self.auto_start_item.state = is_auto_start_enabled()
        
        self.quit_item = rumps.MenuItem("Quit", callback=self.on_quit)
        
        self.menu = [
            self.status_item,
            self.push_status,
            self.nuendo_status,
            None,
            self.start_stop_item,
            self.show_logs_item,
            None,
            self.auto_start_item,
            None,
            self.quit_item,
        ]
    
    def _dbg(self, msg):
        """Write directly to log file, bypassing all logging machinery."""
        try:
            _log = os.path.expanduser("~/Library/Logs/Push2NuendoBridge.log")
            with open(_log, "a") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S')}  {msg}\n")
        except Exception:
            pass
    
    # ─── Worker thread (non-UI) ───
    
    def _start_bridge_worker(self):
        """Runs in background thread. No UI calls here."""
        self._dbg("Worker: starting...")
        try:
            # Small delay to let old ports fully release on restart
            time.sleep(0.5)
            
            # Reuse existing state or create new
            if self.state is None:
                self.state = AppState()
                self._dbg("Worker: AppState created")
            else:
                # Reset connection state but keep track data
                self.state.nuendo_connected = False
                self._dbg("Worker: AppState reused")
            
            # MIDI ports (always recreate)
            self.link = NuendoLink(self.state)
            self._dbg("Worker: NuendoLink created, calling start()...")
            if not self.link.start():
                self._dbg("Worker: MIDI ports FAILED")
                self._pending_notification = (
                    "MIDI Port Error",
                    "Could not open IAC ports. Check Audio MIDI Setup."
                )
                return
            self._dbg("Worker: MIDI ports connected")
            
            # Push 2 — reuse existing connection if possible
            if self.ctrl is not None and self.ctrl.push is not None:
                self._dbg("Worker: Reusing existing Push 2 connection")
                self.ctrl.state = self.state
                self.ctrl.nuendo_link = self.link
                self.link._note_display_callback = self.ctrl._on_playback_note
                self.ctrl._running = True
                # Restart display thread
                import threading
                self.ctrl._display_thread = threading.Thread(
                    target=self.ctrl._display_loop, daemon=True
                )
                self.ctrl._display_thread.start()
                self.ctrl._init_palette()
                self.ctrl._update_all_leds()
            else:
                # First time or Push was not connected — retry until found
                self._dbg("Worker: Waiting for Push 2...")
                self._waiting_for_push = True
                while self._waiting_for_push:
                    try:
                        self.ctrl = Push2Controller(self.state, self.link)
                        if self.ctrl.start():
                            self._dbg("Worker: Push 2 connected!")
                            self._waiting_for_push = False
                            break
                        else:
                            # Clean up failed attempt
                            try:
                                if self.ctrl.push:
                                    del self.ctrl.push
                            except Exception:
                                pass
                            self.ctrl = None
                    except Exception as e:
                        self._dbg(f"Worker: Push 2 attempt error: {e}")
                        self.ctrl = None
                    
                    self._dbg("Worker: Push 2 not found, retrying in 5s...")
                    for _ in range(50):  # 5 seconds in 0.1s steps
                        if not self._waiting_for_push:
                            self._dbg("Worker: Push 2 wait cancelled")
                            return
                        time.sleep(0.1)
            
            self._dbg("Worker: Push 2 connected")
            self.bridge_running = True
            self._dbg("Worker: bridge running!")
        except Exception as e:
            self._dbg(f"Worker CRASH: {e}")
            import traceback
            self._dbg(traceback.format_exc())
    
    # ─── Timer: poll status on main thread ───
    
    @rumps.timer(2)
    def poll_status(self, _):
        """Runs on main thread. Safe to update UI here."""
        
        # Process pending notifications
        if self._pending_notification:
            subtitle, message = self._pending_notification
            self._pending_notification = None
            try:
                rumps.notification("Push 2 Bridge", subtitle, message, sound=True)
            except Exception:
                pass
        
        if not self.bridge_running:
            if self._waiting_for_push:
                self.title = "P2 ⏳"
                self.status_item.title = "Status: Waiting for Push 2..."
                self.push_status.title = "  Push 2: Searching..."
                self.nuendo_status.title = "  Nuendo: —"
                self.start_stop_item.title = "Stop Bridge"
            elif self.link is None and self.ctrl is None:
                # Never started or failed
                self.title = "P2 ✗"
                self.status_item.title = "Status: Not running"
                self.push_status.title = "  Push 2: —"
                self.nuendo_status.title = "  Nuendo: —"
                self.start_stop_item.title = "Start Bridge"
            return
        
        # Check connection states
        nuendo_ok = getattr(self.state, 'nuendo_connected', False) if self.state else False
        push_ok = self.ctrl is not None and hasattr(self.ctrl, 'push') and self.ctrl.push is not None
        
        # Detect Nuendo connection changes → notify
        if nuendo_ok and not self._prev_nuendo:
            self._pending_notification = ("Connected", "Nuendo is now connected.")
        elif not nuendo_ok and self._prev_nuendo:
            self._pending_notification = ("Disconnected", "Nuendo connection lost.")
        self._prev_nuendo = nuendo_ok
        
        # Update menu bar
        if push_ok and nuendo_ok:
            self.title = "P2 ✓"
            self.status_item.title = "Status: Connected"
        elif push_ok:
            self.title = "P2 ⏳"
            self.status_item.title = "Status: Waiting for Nuendo..."
        else:
            self.title = "P2 ✗"
            self.status_item.title = "Status: Push 2 disconnected"
        
        self.push_status.title = f"  Push 2: {'Connected' if push_ok else 'Disconnected'}"
        self.nuendo_status.title = f"  Nuendo: {'Connected' if nuendo_ok else 'Waiting...'}"
        self.start_stop_item.title = "Stop Bridge"
    
    # ─── Menu callbacks (main thread) ───
    
    def on_start_stop(self, sender):
        self._dbg("on_start_stop clicked")
        if self.bridge_running:
            self._stop_bridge()
        else:
            self._dbg("Starting worker thread...")
            self._worker = threading.Thread(target=self._start_bridge_worker, daemon=True)
            self._worker.start()
    
    def _stop_bridge(self):
        self._dbg("Stopping bridge...")
        self.bridge_running = False
        self._waiting_for_push = False  # Cancel any pending retry
        
        # Stop display loop but keep Push 2 connection alive
        if self.ctrl:
            self.ctrl._running = False
            # Don't set self.ctrl = None — we'll reuse it
        
        # Close MIDI ports (will be recreated on start)
        if self.link:
            try:
                self.link.stop()
            except Exception:
                pass
            self.link = None
        
        self.title = "P2"
        self.status_item.title = "Status: Stopped"
        self.push_status.title = "  Push 2: —"
        self.nuendo_status.title = "  Nuendo: —"
        self.start_stop_item.title = "Start Bridge"
        self._prev_nuendo = False
        self._dbg("Bridge stopped")
    
    def on_show_logs(self, sender):
        text = get_log_text() or "No logs yet."
        # Only show last 20 lines to avoid UI freeze with large text
        lines = text.split("\n")
        if len(lines) > 20:
            text = "\n".join(lines[-20:])
        rumps.alert(title="Push 2 Bridge — Logs", message=text, ok="Close")
    
    def on_toggle_auto_start(self, sender):
        sender.state = not sender.state
        set_auto_start(sender.state)
    
    def on_quit(self, sender):
        self._stop_bridge()
        rumps.quit_application()


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def main():
    _debug_log = os.path.expanduser("~/Library/Logs/Push2NuendoBridge.log")
    def _dbg(msg):
        try:
            with open(_debug_log, "a") as f:
                f.write(f"{datetime.now().strftime('%H:%M:%S')}  {msg}\n")
        except Exception:
            pass
    
    _dbg("=== App starting ===")
    try:
        app = Push2BridgeApp()
        _dbg("App created, launching worker thread...")
        
        # Start bridge in background thread (not main thread!)
        worker = threading.Thread(target=app._start_bridge_worker, daemon=True)
        worker.start()
        
        _dbg("Calling app.run()")
        app.run()
    except Exception as e:
        _dbg(f"CRASH: {e}")
        import traceback
        _dbg(traceback.format_exc())

if __name__ == "__main__":
    main()
