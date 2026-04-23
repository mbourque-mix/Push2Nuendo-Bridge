@echo off
REM ─────────────────────────────────────────────────
REM Push 2 / Nuendo Bridge — Windows Installer
REM ─────────────────────────────────────────────────

echo.
echo ╔═══════════════════════════════════════════════╗
echo ║  Push 2 / Nuendo Bridge — Windows Installer   ║
echo ╚═══════════════════════════════════════════════╝
echo.

set "PROJECT_DIR=%~dp0.."

REM ── Check Python ──
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo   X Python not found. Install it from https://python.org
    echo   Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
for /f "tokens=*" %%a in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PY_VERSION=%%a
echo   OK Python %PY_VERSION% found

REM ── Install Python dependencies ──
echo [2/5] Installing Python dependencies...
pip install -r "%PROJECT_DIR%\requirements.txt"
echo   OK Dependencies installed

REM ── loopMIDI setup ──
echo [3/5] loopMIDI setup...
echo.
echo   On Windows, you need loopMIDI to create virtual MIDI ports.
echo   Download from https://www.tobias-erichsen.de/software/loopmidi.html
echo.
echo   Create four ports with these EXACT names:
echo      - NuendoBridge In
echo      - NuendoBridge Out
echo      - BridgeNotes
echo      - BridgeNotes In
echo.
echo   Set loopMIDI to start with Windows (right-click tray icon).
echo.
pause

REM ── Install MIDI Remote script ──
echo [4/5] Installing Nuendo MIDI Remote script...

set INSTALLED=0

for %%D in ("Nuendo 15" "Nuendo 14" "Cubase 15" "Cubase 14") do (
    if exist "%APPDATA%\Steinberg\%%~D" (
        set "SCRIPT_DIR=%APPDATA%\Steinberg\%%~D\MIDI Remote\Driver Scripts\Local"
        if not exist "!SCRIPT_DIR!" mkdir "!SCRIPT_DIR!"
        copy "%PROJECT_DIR%\Ableton_Push2.js" "!SCRIPT_DIR!\" >nul
        echo   OK Script installed to %%~D
        set INSTALLED=1
    )
)

if %INSTALLED%==0 (
    echo   WARNING: Nuendo/Cubase folder not found
    echo   Copy Ableton_Push2.js manually to:
    echo   %%APPDATA%%\Steinberg\^<DAW^>\MIDI Remote\Driver Scripts\Local\
)

REM ── Plugin Mapper (optional) ──
echo [5/5] Plugin Mapper (optional)...
echo.
echo   To enable the Plugin Mapper, run:
echo     pip install fastapi uvicorn pedalboard
echo.

echo.
echo ═══════════════════════════════════════════════
echo   Installation complete!
echo.
echo   To run the bridge:
echo     cd %PROJECT_DIR%\src
echo     python main.py
echo.
echo   To configure Nuendo:
echo     Studio - Studio Setup - MIDI Remote
echo     Input:  NuendoBridge Out
echo     Output: NuendoBridge In
echo ═══════════════════════════════════════════════
echo.
pause
