# Push 2 / Nuendo Bridge -- Driver Switcher (Tier 1 manual helper)
#
# Flips the Push 2's Windows driver between WinUSB (bridge) and Ableton's
# default driver (Live). See README.md for the full design.
#
# IMPORTANT: this version is pure ASCII (PowerShell 5.1 reads .ps1 as
# Windows-1252 by default, so non-ASCII chars in strings/comments break
# the parser). It also writes a transcript log alongside the script
# (Push2-Driver-Switch.log) and keeps the elevated window open on error,
# so silent failures can be diagnosed.

param(
    [ValidateSet('Bridge','Live','Status','Menu')]
    [string]$To = 'Menu'
)

# == Diagnostic logging -- always on =========================================
# Resolve script directory robustly (PSScriptRoot is empty for some launchers).
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$LogFile   = Join-Path $ScriptDir 'Push2-Driver-Switch.log'
try {
    Start-Transcript -Path $LogFile -Append -Force | Out-Null
} catch {
    Write-Host "WARNING: could not start transcript ($LogFile): $($_.Exception.Message)" -ForegroundColor Yellow
}
Write-Host "==== Push2-Driver-Switch ====" -ForegroundColor Cyan
Write-Host ("Started at  : " + (Get-Date -Format 's'))
Write-Host ("Script dir  : " + $ScriptDir)
Write-Host ("PS version  : " + $PSVersionTable.PSVersion)
Write-Host ("OS          : " + (Get-CimInstance Win32_OperatingSystem -EA SilentlyContinue).Caption)
Write-Host ("Arch        : " + $env:PROCESSOR_ARCHITECTURE)
Write-Host ("Invoked -To : " + $To)
Write-Host ""

# == Push 2 hardware identifiers =============================================
$PUSH2_VID_HEX = '2982'
$PUSH2_PID_HEX = '1967'
$HWID_GLOB     = "USB\VID_${PUSH2_VID_HEX}&PID_${PUSH2_PID_HEX}*"
$CACHE_DIR     = Join-Path $ScriptDir 'winusb-cache'

# == Self-elevate (driver ops require admin) =================================
$current = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
$isAdmin = $current.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host ("Elevated    : " + $isAdmin)

if (-not $isAdmin) {
    Write-Host "Re-launching with elevation (UAC)..." -ForegroundColor Cyan
    # Single-string argument list -- most reliable quoting for paths with spaces.
    $argLine = "-NoProfile -NoExit -ExecutionPolicy Bypass -File `"$($MyInvocation.MyCommand.Path)`" -To $To"
    try {
        Start-Process -FilePath 'PowerShell.exe' -Verb RunAs -ArgumentList $argLine -ErrorAction Stop
    } catch {
        Write-Host "ERROR: failed to elevate: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Try right-clicking Push2-Driver-Switch.bat -> Run as administrator." -ForegroundColor Yellow
        Read-Host "Press Enter to close this window" | Out-Null
    }
    try { Stop-Transcript | Out-Null } catch {}
    exit
}

# == Helpers =================================================================

function Get-Push2Devices {
    Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like $HWID_GLOB }
}

function Get-WinUsbInfFromDevice {
    $dev = Get-Push2Devices | Where-Object { $_.Service -eq 'WinUSB' } | Select-Object -First 1
    if (-not $dev) { return $null }
    try {
        $p = Get-PnpDeviceProperty -InstanceId $dev.InstanceId `
             -KeyName 'DEVPKEY_Device_DriverInfPath' -ErrorAction Stop
        return $p.Data
    } catch {
        return $null
    }
}

function Get-CachedInfPath {
    if (-not (Test-Path $CACHE_DIR)) { return $null }
    $inf = Get-ChildItem $CACHE_DIR -Filter *.inf -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($inf) { return $inf.FullName }
    return $null
}

function Save-CurrentWinUsbDriver {
    $publishedInf = Get-WinUsbInfFromDevice
    if (-not $publishedInf) { return $false }
    if (Test-Path $CACHE_DIR) { Remove-Item $CACHE_DIR -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force -Path $CACHE_DIR | Out-Null
    Write-Host "Exporting WinUSB driver package ($publishedInf) to cache..." -ForegroundColor Gray
    & pnputil /export-driver $publishedInf $CACHE_DIR 2>&1 | Write-Host
    return ($LASTEXITCODE -eq 0 -and (Get-CachedInfPath))
}

# == Status ==================================================================

function Show-Status {
    Write-Host ""
    Write-Host "Push 2 devices currently visible to Windows:" -ForegroundColor Cyan
    $devs = Get-Push2Devices
    if (-not $devs) {
        Write-Host "  (none -- is the Push 2 connected over USB?)" -ForegroundColor Yellow
    } else {
        $devs | Select-Object FriendlyName, InstanceId, Status, Class, Service |
            Format-Table -AutoSize | Out-String | Write-Host
        Write-Host "Service column tells you which driver is bound:" -ForegroundColor Gray
        Write-Host "  WinUSB    -> bridge mode (Ableton Live cannot see the Push)" -ForegroundColor Gray
        Write-Host "  usbaudio  -> standard MIDI interface (always there, shared)" -ForegroundColor Gray
        Write-Host "  (other)   -> likely Ableton's driver = Live mode" -ForegroundColor Gray
    }
    Write-Host ""
    if (Get-CachedInfPath) {
        Write-Host "WinUSB driver cache: PRESENT ($CACHE_DIR)" -ForegroundColor Green
    } else {
        Write-Host "WinUSB driver cache: empty" -ForegroundColor Yellow
        Write-Host "  -> the cache fills automatically the first time you switch to Live" -ForegroundColor Gray
        Write-Host "     while a WinUSB-bound Push 2 is connected." -ForegroundColor Gray
    }
    Write-Host ""
}

# == Switch operations =======================================================

function Switch-ToBridge {
    if (Get-WinUsbInfFromDevice) {
        Write-Host "Already in Bridge mode (WinUSB driver is bound). Nothing to do." -ForegroundColor Green
        return $true
    }
    $cached = Get-CachedInfPath
    if (-not $cached) {
        Write-Host ""
        Write-Host "ERROR: no cached WinUSB driver to install." -ForegroundColor Red
        Write-Host ""
        Write-Host "One-time setup (only needed once per Windows install):" -ForegroundColor Yellow
        Write-Host "  1. Run Zadig and install WinUSB on the Push 2 display/bulk" -ForegroundColor Yellow
        Write-Host "     interface (USB ID 2982:1967). See the Windows Installation Guide." -ForegroundColor Yellow
        Write-Host "  2. Re-launch this helper. The next time you switch to Live mode," -ForegroundColor Yellow
        Write-Host "     the WinUSB driver is automatically cached." -ForegroundColor Yellow
        return $false
    }
    Write-Host "Installing WinUSB driver from cache..." -ForegroundColor Cyan
    Write-Host "  source: $cached" -ForegroundColor Gray
    & pnputil /add-driver $cached /install 2>&1 | Write-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "pnputil /add-driver returned exit code $LASTEXITCODE." -ForegroundColor Red
        Write-Host "Fallback: run Zadig manually." -ForegroundColor Yellow
        return $false
    }
    Start-Sleep -Seconds 1
    Write-Host ""
    Write-Host "OK -- WinUSB is back. Launch the bridge .exe." -ForegroundColor Green
    Write-Host "Ableton Live cannot see the Push until you switch back to Live mode." -ForegroundColor Yellow
    return $true
}

function Switch-ToLive {
    $devs = Get-Push2Devices | Where-Object { $_.Service -eq 'WinUSB' }
    if (-not $devs) {
        Write-Host "No WinUSB-bound Push 2 found -- already on Ableton's driver?" -ForegroundColor Yellow
        Show-Status
        return $true
    }

    if (-not (Get-CachedInfPath)) {
        Write-Host "Caching current WinUSB driver for future Bridge switches..." -ForegroundColor Cyan
        if (Save-CurrentWinUsbDriver) {
            Write-Host "  cached in $CACHE_DIR" -ForegroundColor Green
        } else {
            Write-Host ""
            Write-Host "WARNING: could not export the WinUSB driver." -ForegroundColor Yellow
            Write-Host "Switching to Live now will work, but switching back to Bridge" -ForegroundColor Yellow
            Write-Host "later will need Zadig manually again." -ForegroundColor Yellow
            $continue = Read-Host "Continue anyway? [y/N]"
            if ($continue -notmatch '^[Yy]') { return $false }
        }
    }

    $infsToDelete = @()
    foreach ($d in $devs) {
        try {
            $p = Get-PnpDeviceProperty -InstanceId $d.InstanceId `
                 -KeyName 'DEVPKEY_Device_DriverInfPath' -ErrorAction Stop
            if ($p.Data) { $infsToDelete += $p.Data }
        } catch {
            Write-Host "  (could not read DriverInfPath for $($d.InstanceId): $($_.Exception.Message))" -ForegroundColor Gray
        }
    }
    $infsToDelete = $infsToDelete | Sort-Object -Unique

    foreach ($d in $devs) {
        Write-Host "Removing device $($d.InstanceId)..." -ForegroundColor Gray
        & pnputil /remove-device "$($d.InstanceId)" /force 2>&1 | Write-Host
    }
    foreach ($inf in $infsToDelete) {
        Write-Host "Deleting driver package $inf..." -ForegroundColor Gray
        & pnputil /delete-driver $inf /uninstall /force 2>&1 | Write-Host
    }

    Start-Sleep -Milliseconds 500
    Write-Host "Re-scanning hardware..." -ForegroundColor Cyan
    & pnputil /scan-devices 2>&1 | Write-Host
    Start-Sleep -Seconds 2

    Write-Host ""
    Write-Host "OK -- launch Ableton Live; it should detect the Push 2." -ForegroundColor Green
    Write-Host "If Live still cannot see it, unplug/replug the USB cable once." -ForegroundColor Yellow
    return $true
}

# == Menu ====================================================================

function Show-Menu {
    while ($true) {
        Show-Status
        Write-Host "What would you like to do?" -ForegroundColor Cyan
        Write-Host "  [1] Switch to Bridge mode (install WinUSB driver)"
        Write-Host "  [2] Switch to Live mode   (restore Ableton driver)"
        Write-Host "  [3] Refresh status"
        Write-Host "  [Q] Quit"
        $c = Read-Host "Choice"
        switch ($c.ToUpper()) {
            '1' { Switch-ToBridge | Out-Null; Read-Host "Press Enter to continue" | Out-Null }
            '2' { Switch-ToLive   | Out-Null; Read-Host "Press Enter to continue" | Out-Null }
            '3' { }
            'Q' { return }
            default { Write-Host "Unknown choice." -ForegroundColor Yellow }
        }
    }
}

# == Dispatch with top-level crash guard =====================================
try {
    switch ($To) {
        'Bridge' { Switch-ToBridge | Out-Null }
        'Live'   { Switch-ToLive   | Out-Null }
        'Status' { Show-Status }
        'Menu'   { Show-Menu }
    }
} catch {
    Write-Host ""
    Write-Host "==== UNHANDLED ERROR ====" -ForegroundColor Red
    Write-Host $_.Exception.GetType().FullName -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Stack trace:" -ForegroundColor Yellow
    Write-Host $_.ScriptStackTrace
    Write-Host ""
    Write-Host "Full transcript saved to: $LogFile" -ForegroundColor Yellow
}

# Always pause and stop transcript at the very end so the window does not
# vanish silently and the log is closed cleanly.
Write-Host ""
Read-Host "Press Enter to close this window" | Out-Null
try { Stop-Transcript | Out-Null } catch {}
