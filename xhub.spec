# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

block_cipher = None

# --- Hidden imports ---
hiddenimports = [
    # PyQt6 — only modules actually used by the app
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'PyQt6.sip',
    # yt-dlp — only bilibili extractor is used
    'yt_dlp',
    'yt_dlp.YoutubeDL',
    'yt_dlp.utils',
    'yt_dlp.options',
    'yt_dlp.extractor.bilibili',
    'brotli',
    'certifi',
    'mutagen',
    'websockets',
    # curl_cffi — Cloudflare bypass
    'curl_cffi',
    'curl_cffi.requests',
]

# --- Data files ---
datas = []
datas += collect_data_files('PyQt6.QtCore')
datas += collect_data_files('PyQt6.QtGui')
datas += collect_data_files('PyQt6.QtWidgets')
datas += collect_data_files('yt_dlp')
datas += collect_data_files('curl_cffi')
datas += copy_metadata('yt-dlp')
# playwright_stealth JS files (loaded dynamically at runtime when needed)
try:
    datas += collect_data_files('playwright_stealth')
except Exception:
    pass

a = Analysis(
    ['main.py'],
    hiddenimports=hiddenimports,
    datas=datas,
    binaries=[],
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
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
