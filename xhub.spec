# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

block_cipher = None

# --- Hidden imports ---
hiddenimports = [
    # PyQt6
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
]
hiddenimports += collect_submodules('PyQt6')

# yt-dlp and its implicit dependencies
hiddenimports += [
    'yt_dlp',
    'yt_dlp.utils',
    'yt_dlp.extractor',
    'yt_dlp.options',
    'brotli',
    'certifi',
    'mutagen',
    'websockets',
]
hiddenimports += collect_submodules('yt_dlp')

# playwright
hiddenimports += [
    'playwright',
    'playwright.sync_api',
    'playwright_stealth',
    'playwright_stealth.stealth',
    'playwright_stealth.stealth_ess',
]
hiddenimports += collect_submodules('playwright')

# --- Data files ---
datas = []
datas += collect_data_files('PyQt6')
datas += collect_data_files('yt_dlp')
datas += collect_data_files('yt_dlp')
datas += copy_metadata('playwright')
datas += copy_metadata('yt-dlp')

# --- Playwright browser binaries ---
# When PLAYWRIGHT_BROWSERS_PATH=0 is set before `playwright install`,
# browsers are downloaded to %USERPROFILE%\AppData\Local\ms-playwright
playwright_browsers_path = os.path.join(
    os.path.expanduser('~'), 'AppData', 'Local', 'ms-playwright'
)

a = Analysis(
    ['main.py'],
    hiddenimports=hiddenimports,
    datas=datas,
    binaries=[
        # Bundle Playwright chromium browser
        (playwright_browsers_path, 'ms-playwright'),
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='xhub',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # R3: no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',  # R4: application icon
)
