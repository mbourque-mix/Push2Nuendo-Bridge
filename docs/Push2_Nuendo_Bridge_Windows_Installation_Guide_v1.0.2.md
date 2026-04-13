# Push 2 / Nuendo Bridge — Windows Installation Guide

> **Version:** 1.0.2  
> **Platform:** Windows 10 / 11  
> **DAW:** Steinberg Nuendo 14+ (or Cubase 14+)  
> **GitHub:** [github.com/mbourque-mix/Push2Nuendo-Bridge](https://github.com/mbourque-mix/Push2Nuendo-Bridge)

---

## Important Notice

The Push 2 / Nuendo Bridge has been developed and tested on macOS. This guide documents how to get it running on Windows from source. While the underlying code is cross-platform (Python), **Windows support is experimental** — you may encounter issues that don't exist on macOS. Feedback and bug reports via GitHub Issues are welcome.

---

## Overview

The bridge is a Python application that communicates with your Ableton Push 2 over USB and with Nuendo via virtual MIDI ports. On macOS, the app creates its own virtual MIDI ports automatically. On Windows, this is not possible (a limitation of the Windows MIDI subsystem), so you need **loopMIDI** to create the virtual ports manually.

**Architecture:**

```
Push 2  ←── USB ──→  Bridge (Python)  ←── loopMIDI ports ──→  Nuendo (MIDI Remote JS Script)
                          │
                          └── BridgeNotes (loopMIDI) ──→  Nuendo (MIDI instrument input)
```

---

## Prerequisites

Before you start, make sure you have:

- An **Ableton Push 2** connected via USB
- **Steinberg Nuendo 14+** (or Cubase 14+) installed
- An internet connection (for downloading tools and dependencies)
- **Ableton Live must NOT be running** — it locks the Push 2's MIDI ports exclusively

---

## Step 1 — Install Python

The bridge requires Python 3.9 or later.

1. Go to [python.org/downloads](https://www.python.org/downloads/) and download the latest Python 3 installer for Windows.
2. Run the installer. **Critical:** check the box **"Add Python to PATH"** on the first screen before clicking Install.
3. Once installed, open a **Command Prompt** (press `Win + R`, type `cmd`, press Enter) and verify:

```
python --version
```

You should see something like `Python 3.12.x`. If you get an error, Python was not added to PATH — run the installer again and select "Modify" to enable the PATH option.

Also verify pip is available:

```
pip --version
```

---

## Step 2 — Install Git (if not already installed)

You'll need Git to clone the repository and to install one of the Python dependencies.

1. Download Git for Windows from [git-scm.com](https://git-scm.com/download/win).
2. Run the installer with default options.
3. Verify in a **new** Command Prompt:

```
git --version
```

---

## Step 3 — Download the Bridge from GitHub

Open a Command Prompt and run:

```
cd %USERPROFILE%\Documents
git clone https://github.com/mbourque-mix/Push2Nuendo-Bridge.git
cd Push2Nuendo-Bridge
```

This creates a `Push2Nuendo-Bridge` folder in your Documents directory containing all the source files.

Alternatively, you can download the ZIP from the GitHub page: click the green **"Code"** button → **"Download ZIP"**, then extract it to a location of your choice.

---

## Step 4 — Install libusb (USB driver for Push 2)

The Push 2 communicates over USB using the `libusb` protocol. On Windows, you need to install a compatible USB driver using **Zadig**.

1. **Connect your Push 2** via USB and power it on. Wait for Windows to recognize it.
2. Download **Zadig** from [zadig.akeo.ie](https://zadig.akeo.ie/).
3. Run Zadig (no installation needed — it's a standalone .exe).
4. In the menu bar, click **Options → List All Devices**.
5. In the dropdown, find and select **"Ableton Push 2"** (the display/bulk interface, not the MIDI interface). If you see multiple entries for Push 2, select the one that is **not** labeled as a MIDI device — typically the one showing "USB ID: 2982:1967" or similar.
6. On the right side, make sure **WinUSB** is selected as the target driver (this is usually the default).
7. Click **"Replace Driver"** (or "Install Driver" if no driver is currently assigned).
8. Wait for the installation to complete. You should see a success message.

> **Warning:** Only replace the driver for the Push 2 display/bulk interface. Do **not** replace the driver for the Push 2 MIDI interface — doing so would break MIDI communication.

> **Note:** If you're unsure which device to select in Zadig, temporarily unplug the Push 2, note which devices disappear from the list, then plug it back in. The new entries are the Push 2.

---

## Step 5 — Install Python Dependencies

Open a Command Prompt, navigate to the project folder, and install the required Python packages:

```
cd %USERPROFILE%\Documents\Push2Nuendo-Bridge
pip install -r requirements.txt
```

The `push2-python` library is installed from GitHub (not PyPI). If you see an error related to this package, install it manually:

```
pip install git+https://github.com/ffont/push2-python.git
```

Other key dependencies that should be installed automatically include: `python-rtmidi`, `mido`, `Pillow`, `numpy`, and `pyusb`.

To verify everything installed correctly:

```
python -c "import push2_python; import mido; import rtmidi; print('All dependencies OK')"
```

---

## Step 6 — Install and Configure loopMIDI

On macOS, the bridge creates virtual MIDI ports automatically. On Windows, you need loopMIDI to provide these ports.

1. Download **loopMIDI** from [tobias-erichsen.de/software/loopmidi.html](https://www.tobias-erichsen.de/software/loopmidi.html).
2. Install and launch loopMIDI.
3. Create the following four virtual MIDI ports by typing each name in the "New port name" field and clicking the **"+"** button:

| Port Name | Purpose |
|-----------|---------|
| `NuendoBridge In` | Nuendo sends control data to the bridge |
| `NuendoBridge Out` | Bridge sends control data to Nuendo |
| `BridgeNotes` | Bridge sends note/pad data to Nuendo |
| `BridgeNotes In` | Nuendo sends note playback data to the bridge |

> **Critical:** The port names must match **exactly** (including capitalization and spaces). The bridge and the Nuendo script look for these specific names.

4. Make sure loopMIDI is set to **start with Windows** (right-click the loopMIDI tray icon → check "Autostart"). The virtual ports must be available before the bridge and Nuendo are launched.

---

## Step 7 — Install the Nuendo MIDI Remote Script

The bridge includes a JavaScript file (`Ableton_Push2.js`) that acts as the Nuendo-side MIDI Remote script. This file tells Nuendo how to communicate with the bridge.

1. Locate the script file in the downloaded repository. It should be at:

```
Push2Nuendo-Bridge\Ableton_Push2.js
```

2. Copy this file to Nuendo's MIDI Remote scripts folder. The default location is:

```
%APPDATA%\Steinberg\Nuendo 14+\MIDI Remote\Driver Scripts\Local\
```

To navigate there quickly: press `Win + R`, paste the path above, and press Enter. If the `Local` folder does not exist, create it.

For **Cubase**, the path is similar — replace `Nuendo 14+` with your Cubase version (e.g., `Cubase 14`).

> **Tip:** You can also open this path from within Nuendo by going to **Studio → Studio Setup → MIDI Remote**, clicking on a script, and choosing "Open Script Folder."

---

## Step 8 — Configure Nuendo

1. Launch **Nuendo** (make sure loopMIDI is already running with the four ports created).
2. Go to **Studio → Studio Setup**.
3. In the left panel, select **MIDI Remote**.
4. The script should appear listed as **"Ableton Push 2"**. If it doesn't, click **"Reload Scripts"** or restart Nuendo.
5. Assign the MIDI ports as follows:

| Script Port | Assign to (loopMIDI port) |
|-------------|---------------------------|
| NuendoBridge Out (Input) | `NuendoBridge Out` |
| NuendoBridge In (Output) | `NuendoBridge In` |

The naming can feel a bit counterintuitive: "NuendoBridge Out" is the port the *bridge* writes to, and Nuendo *reads* from it (hence it's an Input from Nuendo's perspective).

6. For note input (playing instruments from the Push 2 pads), you also need to set up the `BridgeNotes` port:
   - Go to **Studio → Studio Setup → MIDI Port Setup**.
   - Make sure **BridgeNotes** is visible and enabled as an input.
   - In your MIDI or Instrument tracks, set the input to **BridgeNotes**.

7. Click **OK** to close Studio Setup.

---

## Step 9 — Run the Bridge

1. Make sure your **Push 2 is connected via USB** and powered on.
2. Make sure **Ableton Live is closed** (it locks the Push 2 MIDI ports).
3. Make sure **loopMIDI is running** with the four ports active.
4. Open a Command Prompt and run:

```
cd %USERPROFILE%\Documents\Push2Nuendo-Bridge\src
python main.py
```

On Windows, the bridge runs in **terminal mode** (the macOS menu bar interface is not available). You should see output similar to:

```
╔═══════════════════════════════════════════════╗
║       Push 2 / Nuendo Bridge  v1.0.2          ║
╚═══════════════════════════════════════════════╝

[1/3] Connecting to MIDI ports...
  ✓ MIDI ports connected
[2/3] Connecting to Push 2...
  ✓ Push 2 connected
[3/3] Bridge is running!

  Press Ctrl+C to stop.
```

If the bridge connects successfully, you should see the Push 2 display come alive with your Nuendo mixer channels.

To stop the bridge, press **Ctrl+C** in the Command Prompt window.

---

## Step 10 — Verify Everything Works

Once the bridge is running and Nuendo is open with a project:

1. **Mixer display:** The Push 2 screen should show 8 channel strips with track names, volume levels, and VU meters matching your Nuendo mixer.
2. **Encoders:** Turn the 8 encoders above the display — they should control track volume in Nuendo.
3. **Bank navigation:** Press the ◄ ► buttons to navigate through tracks in groups of 8.
4. **Transport:** Press Play, Stop, and Record on the Push 2 — they should control Nuendo's transport.
5. **Pads:** Switch to pad mode and press pads — notes should be sent to the selected MIDI/Instrument track via the BridgeNotes port.

---

## Creating a Startup Shortcut (Optional)

To make launching the bridge easier, you can create a batch file:

1. Open Notepad and paste:

```batch
@echo off
title Push 2 / Nuendo Bridge
echo Starting Push 2 / Nuendo Bridge...
echo.
echo Make sure loopMIDI is running and Push 2 is connected.
echo Press any key to continue...
pause >nul
cd /d "%USERPROFILE%\Documents\Push2Nuendo-Bridge\src"
python main.py
pause
```

2. Save as `Start Bridge.bat` on your Desktop (select "All Files" as file type).
3. Double-click the batch file whenever you want to launch the bridge.

---

## Troubleshooting

### "Push 2 not found" or "MIDI Push 2 introuvable"

- Make sure the Push 2 is connected via USB and powered on.
- Make sure **Ableton Live is not running** — it locks the Push 2 MIDI ports exclusively.
- Verify the Zadig driver was installed correctly (Step 4). You can re-run Zadig to check.
- Try unplugging and re-plugging the Push 2.

### "Could not open MIDI ports"

- Make sure **loopMIDI is running** and that the four ports (NuendoBridge In, NuendoBridge Out, BridgeNotes, BridgeNotes In) are listed and active.
- Verify the port names match exactly — capitalization and spacing matter.
- Make sure no other application is using the loopMIDI ports exclusively.

### Push 2 display shows nothing / stays dark

- The bridge may not have connected to the USB display interface. Check the Zadig driver installation.
- Try restarting the bridge.
- On some systems, you may need to run the Command Prompt **as Administrator**.

### Nuendo doesn't show the MIDI Remote script

- Make sure `Ableton_Push2.js` is in the correct folder (`%APPDATA%\Steinberg\Nuendo 14+\MIDI Remote\Driver Scripts\Local\`).
- In Nuendo, go to **Studio → Studio Setup → MIDI Remote** and click **Reload Scripts**.
- Restart Nuendo.

### Encoders/buttons don't respond in Nuendo

- Check that the MIDI port assignments in **Studio Setup → MIDI Remote** are correct.
- Open **Studio → Studio Setup → MIDI Port Setup** and make sure the loopMIDI ports are enabled (not hidden or disabled).
- In Nuendo, check that the MIDI Remote script is loaded (the lower zone should show the MIDI Remote panel).

### Bridge loses sync with Nuendo

- Stop the bridge (Ctrl+C) and restart it.
- In Nuendo, you may also need to reload the MIDI Remote script: open **Studio → Studio Setup → MIDI Remote**, and click **Reload Scripts**.

### Python or pip not recognized

- Python was not added to PATH during installation. Re-run the Python installer, select "Modify", and make sure the PATH option is checked.
- Alternatively, use the full path: `C:\Users\YourName\AppData\Local\Programs\Python\Python312\python.exe`

### "ModuleNotFoundError: No module named 'push2_python'"

- Install it directly from GitHub:

```
pip install git+https://github.com/ffont/push2-python.git
```

### Listing available MIDI ports (for debugging)

Run this command to see all MIDI ports visible to Python:

```
python -c "import mido; print('IN:', mido.get_input_names()); print('OUT:', mido.get_output_names())"
```

You should see the four loopMIDI ports in both the input and output lists, plus the Push 2 MIDI ports.

---

## Summary — Quick Checklist

1. ☐ Python 3.9+ installed (with PATH)
2. ☐ Git installed
3. ☐ Repository cloned from GitHub
4. ☐ Zadig: WinUSB driver installed for Push 2 display interface
5. ☐ `pip install -r requirements.txt` completed
6. ☐ loopMIDI installed and running with 4 ports: `NuendoBridge In`, `NuendoBridge Out`, `BridgeNotes`, `BridgeNotes In`
7. ☐ `Ableton_Push2.js` copied to Nuendo's MIDI Remote scripts folder
8. ☐ Nuendo: MIDI Remote ports assigned correctly
9. ☐ Ableton Live closed
10. ☐ Bridge launched: `python main.py` from the `src` folder
