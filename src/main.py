#!/usr/bin/env python3
"""
Push 2 / Nuendo Bridge — Entry Point

- macOS: Launches the menu bar app (with rumps)
- Windows/Linux: Launches the terminal version
- Use --terminal to force terminal mode on any platform
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


def terminal_main():
    """Terminal-based bridge (all platforms)."""
    import time
    import signal
    
    from state import AppState
    from nuendo_link import NuendoLink
    from push2_controller import Push2Controller
    
    print()
    print("╔═══════════════════════════════════════════════╗")
    print("║       Push 2 / Nuendo Bridge  v1.0.1          ║")
    print("╚═══════════════════════════════════════════════╝")
    print()
    
    # ── Create shared state ──
    state = AppState()
    
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
