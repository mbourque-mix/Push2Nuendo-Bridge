# Push 2 Driver Switcher (Windows, Tier 1 — manual helper)

> ⚠️ **You probably do not need this on modern Ableton Live (12.x tested).**
> The bridge and Live share the same WinUSB driver — they just can't talk to
> the Push 2 at the same time (USB exclusive claim). Close one, open the
> other, done. No driver swap needed.
>
> This helper exists for edge cases only:
> - older Ableton Live versions that refuse to work with the WinUSB driver,
> - broken Zadig installs that need a clean reinstall,
> - workflows that strictly need to flip the driver for some reason.
>
> If you don't have a specific problem this tool solves, don't install it.

A small helper that flips the Push 2's Windows USB driver between:

- **Bridge mode** — WinUSB driver installed, so the bridge can talk to the Push 2 via libusb.
- **Live mode** — Ableton's default driver, so Ableton Live can use the Push 2.

It replaces the manual *Zadig → Bridge / Device Manager → Live* dance with a
single command (or double-click).

> 🧪 **Status: experimental, Windows-only, not shipped with releases.**
> Test in a VM before using on your main workstation.

---

## Layout

```
tools/driver-switch/
├── Push2-Driver-Switch.ps1     ← the script (PowerShell, self-elevating)
├── Push2-Driver-Switch.bat     ← double-click wrapper (calls the .ps1)
├── winusb-cache/               ← created automatically on first use (do not touch)
└── README.md                   ← this file
```

**No external binaries to download.** Everything runs on Windows' built-in
`pnputil` and the PowerShell PnP cmdlets.

## How it works (in one paragraph)

The helper relies on the fact that once you've run Zadig **once** to install
WinUSB on the Push 2, the WinUSB driver package is permanently in Windows'
*driver store*. On its first "Switch to Live" call, the helper exports that
driver package to a local `winusb-cache/` folder using
`pnputil /export-driver`. From then on, every flip is just two `pnputil`
commands: `/add-driver … /install` to go back to Bridge, and
`/remove-device` + `/delete-driver` + `/scan-devices` to go back to Live.
No Zadig, no `wdi-simple.exe`, no recompilation.

## One-time setup

1. **Run Zadig once** to install WinUSB on the Push 2 display/bulk interface
   (USB ID `2982:1967`) — exactly the procedure documented in the
   *Windows Installation Guide* PDF, Step 2.

2. While the Push 2 is **in Bridge mode** (WinUSB-bound), double-click
   `Push2-Driver-Switch.bat`. A UAC prompt appears, then the menu.

3. Choose **2 — Switch to Live mode**. On this first call the helper:
   - Exports the WinUSB driver package into `winusb-cache/` (automatic).
   - Removes the WinUSB binding so Live can use the Push.

   From now on, both directions are one-click — Zadig is no longer needed.

## Daily use

### Interactive (recommended)

Double-click `Push2-Driver-Switch.bat`. Choose:

- **1** to switch to **Bridge** mode (re-installs the cached WinUSB driver).
- **2** to switch to **Live** mode (removes the WinUSB binding).
- **3** to refresh the status table.
- **Q** to quit.

### Silent / scripted

```powershell
.\Push2-Driver-Switch.ps1 -To Bridge   # install WinUSB from cache
.\Push2-Driver-Switch.ps1 -To Live     # remove WinUSB, restore Ableton driver
.\Push2-Driver-Switch.ps1 -To Status   # just print the current state
```

Each silent invocation triggers a single UAC prompt, runs, and waits for Enter
before closing (so you can read the output).

## What it actually does

### Switch to Bridge
- Reads `winusb-cache/<inf-file>.inf` (populated automatically the first
  time you switched to Live).
- `pnputil /add-driver <cached.inf> /install` — installs the driver and
  binds it to matching present devices (the Push 2).

### Switch to Live
1. Enumerates current Push 2 USB devices, finds the one bound to `WinUSB`.
2. **Caches** the WinUSB driver package via `pnputil /export-driver` (only
   if `winusb-cache/` is empty — done once).
3. Reads each WinUSB device's INF path (`DEVPKEY_Device_DriverInfPath`).
4. `pnputil /remove-device <instanceId> /force` — removes the device node
   (equivalent of Device Manager → *Uninstall device*).
5. `pnputil /delete-driver <inf> /uninstall /force` — deletes the WinUSB
   driver package from the store (equivalent of the *Delete the driver
   software* tickbox).
6. `pnputil /scan-devices` — re-enumerates. Windows binds the next-best
   available driver → Ableton's, if Live is installed.

The MIDI interface is **always** left untouched.

## Troubleshooting

- **"no cached WinUSB driver to install"** — you haven't completed the
  one-time setup. Run Zadig once, then trigger one *Switch to Live* with
  the Push connected in Bridge mode so the helper can cache the driver.

- **The script does nothing / no UAC prompt** — PowerShell execution policy
  is blocking. Use the `.bat` wrapper (which sets `-ExecutionPolicy Bypass`
  for that single invocation), or run from an elevated PowerShell directly.

- **After "Switch to Live", Live still doesn't see the Push** — unplug and
  replug the USB cable once. If still nothing, the Ableton driver may not
  be in your driver store (rare unless you uninstalled Live). Reinstalling
  / repairing Live restores it.

- **After "Switch to Bridge", the bridge can't find the Push** — confirm the
  bridge `.exe` is launched fresh and that the Push 2 appears in Device
  Manager under *Universal Serial Bus devices* with the `WinUSB` driver.

- **`pnputil /export-driver` failed** — the device is no longer present, or
  the WinUSB binding was already removed. Reconnect the Push 2 (still in
  Bridge mode) and try again.

- **Cache got into a weird state** — delete the `winusb-cache/` folder
  entirely. The next *Switch to Live* will re-cache cleanly (you need to
  be back in Bridge mode for that to work — run Zadig once again if needed).

- **Anything else** — fall back to the manual procedure documented in the
  *Windows Installation Guide* PDF. The script is just a shortcut for what
  Zadig + Device Manager do.

## Caveats

- **Admin/UAC required every switch.** Intrinsic — Windows driver operations
  always need elevation. A future *Tier 2* design may use a pre-installed
  scheduled task to silence per-launch UAC.

- **Initial setup still needs Zadig.** The helper is a flip switch, not an
  installer. We can't ship a precompiled WinUSB INF + signed catalog for the
  Push 2 (that's exactly what Zadig/libwdi generates on the fly with its own
  signed catalog).

- **Crash safety:** if the bridge crashes while in Bridge mode, you stay on
  WinUSB and Live won't see the Push until you flip back manually. The
  Tier 2 design would have to handle that; this Tier 1 helper does not.

- **`winusb-cache/` is a Windows-driver-store snapshot.** Don't move or
  rename files inside it — `pnputil /add-driver` reads the INF and pulls
  the related `.cat`/`.sys` files from the same folder.

## Next steps (not done here)

- *Tier 2*: invoke the same switch logic from the bridge itself at start/stop,
  with a scheduled task to bypass per-launch UAC, plus a watchdog to
  guarantee the driver is restored to Live mode on crash/poweroff. Postponed
  until Tier 1 is proven reliable on real Windows machines.
