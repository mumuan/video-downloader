@echo off
REM xhub Windows Build Script
REM Run this script ONLY on Windows (PyInstaller + NSIS have no cross-platform build capability)
REM Prerequisites: Python 3.10+, NSIS installed and in PATH

echo [1/4] Installing Python dependencies...
pip install -r requirements.txt

echo [2/4] Installing Playwright Chromium browser...
REM PLAYWRIGHT_BROWSERS_PATH=0 forces download to a deterministic location we can bundle
set PLAYWRIGHT_BROWSERS_PATH=0
python -m playwright install chromium --with-deps

echo [3/4] Building with PyInstaller...
pyinstaller xhub.spec

echo [4/4] Building NSIS installer...
REM Note: NSIS (makensis) must be installed and in PATH
where makensis >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] NSIS not found. Please install NSIS and add it to PATH.
    echo Download: https://nsis.sourceforge.io/Download
    exit /b 1
)
makensis xhub-installer.nsi

echo.
echo === Build complete ===
echo   Executable: dist\xhub.exe
echo   Installer:   xhub-installer.exe
echo.
echo NOTE: If running for the first time, Windows SmartScreen may block the unsigned executable.
echo       Click 'More info' and then 'Run anyway' to proceed.
pause
