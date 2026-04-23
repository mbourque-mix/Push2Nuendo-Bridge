#!/usr/bin/env python3
"""
Push 2 / Nuendo Bridge — Entry Point

- macOS: Launches the menu bar app (with rumps)
- Windows/Linux: Launches the terminal version
- Use --terminal to force terminal mode on any platform

The Plugin Mapper server (FastAPI) starts automatically if dependencies are installed.
Access it at http://localhost:8100 to create parameter mappings.
"""

import sys


def main():
    force_terminal = "--terminal" in sys.argv or "-t" in sys.argv
    
    if sys.platform == "darwin" and not force_terminal:
        try:
            from main_macos import main as macos_main
            macos_main()
        except ImportError:
            print("  rumps not installed — falling back to terminal mode")
            print("  Install it with: pip install rumps")
            print()
            terminal_main()
    else:
        terminal_main()


def start_plugin_mapper():
    """Start the Plugin Mapper web server in a daemon thread.
    
    Returns a status string for display.
    Dependencies are optional — the bridge works without them.
    """
    import threading
    
    # ── Check dependencies ──
    try:
        import uvicorn
    except ImportError:
        return "not available (install: pip install fastapi uvicorn)"
    
    try:
        import fastapi
    except ImportError:
        return "not available (install: pip install fastapi)"
    
    # ── Find the mapper server module ──
    mapper_app = None
    
    # Try 1: mapper/ subdirectory (integrated layout)
    try:
        from mapper.server import app as mapper_app
    except ImportError:
        pass
    
    # Try 2: plugin-mapper/backend/ relative path (standalone layout)
    if mapper_app is None:
        import os
        from pathlib import Path
        standalone_path = Path(__file__).parent.parent / "plugin-mapper" / "backend"
        if standalone_path.exists():
            sys.path.insert(0, str(standalone_path))
            try:
                from server import app as mapper_app
            except ImportError:
                pass
            finally:
                if str(standalone_path) in sys.path:
                    sys.path.remove(str(standalone_path))
    
    if mapper_app is None:
        return "not available (mapper files not found)"
    
    # ── Check pedalboard (optional — scanner only) ──
    pedalboard_status = ""
    try:
        import pedalboard
        pedalboard_status = ", scanner ready"
    except ImportError:
        pedalboard_status = ", scanner unavailable (install: pip install pedalboard)"
    
    # ── Start uvicorn in a daemon thread ──
    def _run_server():
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            config = uvicorn.Config(
                mapper_app, host="127.0.0.1", port=8100,
                log_level="warning", log_config=None
            )
            server = uvicorn.Server(config)
            server.install_signal_handlers = False  # Required for non-main thread
            loop.run_until_complete(server.serve())
        except Exception as e:
            print(f"  ⚠ Plugin Mapper server error: {e}")
            import traceback
            traceback.print_exc()
    
    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to bind
    import time as _t
    for _ in range(20):
        _t.sleep(0.1)
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.1)
            result = s.connect_ex(('127.0.0.1', 8100))
            s.close()
            if result == 0:
                return f"running at http://localhost:8100{pedalboard_status}"
        except Exception:
            pass
    
    return f"failed to start (check logs){pedalboard_status}"


def terminal_main():
    """Terminal-based bridge (all platforms)."""
    import time
    import signal
    
    from state import AppState, BRIDGE_VERSION
    from nuendo_link import NuendoLink
    from push2_controller import Push2Controller
    
    print()
    print("╔═══════════════════════════════════════════════╗")
    print(f"║     Push 2 / Nuendo Bridge  v{BRIDGE_VERSION:<15s}║")
    print("╚═══════════════════════════════════════════════╝")
    print()
    
    # ── Create shared state ──
    state = AppState()
    
    # ── Start Plugin Mapper server (optional) ──
    mapper_status = start_plugin_mapper()
    print(f"[0/3] Plugin Mapper: {mapper_status}")
    
    # ── Start Nuendo MIDI link ──
    print("[1/3] Connecting to MIDI ports...")
    link = NuendoLink(state)
    if not link.start():
        print()
        print("  ERROR: Could not open MIDI ports.")
        if sys.platform == "darwin":
            print("  → Check that IAC Driver is enabled in Audio MIDI Setup")
        else:
            print("  → Check that loopMIDI is running")
        print("  → Make sure ports 'Push2-To-Nuendo' and 'Nuendo-To-Push2' exist")
        sys.exit(1)
    print("  ✓ MIDI ports connected")
    
    # ── Start Push 2 controller ──
    print("[2/3] Connecting to Push 2...")
    ctrl = Push2Controller(state, link)
    if not ctrl.start():
        print()
        print("  ERROR: Could not connect to Push 2.")
        print("  → Check that Push 2 is connected via USB")
        print("  → Check that libusb is installed")
        print("  → Check that Ableton Live is not running")
        link.stop()
        sys.exit(1)
    print("  ✓ Push 2 connected")
    
    # ── Ready ──
    print("[3/3] Bridge is running!")
    print()
    print("  Waiting for Nuendo... (make sure the MIDI Remote script is loaded)")
    print("  Press Ctrl+C to quit")
    print()
    
    # ── Graceful shutdown ──
    def shutdown(sig=None, frame=None):
        print("\n  Shutting down...")
        ctrl.stop()
        link.stop()
        print("  ✓ Bridge stopped. Goodbye!")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # ── Main loop ──
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
