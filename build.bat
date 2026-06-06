@echo off
setlocal

echo [1/5] Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo [2/5] Preparing Playwright browser bundle...
set "PLAYWRIGHT_BROWSERS_PATH=%CD%\.playwright-browsers"
if not exist "%PLAYWRIGHT_BROWSERS_PATH%" mkdir "%PLAYWRIGHT_BROWSERS_PATH%"
python scripts\install_playwright_chromium.py
if errorlevel 1 exit /b 1

echo [3/5] Cleaning previous build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/5] Building with PyInstaller...
pyinstaller --clean xhub.spec
if errorlevel 1 exit /b 1

echo [5/5] Building NSIS installer...
set "MAKENSIS=makensis"
where makensis >nul 2>&1
if errorlevel 1 (
    if exist "%ProgramFiles(x86)%\NSIS\makensis.exe" (
        set "MAKENSIS=%ProgramFiles(x86)%\NSIS\makensis.exe"
    ) else if exist "%ProgramFiles%\NSIS\makensis.exe" (
        set "MAKENSIS=%ProgramFiles%\NSIS\makensis.exe"
    ) else (
        echo [ERROR] NSIS not found. Install NSIS and add it to PATH.
        exit /b 1
    )
)
"%MAKENSIS%" xhub-installer.nsi
if errorlevel 1 exit /b 1

echo.
echo Build complete
echo   Executable: dist\xhub.exe
echo   Installer: xhub-installer.exe
endlocal
