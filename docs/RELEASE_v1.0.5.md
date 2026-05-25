# Push 2 / Nuendo Bridge v1.0.5

Turn your Ableton Push 2 into a full-featured control surface for Steinberg Nuendo / Cubase.

## Downloads

| Platform | File | Requirements |
|----------|------|--------------|
| **macOS** (Apple Silicon) | `Push2NuendoBridge-v1.0.5-macOS.zip` | macOS 11+. Self-contained — **no Homebrew, libusb or Python needed**. Intel Macs: run from source (see User Guide). |
| **Windows** (10/11) | `Push2NuendoBridge-v1.0.5-Windows.zip` | loopMIDI. Standalone `.exe` — no Python, no Zadig. |

Both packages include the `Ableton_Push2.js` MIDI Remote script and the PDF guides.

## ✨ New Features

- **Keyswitch pad layouts** — the Layout button now cycles 64 notes / 56 notes + 8 keyswitches / 48 notes + 16 keyswitches / Drum. Keyswitch pads light orange on the bottom row(s) and trigger user-defined notes (great for articulations). Long-press Layout to configure: start note, per-pad overrides, Chromatic/Naturals, Latch (the keyswitch section is monophonic), Reset.
- **XY pad** (Session button) — the 64 pads morph two parameters of the selected track (Volume / Pan / Quick Controls) or raw MIDI CC. Relative, pressure-weighted input (no jump on touch) with two-finger interpolation; per-axis category/parameter, sensitivity & smoothing, plus track Mute/Solo/Monitor/Record.
- **Two octatonic scales** (WH and HW) added to the Scale menu.
- **Per-track automation feedback** — each bank track's Read/Write mode is now shown on screen, not just the selected track's.
- **Pad note range** displayed in the Mix footer (keyswitch pads excluded).
- **Windows system tray app** — runs from the tray (status, Open Plugin Mapper, Show Log, Quit) instead of a console. Use `--terminal` for the classic console.
- **macOS app is now fully self-contained** — the libusb USB runtime is bundled, so Homebrew / `brew install libusb` is no longer required.
- **Rescan** moved to the Setup page (lower-row button 8).

## 🐛 Bug Fixes

- Control Room **Main reset** (Shift+Touch) now lands on an exact **0.00 dB** instead of −0.01 dB.
- **Channel Strip** module values now appear immediately on entering a module and stay visible.
- **Saturator and Limiter** encoders now respond to changes.
- **Inserts** page no longer shows an insert duplicated in another slot (display only).
- Removed the non-functional **CC Pick-up** mode (the MIDI CC page is Absolute only).

## 📦 Install

- **macOS:** copy the `.app` to `/Applications`, clear the quarantine flag (`xattr -dr com.apple.quarantine "/Applications/Push2 Nuendo Bridge_v1.0.5.app"`), copy `Ableton_Push2.js` to the Nuendo MIDI Remote folder.
- **Windows:** unzip anywhere, set up loopMIDI's four ports, run the `.exe`, copy `Ableton_Push2.js` to the MIDI Remote folder.

See the **User Guide** and **Windows Installation Guide** PDFs for full step-by-step instructions.

> **Note:** Plugin Browser, DirectAccess insert control and the Channel Strip extended-parameter / EQ-curve pages require Nuendo 15+ (MIDI Remote API 1.3). All other features work with Nuendo 14+.
