# i18n Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bilingual support (English/Chinese) to xhub Video Downloader with automatic system language detection.

**Architecture:** JSON translation files + lightweight i18n module. Language auto-detected via QLocale; English is fallback for unsupported locales.

**Tech Stack:** Python, PyQt6, JSON translations

---

## File Map

**Create:**
- `src/i18n.py` — Core i18n module with `init_i18n()`, `_()` translate function
- `src/translations/en.json` — English translations (source of truth)
- `src/translations/zh.json` — Chinese translations

**Modify:**
- `main.py` — Call `init_i18n()` before creating MainWindow
- `src/main_window.py` — Wrap all UI strings with `_()`
- `src/widgets/video_info_panel.py` — Wrap strings
- `src/widgets/download_progress.py` — Wrap strings
- `src/widgets/file_exists_dialog.py` — Wrap strings
- `src/widgets/download_history.py` — Wrap strings (Open button already added)
- `src/widgets/actor_search_tab.py` — Wrap strings

---

## Task 1: Create i18n Core Module

**Files:**
- Create: `src/i18n.py`
- Test: `tests/test_i18n.py` (new)

- [ ] **Step 1: Create translation directory**

```bash
mkdir -p src/translations
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_i18n.py
import pytest
from src.i18n import _, init_i18n, set_language

def test_translate_returns_english_by_default():
    init_i18n()
    assert _("Download") == "Download"

def test_translate_returns_chinese_when_set():
    init_i18n()
    set_language("zh")
    assert _("Download") == "下载"

def test_translate_unknown_key_returns_key():
    init_i18n()
    set_language("en")
    assert _("nonexistent_key") == "nonexistent_key"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_i18n.py -v`
Expected: FAIL — module not found

- [ ] **Step 4: Write minimal i18n implementation**

```python
# src/i18n.py
import json
import os
from PyQt6.QtCore import QLocale

_translations = {}
_current_lang = "en"

def init_i18n():
    """Initialize i18n with system language detection."""
    global _current_lang
    system_lang = QLocale.system().bcp47Name().split("-")[0]
    _current_lang = system_lang if system_lang in ["en", "zh"] else "en"
    _load_translations()

def _load_translations():
    """Load translation JSON files."""
    global _translations
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for lang in ["en", "zh"]:
        path = os.path.join(base_dir, "translations", f"{lang}.json")
        with open(path, encoding="utf-8") as f:
            _translations[lang] = json.load(f)

def _(key: str) -> str:
    """Translate a string key to the current language."""
    return _translations.get(_current_lang, {}).get(key, key)

def set_language(lang: str):
    """Manually set language (for testing)."""
    global _current_lang
    if lang in _translations:
        _current_lang = lang
```

- [ ] **Step 5: Run test to verify it fails**

Run: `pytest tests/test_i18n.py -v`
Expected: FAIL — translation files not found

- [ ] **Step 6: Create en.json**

```json
{
  "Download": "Download",
  "Downloading": "Downloading",
  "Download History": "Download History",
  "Output Directory": "Output Directory",
  "Change": "Change",
  "Enter Bilibili URL or BV号...": "Enter Bilibili URL or BV号...",
  "Parse": "Parse",
  "Open": "Open",
  "Error": "Error",
  "Finished": "Finished",
  "Failed": "Failed",
  "Select output directory": "Select output directory",
  "Parse failed": "Parse failed",
  "An error occurred during parsing": "An error occurred during parsing",
  "Confirm exit": "Confirm exit",
  "A download is in progress. Are you sure you want to exit?": "A download is in progress. Are you sure you want to exit?",
  "Cancel": "Cancel",
  "Exit": "Exit",
  "Skip": "Skip",
  "Overwrite": "Overwrite",
  "Rename": "Rename",
  "File exists": "File exists",
  "The file already exists. What would you like to do?": "The file already exists. What would you like to do?",
  "Actor Search": "Actor Search",
  "Search": "Search",
  "Select All": "Select All",
  "Download Selected": "Download Selected",
  "Extracting...": "Extracting...",
  "Downloading 1 video...": "Downloading 1 video...",
  "Downloading N videos...": "Downloading N videos...",
  "Batch download complete": "Batch download complete",
  "N videos downloaded successfully": "N videos downloaded successfully",
  "N succeeded, M failed": "N succeeded, M failed",
  "No results found": "No results found",
  "Cloudflare verification required": "Cloudflare verification required",
  "Search actor name": "Search actor name",
  "Bilibili Download": "Bilibili Download",
  "No video info": "No video info",
  "BV: ": "BV: ",
  "Duration: ": "Duration: ",
  "Filename: ": "Filename: ",
  "No thumbnail": "No thumbnail",
  "Thumbnail load failed": "Thumbnail load failed",
  "Waiting for download...": "Waiting for download...",
  "Download complete": "Download complete",
  "Download failed: ": "Download failed: ",
  "Choose operation:": "Choose operation:",
  "File already exists in target directory:": "File already exists in target directory:"
}
```

- [ ] **Step 7: Create zh.json**

```json
{
  "Download": "下载",
  "Downloading": "下载中",
  "Download History": "下载历史",
  "Output Directory": "输出目录",
  "Change": "更改",
  "Enter Bilibili URL or BV号...": "输入 Bilibili 视频链接或 BV号...",
  "Parse": "解析",
  "Open": "打开",
  "Error": "错误",
  "Finished": "已完成",
  "Failed": "失败",
  "Select output directory": "选择输出目录",
  "Parse failed": "解析失败",
  "An error occurred during parsing": "解析时发生错误",
  "Confirm exit": "确认退出",
  "A download is in progress. Are you sure you want to exit?": "有下载任务正在进行，确定要退出吗？",
  "Cancel": "取消",
  "Exit": "退出",
  "Skip": "跳过",
  "Overwrite": "覆盖",
  "Rename": "重命名",
  "File exists": "文件已存在",
  "The file already exists. What would you like to do?": "文件已存在，如何处理？",
  "Actor Search": "演员搜索",
  "Search": "搜索",
  "Select All": "全选",
  "Download Selected": "下载所选",
  "Extracting...": "正在解析...",
  "Downloading 1 video...": "正在下载 1 个视频...",
  "Downloading N videos...": "正在下载 N 个视频...",
  "Batch download complete": "批量下载完成",
  "N videos downloaded successfully": "N 个视频下载成功",
  "N succeeded, M failed": "成功 N 个，失败 M 个",
  "No results found": "未找到结果",
  "Cloudflare verification required": "需要通过 Cloudflare 验证",
  "Search actor name": "搜索演员名称",
  "Bilibili Download": "Bilibili 下载",
  "No video info": "暂无视频信息",
  "BV: ": "BV号：",
  "Duration: ": "时长：",
  "Filename: ": "文件名：",
  "No thumbnail": "无封面",
  "Thumbnail load failed": "封面加载失败",
  "Waiting for download...": "等待下载...",
  "Download complete": "下载完成",
  "Download failed: ": "下载失败：",
  "Choose operation:": "请选择操作方式：",
  "File already exists in target directory:": "即将下载的文件已存在于目标目录："
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_i18n.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/i18n.py src/translations/ tests/test_i18n.py
git commit -m "feat: add i18n core module with en/zh translations"
```

---

## Task 2: Integrate i18n into main.py

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add init_i18n import and call**

```python
# main.py
import os
import sys

from PyQt6.QtWidgets import QApplication
from src.i18n import init_i18n
from src.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Initialize i18n before creating windows
    init_i18n()

    # PyInstaller mode...
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --tb=short`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: initialize i18n before creating main window"
```

---

## Task 3: Wrap main_window.py strings

**Files:**
- Modify: `src/main_window.py`

- [ ] **Step 1: Add import**

```python
from src.i18n import _
```

- [ ] **Step 2: Wrap all Chinese strings** (strings found at lines 38, 58, 60, 64, 71, 73, 93, 94, 112, 115, 131, 134, 144, 218-222, etc.)

Key changes:
- Line 38: `self.setWindowTitle("xhub")` → `self.setWindowTitle("xhub")` (keep as-is, no translation needed)
- Line 58: `"Bilibili 下载"` → `_("Bilibili Download")`
- Line 60: `"演员搜索"` → `_("Actor Search")`
- Line 64: `"下载历史"` → `_("Download History")`
- Line 71: `f"输出目录：{self.config.output_dir}"` → `f"{_("Output Directory")}: {self.config.output_dir}"`
- Line 73: `"更改"` → `_("Change")`
- Line 93: placeholder text → `_("Enter Bilibili URL or BV号...")`
- Line 94: `"下载"` → `_("Download")`
- Line 112: `"选择输出目录"` → `_("Select output directory")`
- Line 115: update dir label with `_("Output Directory")`
- Line 131: `"解析失败"` → `_("Parse failed")`
- Line 134: `"错误"` and message → `_("Error")` and `_("An error occurred during parsing")`
- Line 144 (FileExistsDialog): title uses `_("File exists")` (already wrapped in that class)
- Line 218-222: `"确认退出"`, message, `"是"`, `"否"` → `_("Confirm exit")`, `_("A download is in progress. Are you sure you want to exit?")`, `_("Yes")`, `_("No")`

- [ ] **Step 3: Verify no hardcoded Chinese strings remain**

Search for Chinese characters in src/main_window.py after edit

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v --tb=short`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/main_window.py
git commit -m "feat: wrap main_window strings with i18n"
```

---

## Task 4: Wrap video_info_panel.py strings

**Files:**
- Modify: `src/widgets/video_info_panel.py`

- [ ] **Step 1: Add import and wrap all Chinese strings**

```python
from src.i18n import _
```

Changes:
- Line 14: `"暂无视频信息"` → `_("No video info")`
- Line 47: `"暂无视频信息"` → `_("No video info")`
- Line 50: `"无封面"` → `_("No thumbnail")`
- Line 56: `f"BV号：{info.bv_id}"` → `f"{_("BV: ")}{info.bv_id}"`
- Line 57: `f"时长：{info.formatted_duration}"` → `f"{_("Duration: ")}{info.formatted_duration}"`
- Line 58: `f"文件名：{info.output_filename}"` → `f"{_("Filename: ")}{info.output_filename}"`
- Line 63: `"无封面"` → `_("No thumbnail")`
- Line 70, 75: `"封面加载失败"` → `_("Thumbnail load failed")`

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --tb=short`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/widgets/video_info_panel.py
git commit -m "feat: wrap video_info_panel strings with i18n"
```

---

## Task 5: Wrap download_progress.py strings

**Files:**
- Modify: `src/widgets/download_progress.py`

- [ ] **Step 1: Add import and wrap strings**

```python
from src.i18n import _
```

Changes:
- Line 11: `"等待下载..."` → `_("Waiting for download...")`
- Line 33: `"等待下载..."` → `_("Waiting for download...")`
- Line 40: `"下载中..."` → `_("Downloading")`
- Line 47: `"下载完成"` → `_("Download complete")`
- Line 54: `f"下载失败：{message}"` → `f"{_("Download failed: ")}{message}"`

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --tb=short`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/widgets/download_progress.py
git commit -m "feat: wrap download_progress strings with i18n"
```

---

## Task 6: Wrap file_exists_dialog.py strings

**Files:**
- Modify: `src/widgets/file_exists_dialog.py`

- [ ] **Step 1: Add import and wrap strings**

```python
from src.i18n import _
```

Changes:
- Line 14: `"文件已存在"` → `_("File exists")`
- Line 24: `"文件已存在"` → `_("File exists")`
- Line 28: Chinese message → use `_("File already exists in target directory:")` and `_("Choose operation:")`
- Line 36: `"重命名"` → `_("Rename")`
- Line 38: `"覆盖"` → `_("Overwrite")`
- Line 42: `"跳过"` → `_("Skip")`

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --tb=short`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/widgets/file_exists_dialog.py
git commit -m "feat: wrap file_exists_dialog strings with i18n"
```

---

## Task 7: Wrap download_history.py strings

**Files:**
- Modify: `src/widgets/download_history.py`

- [ ] **Step 1: Add import and wrap strings**

```python
from src.i18n import _
```

Changes:
- Line 51 (Open button): `"Open"` is already English, no change needed

- [ ] **Step 2: Run tests**

Run: `pytest tests/ -v --tb=short`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/widgets/download_history.py
git commit -m "feat: wrap download_history strings with i18n"
```

---

## Task 8: Wrap actor_search_tab.py strings

**Files:**
- Modify: `src/widgets/actor_search_tab.py`

- [ ] **Step 1: Add import**

```python
from src.i18n import _
```

- [ ] **Step 2: Identify and wrap all Chinese strings** (search for Chinese characters in the file)

Key strings to wrap:
- Tab label: `_("Actor Search")` (line creating tab, not seen yet)
- `"演员搜索"` → `_("Actor Search")`
- `"搜索"` → `_("Search")`
- `"输入演员名称..."` placeholder → `_("Search actor name")`
- `"全选"` → `_("Select All")`
- `"下载所选"` → `_("Download Selected")`
- `"正在解析..."` → `_("Extracting...")`
- `"正在下载 X 个视频..."` → use `_("Downloading N videos...")`
- `"批量下载完成"` → `_("Batch download complete")`
- `"N 个视频下载成功"` → `_("N videos downloaded successfully")`
- `"成功 N 个，失败 M 个"` → `_("N succeeded, M failed")`
- `"未找到结果"` → `_("No results found")`
- `"需要通过 Cloudflare 验证"` → `_("Cloudflare verification required")`
- MessageBox titles and buttons

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -v --tb=short`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add src/widgets/actor_search_tab.py
git commit -m "feat: wrap actor_search_tab strings with i18n"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Search for any remaining hardcoded Chinese strings**

Run: `grep -r "[\u4e00-\u9fff]" src/` (or search for Chinese characters manually)
Expected: No results in translatable UI strings

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: PASS

- [ ] **Step 3: Verify translations completeness**

Ensure all keys in en.json have corresponding zh.json values

---

## Self-Review Checklist

1. **Spec coverage**: All features in the design spec have corresponding tasks? Yes
2. **Placeholder scan**: No TBD/TODO in plan? Verified
3. **Type consistency**: Method signatures consistent across all tasks? Yes
4. **Gap check**: Any Chinese strings in UI files that weren't wrapped? Need to verify in execution
