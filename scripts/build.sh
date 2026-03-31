#!/bin/bash
# ─────────────────────────────────────────────────
# Push 2 / Nuendo Bridge — Build standalone .app
# ─────────────────────────────────────────────────

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
SRC_DIR="$PROJECT_DIR/src"

echo ""
echo "Building Push 2 / Nuendo Bridge..."
echo ""

# Check dependencies
pip3 install pyinstaller rumps 2>/dev/null

# Clean previous build
rm -rf "$PROJECT_DIR/dist" "$PROJECT_DIR/build"

cd "$SRC_DIR"

# Build the .app
# Note: push2-python includes a Flask/SocketIO simulator that requires
# engineio.async_drivers to be bundled, otherwise it crashes at import.
pyinstaller \
    --name "Push2 Nuendo Bridge" \
    --onedir \
    --windowed \
    --noconfirm \
    --clean \
    --osx-bundle-identifier "com.push2nuendo.bridge" \
    --add-data "state.py:." \
    --add-data "nuendo_link.py:." \
    --add-data "push2_controller.py:." \
    --add-data "renderer.py:." \
    --add-data "pad_grid.py:." \
    --add-data "control_room.py:." \
    --add-data "repeat.py:." \
    --add-data "overview.py:." \
    --add-data "main_macos.py:." \
    --hidden-import rumps \
    --hidden-import push2_python \
    --hidden-import push2_python.constants \
    --hidden-import push2_python.simulator \
    --hidden-import push2_python.simulator.simulator \
    --hidden-import rtmidi \
    --hidden-import mido \
    --hidden-import mido.backends \
    --hidden-import mido.backends.rtmidi \
    --hidden-import PIL \
    --hidden-import PIL.Image \
    --hidden-import PIL.ImageDraw \
    --hidden-import PIL.ImageFont \
    --collect-submodules PIL \
    --collect-submodules push2_python \
    --collect-submodules engineio \
    --collect-submodules socketio \
    --hidden-import numpy \
    --hidden-import engineio \
    --hidden-import engineio.async_drivers \
    --hidden-import engineio.async_drivers.threading \
    --hidden-import socketio \
    --hidden-import flask \
    --hidden-import flask_socketio \
    --hidden-import usb \
    --hidden-import usb.core \
    --hidden-import usb.backend \
    --hidden-import usb.backend.libusb1 \
    main.py

# Move output to project root
mv dist "$PROJECT_DIR/dist"
rm -rf build *.spec

# Copy JS script into dist
cp "$PROJECT_DIR/Ableton_Push2.js" "$PROJECT_DIR/dist/"

# Add LSUIElement to Info.plist (hide from Dock, show only in menu bar)
PLIST="$PROJECT_DIR/dist/Push2 Nuendo Bridge.app/Contents/Info.plist"
if [ -f "$PLIST" ]; then
    /usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "$PLIST" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "$PLIST"
    echo "  ✓ LSUIElement set (app will hide from Dock)"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✓ Build complete!"
echo ""
echo "  App:    dist/Push2 Nuendo Bridge.app"
echo "  Script: dist/Ableton_Push2.js"
echo ""
echo "  Test it:"
echo "    ./dist/Push2\\ Nuendo\\ Bridge.app/Contents/MacOS/Push2\\ Nuendo\\ Bridge"
echo ""
echo "  To distribute:"
echo "    1. Copy the .app to /Applications"
echo "    2. Copy Ableton_Push2.js to Nuendo MIDI Remote folder"
echo "═══════════════════════════════════════════════"
echo ""
