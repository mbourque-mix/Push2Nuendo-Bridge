# Push 2 / Nuendo Bridge

Turn your **Ableton Push 2** into a full-featured control surface for **Steinberg Nuendo** (and Cubase 14+).

![Version](https://img.shields.io/badge/version-1.0.6-brightgreen.svg)
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

### Channel Strip *(Nuendo 15+ / API 1.3)*
- **Overview** — Gate, Comp, EQ, Tools, Sat, Limiter shown as Cubase-coloured banners with bold names; lower row bypasses each section (amber when engaged)
- **Module sub-pages** — 8 encoders per module, including **extended parameters not in Cubase's bank zone** via DirectAccess (VintageCompressor Ratio/Mix, Tube Comp Character/High-Ratio, Standard Comp DryMix/Hold, DeEsser side-chain filter + Diff, Magneto II Dual/Oversample, Maximizer Release/Recover, Brickwall Link/Oversample, Noise Gate Hold/Analysis, …)
- **Channel EQ page (EQ-Eight style)** — band selector, Type/Freq/Q/Gain per band, PreFilter LC/HC freq + on/off, PreGain, and a **live magnitude curve** (4 bands + PreFilter) with numbered band markers
- **Bidirectional feedback** — the curve, pills and LEDs update whether you change a parameter from the Push or directly in Nuendo
- **Edit Channel Settings** — lower row 8 (Channel Strip) and Shift+Upper Row (Mix), window-open state shown white on screen and LED
- Variant chips mirror the active strip plugin (variant switching is done in Nuendo — the MIDI Remote API does not allow it from a controller)

### Plugin Browser *(Nuendo 15+ / API 1.3)*
- **Add Device** button opens the Plugin Browser
- Phase 1: Select target insert slot (upper row buttons)
- Phase 2: Browse plugins with encoders (page scroll + fine scroll)
- Load plugins directly from the Push 2 display
- **Collection picker** — browse all available Nuendo plugin collections with a dedicated selection page
- Auto-return to Inserts mode after loading

### Plugin Mapper *(optional)*
- Web-based parameter mapping tool at http://localhost:8100
- **Scanner** — discovers VST3 plugins (incl. Nuendo/Cubase stock plug-ins inside the app bundles, version-independent) and extracts parameters using Spotify's pedalboard library (GPL-3.0); user-configurable extra folders, multi-plugin VST3 shells, scan progress bar with Cancel/Skip, per-plugin rescan, clear hints for Intel-only / PACE-protected plug-ins
- **DirectAccess capture (Shift+Browse)** — capture parameters live from the running plugin inside Nuendo, for plug-ins the scanner can't read (iLok/PACE, Waves shells, Nuendo stock) — works for inserts **and** instruments
- **Drag-and-drop UI** — create pages of 8 encoders with custom labels; filters (manufacturer/kind/state/type), parameter search, slot-to-slot drag, mapping export/import
- **Edit Map** button on the Push (Inserts parameter page) opens the Mapper directly on the selected plugin
- **Fuzzy matching** — scanned parameter names matched to Nuendo's DirectAccess parameters automatically
- Mappings saved in `~/.push2bridge/mappings/` (shareable JSON files); after saving, press **↻ Reload** on the Push (Setup) to pick them up
- Integrated into the bridge — starts automatically; access via macOS menu bar / Windows tray or directly at http://localhost:8100
- **Nothing to install with the standalone app** — fastapi/uvicorn/pedalboard are bundled in the `.app`/`.exe`. Only source installs need `pip install fastapi uvicorn pedalboard`

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
- Master encoder controls the Main level by default; **hold Select** to control the Phones bus instead (the default can be swapped in Setup → CR Knob)
- Current CR / Phones level shown in the Mix footer

### Footswitch / Pedals
- Two pedal jacks supported: **jack 1 = CC 64**, **jack 2 = CC 69**
- Each pedal is configured on its own Setup page (Pedal 1 / Pedal 2)
- Assignable actions: **Sustain** (CC 64 passthrough to the instrument), **Play/Stop**, **Play**, **Stop**, **Record**, **Rec/Stop** (start recording, press again to stop), **Off**
- **Invert** option per pedal for normally-closed switches
- Defaults: Pedal 1 = Sustain, Pedal 2 = Play/Stop

### Touchstrip
- 3 modes (cycle with Shift+Layout): Pitch Bend / Mod Wheel / Volume Fader

### Setup Page
- **MIDI Ctrl** — Aftertouch Mode: Polyphonic, Channel, or Off
- **Vel Curve** — Velocity Curve: Linear, Logarithmic, Exponential, S-Curve, Fixed (with adjustable value)
- **CR Knob** — Master-encoder default: Main or Phones (Select gives the other)
- **Pedal 1 / Pedal 2** — Footswitch action + invert (see Footswitch / Pedals above)
- **Reload Script** (upper row 7) — re-scan tracks and re-sync the bridge's view of the project
- **About** — Bridge version and JS Script version display
- All Setup options are **saved to `~/.push2bridge/settings.json`** and restored on the next launch

### MIDI CC Controller (Shift+Note)
- 8 assignable CC faders with real-time value bars
- CC number editing mode via upper row buttons
- On/Off toggle via lower row buttons (for sustain, etc.)
- Absolute value output (these generic CCs have no value feedback from Nuendo)
- Default CCs: Mod Wheel, Breath, Volume, Balance, Pan, Expression, Sustain, Portamento

### Note Input
- Chromatic and drum pad modes
- Scale selector with root note (includes Piano and two Octatonic scales)
- **Keyswitch layouts** (Layout button cycles 64 / 56+8 KS / 48+16 KS / Drum): orange, user-configurable keyswitch pads on the bottom row(s), with latch and a monophonic keyswitch section. Long-press Layout to configure (start note, per-pad overrides, Chromatic/Naturals)
- Note Repeat with adjustable BPM
- Adjustable velocity curves and fixed velocity

### XY Pad (Session button)
- 64 pads morph two parameters of the selected track (Volume / Pan / Quick Controls) or raw MIDI CC
- Relative, pressure-weighted input (no jump on touch) with two-finger interpolation
- Per-axis category/parameter selection, sensitivity and smoothing, plus track Mute/Solo/Monitor/Record

### Navigation (Master button)
- Overlays four directional **D-pads** on the 64 pads (corners): Zoom, Scroll/cursor, Markers/locators, Nudge — each with hold-to-repeat
- The D-pads stay active across the mix pages, so you can navigate the timeline while you work
- **Hold Master** to flash an on-screen reminder of each D-pad; the screen otherwise keeps showing the mix
- Note / Scale / Session restore the normal pads

### Additional Features
- Track color display from Nuendo
- Mix footer shows the pad MIDI note range
- Long press upper row (1s) → Open instrument UI
- Double press upper row → Edit Channel Settings
- Add Track / New Track Version / Duplicate Track
- Full 960×160 pixel Push 2 display rendering with bold headers
- **Windows system tray** app (run with `--terminal` for the console version)

---

## Requirements

- **Ableton Push 2** (connected via USB)
- **Steinberg Nuendo 14+** (or Cubase 14+)
- **macOS 11+** or **Windows 10/11**

**Nuendo 15+ features:** Plugin Browser (Add Device) and DirectAccess-based insert control require MIDI Remote API 1.3. All other features work with Nuendo 14+.

**Nothing to install for end users** — the Windows `.exe` and the macOS `.app` bundle the Python interpreter, every dependency **and the libusb USB runtime**. No Homebrew, no `brew install libusb`, no Python. (libusb is only needed when **running from source**, where `brew install libusb` is still required on macOS.)

**Python (source / build only):** 3.9 – **3.11.9 maximum** (3.12 / 3.13 are not yet supported by the audio/MIDI dependencies). When running from source, `push2-python` must be installed from source:
```bash
pip install git+https://github.com/ffont/push2-python.git
```

For Windows, you also need:
- **[loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)** for virtual MIDI ports

(The Push 2's USB driver installs automatically on Windows — no Zadig needed.)

For the Plugin Mapper (optional, **source installs only** — these are bundled in the standalone `.app`/`.exe`):
```bash
pip install fastapi uvicorn pedalboard
```

---

## Installation

### macOS — Standalone App (Apple Silicon, Recommended)

The pre-built `.app` is **Apple Silicon (arm64) only**. On an M1/M2/M3 Mac, no Homebrew, libusb or Python is required — everything (including the libusb USB runtime) is bundled in the app. **Intel Macs:** use *From Source* below (or build an Intel `.app` with `scripts/build.sh` on an Intel machine).

1. Copy **Push2 Nuendo Bridge.app** to `/Applications`
2. The app is **not code-signed**, so macOS Gatekeeper blocks it on first launch. Remove the quarantine flag from Terminal (adjust the version in the name to match your copy):
   ```bash
   xattr -dr com.apple.quarantine "/Applications/Push2 Nuendo Bridge_v1.0.6.app"
   ```
3. Copy **Ableton_Push2.js** to:
   ```
   ~/Documents/Steinberg/Nuendo/MIDI Remote/Driver Scripts/Local/Ableton/Push2/
   ```
4. Launch the app — a **P2** icon appears in the menu bar
5. Open Nuendo — the MIDI Remote script configures itself automatically

### macOS — From Source (also the path for Intel Macs)

```bash
brew install libusb python@3.11
pip3.11 install -r requirements.txt
pip3.11 install git+https://github.com/ffont/push2-python.git
cd src && python3.11 main.py
```

To build a native standalone `.app` for your architecture (e.g. an Intel `.app` on an Intel Mac), run `bash scripts/build.sh` with the dependencies above installed.

### Windows

Windows ships as a **standalone `.exe`** — no Python, pip or command line required. See the **[Windows Installation Guide](docs/Push2_Nuendo_Bridge_Windows_Installation_Guide_v1_0_6.pdf)** for the full step-by-step (loopMIDI, Nuendo configuration).

Quick start:

1. Download **`Push2NuendoBridge-vX.Y.Z-Windows.zip`** from the [Releases](https://github.com/mbourque-mix/Push2Nuendo-Bridge/releases) page and unzip it anywhere.
2. Install **[loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html)** and create four ports: `NuendoBridge In`, `NuendoBridge Out`, `BridgeNotes`, `BridgeNotes In`.
3. **Plug in the Push 2** — Windows installs the USB driver (WinUSB) automatically the first time. No Zadig, no manual driver step.
4. **Double-click the `.exe`.** A console shows the status and a clickable Plugin Mapper link (`http://localhost:8100`).

> **Windows note:** the bridge and Ableton Live share the same Push 2 USB connection, so only one can control the Push at a time — close one to use the other. No driver change is needed to go back and forth (tested with Live 12). macOS is not affected.

> No Python install needed — the interpreter, all dependencies and the libusb runtime are bundled in the `.exe`.

**Building the `.exe` yourself:** run `scripts\build_windows.bat` on a Windows machine (PyInstaller cannot cross-compile), or let the `Build Windows .exe` GitHub Actions workflow build it on every `v*` tag.

Copy **Ableton_Push2.js** to (create the `Local\Ableton\Push2` sub-folders):
```
C:\Users\<user>\Documents\Steinberg\Nuendo\MIDI Remote\Driver Scripts\Local\Ableton\Push2\
```
For Cubase, replace `Nuendo` with `Cubase` in that path.

**If the script doesn't load automatically:** open a project → Studio → MIDI Remote Manager → **Add MIDI Controller Surface** → Vendor **Ableton**, Model **Push2**, MIDI In **NuendoBridge Out**, MIDI Out **NuendoBridge In**.

> ⚠️ **Avoid doubled pad notes:** in Studio Setup → MIDI Port Setup, uncheck **"In 'All MIDI Inputs'"** for both **Ableton Push 2** (Live Port) and **Ableton Push 2 User Port**. Otherwise every pad is received twice (once via BridgeNotes, once direct from the hardware).

---

## Button Reference

| Push 2 Button | Function | Shift + Button |
|---------------|----------|----------------|
| Mix | Volume mode (press again → Channel Strip) | Track mode |
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
- **push2-python error**: install from source — `pip install git+https://github.com/ffont/push2-python.git`; use Python ≤ 3.11.9
- **Doubled pad notes**: uncheck "In 'All MIDI Inputs'" for the Push 2 Live Port and User Port (Studio Setup → MIDI Port Setup)
- **No connection to Nuendo**: Check that the bridge is running and MIDI Remote ports are correctly assigned (or add the surface manually in MIDI Remote Manager)
- **Plugin Browser / Channel Strip / EQ curve not working**: Requires Nuendo 15+ (API 1.3)
- **Plugin Mapper not loading**: with the standalone app this shouldn't happen (everything is bundled) — when running from source, install the dependencies with `pip install fastapi uvicorn pedalboard`
- **Peak clip on startup**: Normal — filtered automatically after a 3-second grace period
- **Track names not loading**: Navigate with ◄► to force a bank refresh

---

## Documentation

- **[User Guide](docs/Push2_Nuendo_Bridge_User_Guide_v1_0_6.pdf)** — Complete installation and usage manual
- **[Release Notes](docs/Push2_Nuendo_Bridge_Release_Notes_v1_0_6.pdf)** — Version history
- **[Plugin Mapper Guide](docs/Push2_Nuendo_Bridge_Plugin_Mapper_Guide_v1_0.pdf)** — Plugin Mapper setup and usage
- **[Windows Installation Guide](docs/Push2_Nuendo_Bridge_Windows_Installation_Guide_v1_0_6.pdf)** — Step-by-step Windows `.exe` setup

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
