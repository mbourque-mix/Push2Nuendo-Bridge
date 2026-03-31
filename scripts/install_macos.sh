#!/bin/bash
# ─────────────────────────────────────────────────
# Push 2 / Nuendo Bridge — macOS Installer
# ─────────────────────────────────────────────────

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║   Push 2 / Nuendo Bridge — macOS Installer    ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# ── Check Python ──
echo "[1/5] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 not found. Install it from https://python.org"
    exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  ✓ Python $PY_VERSION found"

# ── Check libusb ──
echo "[2/5] Checking libusb..."
if ! brew list libusb &> /dev/null 2>&1; then
    echo "  libusb not found. Installing via Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo "  ✗ Homebrew not found. Install it from https://brew.sh"
        echo "  Then run: brew install libusb"
        exit 1
    fi
    brew install libusb
fi
echo "  ✓ libusb installed"

# ── Install Python dependencies ──
echo "[3/5] Installing Python dependencies..."
pip3 install -r "$PROJECT_DIR/requirements.txt"
echo "  ✓ Dependencies installed"

# ── Set up IAC ports ──
echo "[4/5] IAC Driver setup..."
echo ""
echo "  You need to create two IAC ports manually:"
echo "  1. Open Audio MIDI Setup (Applications → Utilities)"
echo "  2. Menu: Window → Show MIDI Studio"
echo "  3. Double-click 'IAC Driver'"
echo "  4. Check 'Device is online'"
echo "  5. Add two ports:"
echo "     • Push2-To-Nuendo"
echo "     • Nuendo-To-Push2"
echo ""
read -p "  Press Enter when done (or 's' to skip)... " REPLY
if [[ "$REPLY" == "s" ]]; then
    echo "  ⚠ Skipped — remember to set up IAC ports before running!"
fi

# ── Install MIDI Remote script ──
echo "[5/5] Installing Nuendo MIDI Remote script..."
MIDI_REMOTE_DIR="$HOME/Documents/Steinberg/Nuendo 14/MIDI Remote/Driver Scripts/Local"

# Also try Cubase
CUBASE_DIR="$HOME/Documents/Steinberg/Cubase 14/MIDI Remote/Driver Scripts/Local"

install_js() {
    local dir="$1"
    local name="$2"
    mkdir -p "$dir"
    cp "$PROJECT_DIR/Ableton_Push2.js" "$dir/"
    echo "  ✓ Script installed to $name"
}

if [ -d "$HOME/Documents/Steinberg/Nuendo 14" ]; then
    install_js "$MIDI_REMOTE_DIR" "Nuendo 14"
fi

if [ -d "$HOME/Documents/Steinberg/Cubase 14" ]; then
    install_js "$CUBASE_DIR" "Cubase 14"
fi

if [ ! -d "$HOME/Documents/Steinberg/Nuendo 14" ] && [ ! -d "$HOME/Documents/Steinberg/Cubase 14" ]; then
    echo "  ⚠ Nuendo/Cubase 14 folder not found"
    echo "  Copy Ableton_Push2.js manually to:"
    echo "  ~/Documents/Steinberg/<DAW>/MIDI Remote/Driver Scripts/Local/"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Installation complete!"
echo ""
echo "  To run the bridge:"
echo "    cd $PROJECT_DIR/src"
echo "    python3 main.py"
echo ""
echo "  To configure Nuendo:"
echo "    Studio → Studio Setup → MIDI Remote"
echo "    Input: Push2-To-Nuendo"
echo "    Output: Nuendo-To-Push2"
echo "═══════════════════════════════════════════════"
