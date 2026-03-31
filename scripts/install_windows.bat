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
echo [1/4] Checking Python...
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
echo [2/4] Installing Python dependencies...
pip install -r "%PROJECT_DIR%\requirements.txt"
echo   OK Dependencies installed

REM ── loopMIDI setup ──
echo [3/4] loopMIDI setup...
echo.
echo   You need loopMIDI to create virtual MIDI ports:
echo   1. Download from https://www.tobias-erichsen.de/software/loopmidi.html
echo   2. Install and run loopMIDI
echo   3. Create two ports:
echo      - Push2-To-Nuendo
echo      - Nuendo-To-Push2
echo.
pause

REM ── Install MIDI Remote script ──
echo [4/4] Installing Nuendo MIDI Remote script...

set "NUENDO_DIR=%APPDATA%\Steinberg\Nuendo 14\MIDI Remote\Driver Scripts\Local"
set "CUBASE_DIR=%APPDATA%\Steinberg\Cubase 14\MIDI Remote\Driver Scripts\Local"

if exist "%APPDATA%\Steinberg\Nuendo 14" (
    if not exist "%NUENDO_DIR%" mkdir "%NUENDO_DIR%"
    copy "%PROJECT_DIR%\Ableton_Push2.js" "%NUENDO_DIR%\" >nul
    echo   OK Script installed to Nuendo 14
)

if exist "%APPDATA%\Steinberg\Cubase 14" (
    if not exist "%CUBASE_DIR%" mkdir "%CUBASE_DIR%"
    copy "%PROJECT_DIR%\Ableton_Push2.js" "%CUBASE_DIR%\" >nul
    echo   OK Script installed to Cubase 14
)

if not exist "%APPDATA%\Steinberg\Nuendo 14" if not exist "%APPDATA%\Steinberg\Cubase 14" (
    echo   WARNING: Nuendo/Cubase 14 folder not found
    echo   Copy Ableton_Push2.js manually to:
    echo   %%APPDATA%%\Steinberg\^<DAW^>\MIDI Remote\Driver Scripts\Local\
)

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
echo     Input: Push2-To-Nuendo
echo     Output: Nuendo-To-Push2
echo ═══════════════════════════════════════════════
echo.
pause
