# -*- mode: python ; coding: utf-8 -*-
import glob
import os

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

block_cipher = None


def collect_directory(source_dir, dest_root):
    entries = []
    if not os.path.isdir(source_dir):
        return entries
    for root, _, files in os.walk(source_dir):
        rel_root = os.path.relpath(root, source_dir)
        dest_dir = dest_root if rel_root == "." else os.path.join(dest_root, rel_root)
        for name in files:
            entries.append((os.path.join(root, name), dest_dir))
    return entries


hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.sip",
    "yt_dlp",
    "yt_dlp.YoutubeDL",
    "yt_dlp.utils",
    "yt_dlp.options",
    "yt_dlp.extractor.generic",
    "yt_dlp.extractor.bilibili",
    "yt_dlp.extractor.youtube",
    "curl_cffi",
    "curl_cffi.requests",
    "vlc",
    "playwright",
    "playwright.sync_api",
    "playwright_stealth",
]

datas = []
datas += collect_data_files("yt_dlp")
datas += collect_data_files("curl_cffi")
datas += collect_data_files("playwright")
datas += collect_data_files("playwright_stealth")
datas += copy_metadata("yt-dlp")
datas += copy_metadata("curl_cffi")
datas += copy_metadata("playwright")

spec_dir = os.path.dirname(os.path.abspath(SPEC))
src_dir = os.path.join(spec_dir, "src")
datas.append((os.path.join(src_dir, "translations", "en.json"), "translations"))
datas.append((os.path.join(src_dir, "translations", "zh.json"), "translations"))
datas.append((os.path.join(src_dir, "styles.qss"), "."))

playwright_browsers_dir = os.path.join(spec_dir, ".playwright-browsers")
datas += collect_directory(playwright_browsers_dir, "ms-playwright")

vlc_dir = r"C:\Program Files\VideoLAN\VLC"
if not os.path.isdir(vlc_dir):
    vlc_dir = os.path.expanduser(r"~\AppData\Local\Programs\VideoLAN\VLC")

vlc_binaries = []
vlc_datas = []
if os.path.isdir(vlc_dir):
    for dll in glob.glob(os.path.join(vlc_dir, "*.dll")):
        vlc_binaries.append((dll, "."))
    vlc_datas += collect_directory(os.path.join(vlc_dir, "plugins"), "plugins")
    vlc_datas += collect_directory(os.path.join(vlc_dir, "lua"), "lua")

a = Analysis(
    ["main.py"],
    hiddenimports=hiddenimports,
    datas=datas + vlc_datas,
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
    name="xhub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)
