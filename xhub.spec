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
    # VLC — video playback
    'vlc',
]

# --- Data files ---
datas = []
datas += collect_data_files('PyQt6.QtCore')
datas += collect_data_files('PyQt6.QtGui')
datas += collect_data_files('PyQt6.QtWidgets')
datas += collect_data_files('yt_dlp')
datas += collect_data_files('curl_cffi')
datas += copy_metadata('yt-dlp')
# i18n translations
import os
spec_dir = os.path.dirname(os.path.abspath(SPEC))
src_dir = os.path.join(spec_dir, 'src')
trans_src = os.path.join(src_dir, 'translations')
datas.append((os.path.join(trans_src, 'en.json'), 'translations'))
datas.append((os.path.join(trans_src, 'zh.json'), 'translations'))
datas.append((os.path.join(src_dir, 'styles.qss'), '.'))
# playwright_stealth JS files (loaded dynamically at runtime when needed)
try:
    datas += collect_data_files('playwright_stealth')
except Exception:
    pass

# --- VLC bundling ---
vlc_dir = r"C:\Program Files\VideoLAN\VLC"
if not os.path.isdir(vlc_dir):
    vlc_dir = os.path.expanduser(r"~\AppData\Local\Programs\VideoLAN\VLC")

vlc_binaries = []
vlc_datafiles = []
if os.path.isdir(vlc_dir):
    # Collect all DLLs from VLC directory
    import glob
    for dll in glob.glob(os.path.join(vlc_dir, "*.dll")):
        vlc_binaries.append((dll, vlc_dir))
    # Include plugins folder
    plugins_dir = os.path.join(vlc_dir, "plugins")
    if os.path.isdir(plugins_dir):
        vlc_datafiles.append((plugins_dir, "plugins"))
    # Include lua playlist folder if exists
    lua_dir = os.path.join(vlc_dir, "lua")
    if os.path.isdir(lua_dir):
        vlc_datafiles.append((lua_dir, "lua"))

a = Analysis(
    ['main.py'],
    hiddenimports=hiddenimports,
    datas=datas + vlc_datafiles,
    binaries=vlc_binaries,
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
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
