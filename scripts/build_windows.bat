@echo off
setlocal EnableDelayedExpansion
REM ─────────────────────────────────────────────────
REM  Push 2 / Nuendo Bridge — Build standalone .exe
REM  Output: dist\Push2 Nuendo Bridge_v<ver>.exe  (onefile, console)
REM
REM  Run this ON WINDOWS (PyInstaller cannot cross-compile).
REM  Requires Python 3.9 - 3.11.9.
REM ─────────────────────────────────────────────────

echo.
echo ===================================================
echo   Push 2 / Nuendo Bridge - Windows build
echo ===================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "SRC_DIR=%PROJECT_DIR%\src"

REM ── Check Python ──
python --version >nul 2>&1
if errorlevel 1 (
    echo   X Python not found. Install Python 3.9-3.11 from https://python.org
    pause
    exit /b 1
)

REM ── Extract version from state.py ──
for /f "tokens=*" %%v in ('python -c "import sys; sys.path.insert(0, r'%SRC_DIR%'); from state import BRIDGE_VERSION; print(BRIDGE_VERSION)"') do set "VERSION=%%v"
if "%VERSION%"=="" set "VERSION=dev"
set "APP_NAME=Push2 Nuendo Bridge_v%VERSION%"
echo   Building %APP_NAME% ...
echo.

REM ── Install build + runtime dependencies ──
echo [1/4] Installing dependencies...
python -m pip install --upgrade pip >nul
python -m pip install pyinstaller >nul
REM libusb-package ships libusb-1.0.dll so the Push 2 USB link works
REM without a separate manual DLL copy.
python -m pip install libusb-package >nul
REM Plugin Mapper deps must be in the build env so PyInstaller bundles them
REM (a frozen .exe cannot pip-install them at runtime).
python -m pip install fastapi uvicorn pedalboard >nul
REM pystray powers the system tray icon (windowed mode).
python -m pip install pystray >nul
python -m pip install -r "%PROJECT_DIR%\requirements.txt"
if errorlevel 1 (
    echo   X Dependency install failed.
    pause
    exit /b 1
)
echo   OK dependencies installed
echo.

REM ── Locate the bundled libusb-1.0.dll ──
echo [2/4] Locating libusb-1.0.dll...
set "LIBUSB_DLL="
for /f "tokens=*" %%d in ('python -c "import libusb_package, os; p=os.path.join(os.path.dirname(libusb_package.__file__),'platform','windows','x64','libusb-1.0.dll'); print(p if os.path.isfile(p) else '')" 2^>nul') do set "LIBUSB_DLL=%%d"
if not defined LIBUSB_DLL (
    for /f "tokens=*" %%d in ('python -c "import glob,os,libusb_package; m=glob.glob(os.path.join(os.path.dirname(libusb_package.__file__),'**','libusb-1.0.dll'),recursive=True); print(m[0] if m else '')" 2^>nul') do set "LIBUSB_DLL=%%d"
)
if defined LIBUSB_DLL (
    echo   OK libusb-1.0.dll: !LIBUSB_DLL!
    set "ADD_LIBUSB=--add-binary "!LIBUSB_DLL!;.""
) else (
    echo   WARNING: libusb-1.0.dll not found. The Push 2 USB connection
    echo   may fail. Install the WinUSB driver via Zadig and/or place
    echo   libusb-1.0.dll next to the .exe.
    set "ADD_LIBUSB="
)
echo.

REM ── Clean previous build ──
if exist "%PROJECT_DIR%\dist"  rmdir /s /q "%PROJECT_DIR%\dist"
if exist "%PROJECT_DIR%\build" rmdir /s /q "%PROJECT_DIR%\build"

cd /d "%SRC_DIR%"

REM ── Build the onefile console .exe ──
echo [3/4] Running PyInstaller (onefile, windowed/tray)...
pyinstaller ^
    --name "%APP_NAME%" ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --paths . ^
    --add-data "assets;assets" ^
    --add-data "mapper;mapper" ^
    --add-data "state.py;." ^
    --add-data "nuendo_link.py;." ^
    --add-data "push2_controller.py;." ^
    --add-data "renderer.py;." ^
    --add-data "pad_grid.py;." ^
    --add-data "control_room.py;." ^
    --add-data "repeat.py;." ^
    --add-data "overview.py;." ^
    --add-data "main_windows.py;." ^
    --collect-all pystray ^
    --hidden-import main_windows ^
    --hidden-import state ^
    --hidden-import nuendo_link ^
    --hidden-import push2_controller ^
    --hidden-import renderer ^
    --hidden-import pad_grid ^
    --hidden-import control_room ^
    --hidden-import repeat ^
    --hidden-import overview ^
    !ADD_LIBUSB! ^
    --hidden-import push2_python ^
    --hidden-import push2_python.constants ^
    --hidden-import push2_python.simulator ^
    --hidden-import push2_python.simulator.simulator ^
    --hidden-import rtmidi ^
    --hidden-import mido ^
    --hidden-import mido.backends ^
    --hidden-import mido.backends.rtmidi ^
    --hidden-import numpy ^
    --hidden-import usb ^
    --hidden-import usb.core ^
    --hidden-import usb.backend ^
    --hidden-import usb.backend.libusb1 ^
    --hidden-import engineio ^
    --hidden-import engineio.async_drivers ^
    --hidden-import engineio.async_drivers.threading ^
    --hidden-import socketio ^
    --hidden-import flask ^
    --hidden-import flask_socketio ^
    --collect-submodules PIL ^
    --collect-submodules push2_python ^
    --collect-submodules engineio ^
    --collect-submodules socketio ^
    --collect-all uvicorn ^
    --collect-all fastapi ^
    --collect-all starlette ^
    --collect-all pydantic ^
    --collect-all pydantic_core ^
    --collect-all anyio ^
    --collect-all pedalboard ^
    --hidden-import mapper ^
    --hidden-import mapper.server ^
    --hidden-import mapper.scanner ^
    main.py
if errorlevel 1 (
    echo   X PyInstaller build failed.
    pause
    exit /b 1
)

REM ── Move output to project root ──
if not exist "%PROJECT_DIR%\dist" mkdir "%PROJECT_DIR%\dist"
move /y "%SRC_DIR%\dist\%APP_NAME%.exe" "%PROJECT_DIR%\dist\" >nul
rmdir /s /q "%SRC_DIR%\build"  2>nul
rmdir /s /q "%SRC_DIR%\dist"   2>nul
del /q "%SRC_DIR%\%APP_NAME%.spec" 2>nul

REM ── Bundle the JS script + docs next to the .exe ──
copy "%PROJECT_DIR%\Ableton_Push2.js" "%PROJECT_DIR%\dist\" >nul
for %%P in ("%PROJECT_DIR%\docs\*.pdf") do copy "%%P" "%PROJECT_DIR%\dist\" >nul 2>&1

REM ── Zip for release ──
echo [4/4] Creating release zip...
set "ZIP_NAME=Push2NuendoBridge-v%VERSION%-Windows.zip"
powershell -NoProfile -Command "Compress-Archive -Force -Path '%PROJECT_DIR%\dist\*' -DestinationPath '%PROJECT_DIR%\dist\%ZIP_NAME%'" 2>nul

echo.
echo ===================================================
echo   Build complete!  (v%VERSION%)
echo.
echo   Exe:    dist\%APP_NAME%.exe
echo   Script: dist\Ableton_Push2.js
echo   Zip:    dist\%ZIP_NAME%
echo.
echo   Run it by double-clicking the .exe.
echo ===================================================
echo.
pause
