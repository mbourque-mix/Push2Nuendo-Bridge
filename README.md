# Push 2 / Nuendo Bridge

Turn your **Ableton Push 2** into a full-featured control surface for **Steinberg Nuendo** (and Cubase 14+).

![Version](https://img.shields.io/badge/version-1.0.3-brightgreen.svg)
![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)

🌐 **Website:** [push2bridge.kaikuaudio.com](https://push2bridge.kaikuaudio.com)

---

## Features

### Mixer Control
- **Volume** — 8 track faders via encoders with VU meters and peak clip detection
- **Pan** — Panorama control with visual L/C/R feedback
- **Track** — Combined Vol + Pan + 6 Sends for the selected track
- **Mute / Solo / Monitor / Record** — Toggle per track with colored LED indicators
- **Long press** in Mute mode = Monitor toggle, in Solo mode = Record Arm toggle
- **Clear All** — Shift+Mute/Solo clears all mutes, solos, monitors, or rec arms
- **Edit Channel Settings** — Double press upper row to open
- **Bank navigation** — Browse tracks in groups of 8, Shift+◄► nudges by 1 track
- **Adaptive text color** — Track headers automatically switch between white and black text based on background luminance

### Sends
- 8 sends per selected track with destination names and level display
- On/Off toggle, Pre/Post fader toggle
- Level control via encoders
- Track navigation with ◄►

### Inserts
- Scan and display up to 16 insert plugins per track (2 banks of 8)
- Bypass toggle per slot via DirectAccess (instant response)
- Plugin parameter control with bank navigation
- Short press = enter parameters, Long press (0.5s) = open plugin UI only
- Open plugin UI, Deactivate plugin
- **Plugin Mapper integration** — mapped plugins show ★ MAPPED indicator and use custom parameter pages
- Mute/Solo/Monitor/Rec on buttons 5-8
- Track navigation with ◄►

### Plugin Browser *(Nuendo 15+ / API 1.3)*
- **Add Device** button opens the Plugin Browser
- Phase 1: Select target insert slot (upper row buttons)
- Phase 2: Browse plugins with encoders (page scroll + fine scroll)
- Load plugins directly from the Push 2 display
- **Collection picker** — browse all available Nuendo plugin collections with a dedicated selection page
- Auto-return to Inserts mode after loading

### Plugin Mapper *(optional)*
- Web-based parameter mapping tool at http://localhost:8100
- **Scanner** — discovers VST3 plugins and extracts parameters using Spotify's pedalboard library (GPL-3.0)
- **Drag-and-drop UI** — create pages of 8 encoders with custom labels
- **Fuzzy matching** — pedalboard parameter names matched to Nuendo's DirectAccess parameters automatically
- Mappings saved in `~/.push2bridge/mappings/` (shareable JSON files)
- Integrated into the bridge — starts automatically if dependencies are installed
- Access via macOS menu bar (Plugin Mapper) or directly at http://localhost:8100
- Install dependencies: `pip install fastapi uvicorn pedalboard`

### Quick Controls (Device)
- 8 Quick Controls per selected track
- Open instrument UI
- Mute/Solo/Monitor/Rec on buttons 5-8
- Track navigation with ◄►

### Transport
- Play / Stop / Record
- Cycle (Loop) toggle
- Metronome toggle
- Undo
- Play LED: white (stop), green (play), purple (play + loop)
- Record LED: orange (idle), blinking red (track armed), solid red (recording)

### Automation
- Cycle: Off → Read → Read+Write → Write → Off
- Automate button LED: white (off), green (read), red (write)
- Per-track R/W indicators on screen

### Control Room
- 4 pages: Main, Phones, Cues, Sources
- Full knob control for levels, click, listen, talkback
- Master encoder always controls Main level

### Touchstrip
- 3 modes (cycle with Shift+Layout): Pitch Bend / Mod Wheel / Volume Fader

### Setup Page
- **Aftertouch Mode**: Polyphonic, Channel, or Off
- **Velocity Curve**: Linear, Logarithmic, Exponential, S-Curve, Fixed (with adjustable value)
- **CC Mode**: Absolute or Pick-up (direction-change detection to prevent parameter jumps)
- **About**: Bridge version and JS Script version display

### MIDI CC Controller (Shift+Note)
- 8 assignable CC faders with real-time value bars
- CC number editing mode via upper row buttons
- On/Off toggle via lower row buttons (for sustain, etc.)
- CC Mode (Absolute/Pick-up) configurable in Setup page
- Default CCs: Mod Wheel, Breath, Volume, Balance, Pan, Expression, Sustain, Portamento

### Note Input
- Chromatic and drum pad modes
- Scale selector with root note
- Note Repeat with adjustable BPM
- Adjustable velocity curves and fixed velocity

### Additional Features
- Track color display from Nuendo
- Long press upper row (1s) → Open instrument UI
- Double press upper row → Edit Channel Settings
- Add Track / New Track Version / Duplicate Track
- Full 960×160 pixel Push 2 display rendering with bold headers

---

## Requirements

- **Ableton Push 2** (connected via USB)
- **Steinberg Nuendo 14+** (or Cubase 14+)
- **macOS 11+** or **Windows 10/11**
- **libusb** (macOS: `brew install libusb`)

**Nuendo 15+ features:** Plugin Browser (Add Device) and DirectAccess-based insert control require MIDI Remote API 1.3. All other features work with Nuendo 14+.

For Windows, you also need:
- **Python 3.9+**
- **[loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)** for virtual MIDI ports
- **[Zadig](https://zadig.akeo.ie/)** for USB driver

For the Plugin Mapper (optional):
```bash
pip install fastapi uvicorn pedalboard
```

---

## Installation

### macOS — Standalone App (Recommended)

1. Install Homebrew (if needed): visit [brew.sh](https://brew.sh)
2. Install libusb: `brew install libusb`
3. Copy **Push2 Nuendo Bridge.app** to `/Applications`
4. Copy **Ableton_Push2.js** to:
   ```
   ~/Documents/Steinberg/Nuendo/MIDI Remote/Driver Scripts/Local/Ableton/Push2/
   ```
5. Launch the app — a **P2** icon appears in the menu bar
6. Open Nuendo — the MIDI Remote script configures itself automatically

### macOS — From Source

```bash
brew install libusb python3
pip3 install -r requirements.txt
cd src && python3 main.py
```

### Windows

See the **[Windows Installation Guide](docs/Push2_Nuendo_Bridge_Windows_Installation_Guide_v1_0_2.pdf)** for detailed step-by-step instructions including Python, Zadig, loopMIDI, and Nuendo configuration.

Quick start:
```bash
pip install -r requirements.txt
cd src
python main.py --terminal
```

---

## Button Reference

| Push 2 Button | Function | Shift + Button |
|---------------|----------|----------------|
| Mix | Volume mode | Track mode |
| Clip | Sends mode | Pan mode |
| Device | Quick Controls | |
| Browse | Inserts mode | |
| Add Device | Plugin Browser | |
| Note | MIDI note pads | MIDI CC controller |
| Setup | Setup page | |
| ◄ ► | Bank navigation (8) | Nudge ±1 (Vol/Pan) |
| Play | Start playback | |
| Record | Record toggle | |
| Fixed Length | Cycle/Loop toggle | |
| Automate | Automation cycle | |
| Metronome | Metronome toggle | |
| Mute | Mute / Monitor toggle | Clear all mutes (or monitors) |
| Solo | Solo / Rec arm toggle | Clear all solos (or rec arms) |
| User | Control Room mode | |
| Layout | Drum/Chromatic toggle | Touchstrip mode cycle |
| Upper row (long) | Open instrument UI | Clear peak clip |
| Upper row (double) | Edit Channel Settings | |

## MIDI Channel Allocation

| Channel | Usage |
|---------|-------|
| 1 (0xB0) | Mixer controls (volume, pan, transport, selection, VU) |
| 2 (0xB1) | Insert plugin parameters |
| 3 (0xB2) | Send levels for selected track |
| 4 (0xB3) | Insert bypass toggles |
| 5 (0xB4) | Quick Controls |
| 6 (0xB5) | Control Room knobs and buttons |
| 7 (0xB6) | Bank zone sends |
| 8 (0xB7) | DirectAccess commands (plugin browser, bypass, edit) |
| 9 (0xB8) | DirectAccess encoder control (mapped plugin parameters) |
| 16 (0xBF) | Heartbeat (connection monitoring) |

---

## Troubleshooting

- **Push 2 not found**: Make sure it's connected via USB, libusb is installed, and Ableton Live is not running
- **No connection to Nuendo**: Check that the bridge is running and MIDI Remote ports are correctly assigned
- **Plugin Browser not working**: Requires Nuendo 15+ (API 1.3)
- **Plugin Mapper not loading**: Install dependencies with `pip install fastapi uvicorn pedalboard`
- **Peak clip on startup**: Normal — filtered automatically after a 3-second grace period
- **Track names not loading**: Navigate with ◄► to force a bank refresh

---

## Documentation

- **[User Guide](docs/Push2_Nuendo_Bridge_User_Guide_v1_0_3.pdf)** — Complete installation and usage manual
- **[Release Notes](docs/Push2_Nuendo_Bridge_Release_Notes_v1_0_3.pdf)** — Version history
- **[Plugin Mapper Guide](docs/Push2_Nuendo_Bridge_Plugin_Mapper_Guide_v1_0.pdf)** — Plugin Mapper setup and usage
- **[Windows Installation Guide](docs/Push2_Nuendo_Bridge_Windows_Installation_Guide_v1_0_2.pdf)** — Step-by-step Windows setup

---

## License

This project is licensed under the **GNU General Public License v3.0** — see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! This project uses the [Developer Certificate of Origin (DCO)](https://developercertificate.org/). All commits must be signed off with `git commit -s`. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Support

If you find this project useful, consider buying me a coffee:

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg)](https://buymeacoffee.com/mbourque)

## Credits

Built with [push2-python](https://github.com/ffont/push2-python) and the [Steinberg MIDI Remote API](https://steinbergmedia.github.io/midiremote_api_doc/).
