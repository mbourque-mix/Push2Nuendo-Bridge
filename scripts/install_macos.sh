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

# ── Check Homebrew ──
echo "[1/5] Checking Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "  Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
echo "  ✓ Homebrew available"

# ── Check Python ──
echo "[2/5] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "  ✗ Python 3 not found. Install it from https://python.org"
    exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  ✓ Python $PY_VERSION found"

# ── Check libusb ──
echo "[3/5] Checking libusb..."
if ! brew list libusb &> /dev/null 2>&1; then
    echo "  libusb not found. Installing via Homebrew..."
    brew install libusb
fi
echo "  ✓ libusb installed"

# ── Install Python dependencies ──
echo "[4/5] Installing Python dependencies..."
pip3 install -r "$PROJECT_DIR/requirements.txt"
echo "  ✓ Core dependencies installed"

echo ""
echo "  Plugin Mapper (optional):"
echo "  To enable the Plugin Mapper, install additional dependencies:"
echo "    pip3 install fastapi uvicorn pedalboard"
echo ""
read -p "  Install Plugin Mapper dependencies now? (y/n) " REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    pip3 install fastapi uvicorn pedalboard
    echo "  ✓ Plugin Mapper dependencies installed"
fi

# ── Install MIDI Remote script ──
echo "[5/5] Installing Nuendo MIDI Remote script..."

install_js() {
    local dir="$1"
    local name="$2"
    mkdir -p "$dir/Ableton/Push2"
    cp "$PROJECT_DIR/Ableton_Push2.js" "$dir/Ableton/Push2/"
    echo "  ✓ Script installed to $name"
}

# Try common Nuendo/Cubase versions
INSTALLED=false
for DAW in "Nuendo" "Cubase"; do
    for VER in 15 14; do
        DAW_DIR="$HOME/Documents/Steinberg/${DAW} ${VER}/MIDI Remote/Driver Scripts/Local"
        BASE_DIR="$HOME/Documents/Steinberg/${DAW} ${VER}"
        if [ -d "$HOME/Documents/Steinberg/${DAW} ${VER}" ] || [ -d "$HOME/Documents/Steinberg/${DAW}" ]; then
            install_js "$DAW_DIR" "${DAW} ${VER}"
            INSTALLED=true
        fi
    done
    # Try without version number
    DAW_DIR="$HOME/Documents/Steinberg/${DAW}/MIDI Remote/Driver Scripts/Local"
    if [ -d "$HOME/Documents/Steinberg/${DAW}" ] && [ "$INSTALLED" = false ]; then
        install_js "$DAW_DIR" "${DAW}"
        INSTALLED=true
    fi
done

if [ "$INSTALLED" = false ]; then
    echo "  ⚠ Nuendo/Cubase folder not found"
    echo "  Copy Ableton_Push2.js manually to:"
    echo "  ~/Documents/Steinberg/<DAW>/MIDI Remote/Driver Scripts/Local/Ableton/Push2/"
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Installation complete!"
echo ""
echo "  The bridge creates virtual MIDI ports automatically."
echo "  No IAC Driver configuration needed."
echo ""
echo "  To run the bridge:"
echo "    cd $PROJECT_DIR/src"
echo "    python3 main.py"
echo ""
echo "  To configure Nuendo:"
echo "    Studio → Studio Setup → MIDI Remote"
echo "    Input:  NuendoBridge Out"
echo "    Output: NuendoBridge In"
echo "═══════════════════════════════════════════════"
