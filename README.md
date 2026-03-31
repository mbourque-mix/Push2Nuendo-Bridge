# Push 2 / Nuendo Bridge

Turn your **Ableton Push 2** into a full-featured control surface for **Steinberg Nuendo 14** (and Cubase 14+).

![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)

## Features

### Mixer Control
- **Volume** — 8 track faders via encoders with VU meters and peak clip detection
- **Pan** — Panorama control with visual feedback
- **Mute / Solo / Monitor / Record** — Toggle per track with LED indicators
- **Bank navigation** — Browse tracks in groups of 8

### Sends
- 8 sends per selected track with destination names
- On/Off toggle, Pre/Post fader toggle
- Level control via encoders
- Track navigation with ◄►

### Inserts
- Scan and display 8 insert plugins per track
- Bypass toggle per slot
- Plugin parameter control with bank navigation
- Open plugin UI, Deactivate plugin
- Track navigation with ◄►

### Quick Controls (Device)
- 8 Quick Controls per selected track
- Open instrument UI via lower row button
- Track navigation with ◄►

### Transport
- Play / Stop / Record
- Cycle (Loop) toggle
- Metronome toggle
- Play LED: white (stop), green (play), purple (play + loop)

### Automation
- Cycle: Off → Read → Read+Write → Write → Off
- Automate button LED: white (off), green (read), red (write)
- Per-track R/W indicators on screen

### Touchstrip
- 3 modes (cycle with Shift+Layout): Pitch Bend / Mod Wheel / Volume Fader
- Volume mode controls the selected track's fader

### Additional Features
- Track color display from Nuendo
- Smart track name abbreviation (16 chars)
- Long press upper row (1s) → Open instrument UI
- Add Track / New Track Version buttons
- Duplicate Track / Duplicate Track Version (Shift)
- Undo (Shift+Delete)
- Note input with drum and chromatic modes
- Scale selector
- Note Repeat with subdivision control
- Control Room integration

## Requirements

- **Ableton Push 2** (connected via USB)
- **Steinberg Nuendo 14** (or Cubase 14+)
- **Python 3.9+**
- **Virtual MIDI ports**:
  - macOS: IAC Driver (built-in)
  - Windows: [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
- **libusb** (for Push 2 USB communication)

## Installation

### 1. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up virtual MIDI ports

#### macOS (IAC Driver)
1. Open **Audio MIDI Setup** (Applications → Utilities)
2. Menu **Window → Show MIDI Studio**
3. Double-click **IAC Driver**
4. Check **Device is online**
5. Create two ports:
   - `Push2-To-Nuendo`
   - `Nuendo-To-Push2`

#### Windows (loopMIDI)
1. Install [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)
2. Create two ports:
   - `Push2-To-Nuendo`
   - `Nuendo-To-Push2`

### 3. Install the Nuendo MIDI Remote script

Copy `Ableton_Push2.js` to:

- **macOS**: `~/Documents/Steinberg/Nuendo 14/MIDI Remote/Driver Scripts/Local/`
- **Windows**: `%APPDATA%\Steinberg\Nuendo 14\MIDI Remote\Driver Scripts\Local\`

Create the `Local` folder if it doesn't exist.

### 4. Configure Nuendo

1. Open Nuendo
2. Go to **Studio → Studio Setup → MIDI Remote**
3. The script should appear as "Ableton Push 2"
4. Assign the MIDI ports:
   - Input: `Push2-To-Nuendo`
   - Output: `Nuendo-To-Push2`

### 5. Run the bridge

```bash
cd src
python main.py
```

Or if no `main.py`:
```bash
cd src
python -c "
from state import AppState
from nuendo_link import NuendoLink
from push2_controller import Push2Controller

state = AppState()
link = NuendoLink(state)
link.start()
ctrl = Push2Controller(state, link)
ctrl.start()

import time
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    ctrl.stop()
    link.stop()
"
```

## Usage

### Button Mapping

| Push 2 Button | Function |
|---------------|----------|
| Mix | Volume mode (Shift: Track mode) |
| Clip | Sends mode (Shift: Pan mode) |
| Device | Quick Controls mode |
| Browse | Inserts mode |
| ◄ ► | Bank navigation / Track navigation (in Sends/Inserts/Device) |
| Play | Play/Stop |
| Record | Record |
| Fixed Length | Cycle/Loop toggle |
| Metronome | Metronome toggle |
| Automate | Automation cycle (Off→R→RW→W→Off) |
| Add Track | Add Track dialog |
| New | New Track Version |
| Duplicate | Duplicate Track (Shift: Duplicate Track Version) |
| Delete | Delete (Shift: Undo) |
| Shift+Layout | Touchstrip mode cycle (Pitch/Mod/Volume) |
| Mute | Mute mode (toggle: Monitor mode) |
| Solo | Solo mode (toggle: Record arm mode) |
| Long press upper row | Open instrument UI |

### MIDI Channel Allocation

| Channel | Usage |
|---------|-------|
| 1 (0xB0) | Main controls (volume, pan, transport, selection, VU) |
| 2 (0xB1) | Insert parameters (CC 20-27), param bank nav, deactivate |
| 3 (0xB2) | Send levels for selected track (CC 20-27) |
| 4 (0xB3) | Insert bypass toggle (CC 20-27) |
| 5 (0xB4) | Quick Controls (CC 56-63) |

## Troubleshooting

- **Push 2 not found**: Make sure it's connected via USB, libusb is installed, and Ableton Live is not running
- **No connection to Nuendo**: Check that virtual MIDI ports are active and correctly assigned in Studio Setup
- **Peak clip on startup**: Normal — wait 2 seconds after connecting, artifacts are filtered automatically
- **Track names not loading**: Press Shift+upper row or navigate with ◄► to force a refresh

## License

This project is licensed under the GNU General Public License v3.0 — see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! This project uses the [Developer Certificate of Origin (DCO)](https://developercertificate.org/). All commits must be signed off with `git commit -s`. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Support

If you find this project useful, consider buying me a coffee:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg)](https://buymeacoffee.com/mbourque)

## Credits

Built with [push2-python](https://github.com/ffont/push2-python) and the [Steinberg MIDI Remote API](https://steinbergmedia.github.io/midiremote_api_doc/).
