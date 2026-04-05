# Bilibili 视频下载工具 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A PyQt6 GUI application that downloads Bilibili videos using yt-dlp, with video preview, real-time progress, and download history.

**Architecture:** Single-window PyQt6 app. yt-dlp runs in a background QThread. All GUI updates via Qt signals from the worker thread. Settings persisted to JSON in app data folder.

**Tech Stack:** Python 3.10+, PyQt6, yt-dlp

---

## File Structure

```
C:\Users\成一一\Desktop\X\videodownload\
├── main.py                           # Entry point
├── requirements.txt                   # Dependencies
└── src\
    ├── __init__.py
    ├── video_info.py                 # VideoInfo dataclass (R6)
    ├── config.py                      # Output dir persistence (R7)
    ├── video_parser.py                # yt-dlp extract_info (R1, R6)
    ├── downloader.py                  # yt-dlp download with progress (R2, R5)
    ├── main_window.py                 # Main window (R4)
    └── widgets\
        ├── __init__.py
        ├── video_info_panel.py        # Video info preview (R6)
        ├── download_progress.py        # Progress bar + speed (R5)
        └── download_history.py        # History list (R5)
```

---

## Task 1: Project Setup

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/widgets/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```txt
PyQt6>=6.6.0
yt-dlp>=2024.0.0
```

- [ ] **Step 2: Create src/__init__.py**

```python
```

- [ ] **Step 3: Create src/widgets/__init__.py**

```python
```

- [ ] **Step 4: Commit**

```bash
git add requirements.txt src/__init__.py src/widgets/__init__.py
git commit -m "chore: project skeleton"
```

---

## Task 2: VideoInfo Data Class

**Files:**
- Create: `src/video_info.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video_info.py
import pytest
from src.video_info import VideoInfo

def test_video_info_creation():
    info = VideoInfo(
        bv_id="BV1xx411xxx",
        title="测试视频标题",
        duration=754,  # seconds
        thumbnail="https://example.com/thumb.jpg",
        output_filename="测试视频标题_bilibili_BV1xx411xxx.mp4"
    )
    assert info.bv_id == "BV1xx411xxx"
    assert info.title == "测试视频标题"
    assert info.duration == 754
    assert info.formatted_duration == "12:34"
    assert info.output_filename == "测试视频标题_bilibili_BV1xx411xxx.mp4"

def test_formatted_duration_short():
    info = VideoInfo(bv_id="BV1", title="t", duration=65, thumbnail="", output_filename="t.mp4")
    assert info.formatted_duration == "1:05"

def test_formatted_duration_zero():
    info = VideoInfo(bv_id="BV1", title="t", duration=0, thumbnail="", output_filename="t.mp4")
    assert info.formatted_duration == "0:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video_info.py -v`
Expected: FAIL — `VideoInfo` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# src/video_info.py
from dataclasses import dataclass

@dataclass
class VideoInfo:
    bv_id: str
    title: str
    duration: int  # seconds
    thumbnail: str
    output_filename: str

    @property
    def formatted_duration(self) -> str:
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_video_info.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/video_info.py tests/test_video_info.py
git commit -m "feat: add VideoInfo dataclass"
```

---

## Task 3: Video Parser (URL/BV → VideoInfo)

**Files:**
- Create: `src/video_parser.py`
- Create: `tests/test_video_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video_parser.py
import pytest
from src.video_parser import VideoParser, InvalidVideoURLError

def test_normalize_bv_id():
    p = VideoParser()
    assert p._normalize_bv_id("BV1xxxx") == "BV1xxxx"
    assert p._normalize_bv_id("https://www.bilibili.com/video/BV1xxxx") == "BV1xxxx"
    assert p._normalize_bv_id("https://bilibili.com/video/BV1xxxx") == "BV1xxxx"

def test_normalize_bv_id_invalid():
    p = VideoParser()
    with pytest.raises(InvalidVideoURLError):
        p._normalize_bv_id("https://youtube.com/watch?v=xxx")

def test_normalize_bv_id_empty():
    p = VideoParser()
    with pytest.raises(InvalidVideoURLError):
        p._normalize_bv_id("")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video_parser.py -v`
Expected: FAIL — `VideoParser` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# src/video_parser.py
import yt_dlp
from src.video_info import VideoInfo

class InvalidVideoURLError(Exception):
    pass

class VideoParser:
    def _normalize_bv_id(self, raw: str) -> str:
        raw = raw.strip()
        if not raw:
            raise InvalidVideoURLError("输入为空")
        if raw.startswith("https://") or raw.startswith("http://"):
            if "bilibili.com" not in raw:
                raise InvalidVideoURLError("不支持的网站，仅支持 Bilibili")
            # Extract BV号 from URL
            import re
            match = re.search(r'BV[\w]+', raw)
            if not match:
                raise InvalidVideoURLError("无法从URL中提取BV号")
            return match.group(0)
        if raw.startswith("BV"):
            return raw
        raise InvalidVideoURLError("请输入有效的 BV号 或 Bilibili 视频链接")

    def parse(self, raw_input: str) -> VideoInfo:
        bv_id = self._normalize_bv_id(raw_input)
        url = f"https://www.bilibili.com/video/{bv_id}"

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise InvalidVideoURLError("无法获取视频信息，请检查链接是否有效")

        title = info.get('title', '未知标题')
        duration = info.get('duration', 0)
        thumbnail = info.get('thumbnail', '')
        # Sanitize filename characters
        safe_title = "".join(c for c in title if c not in '<>:"/\\|?*')
        output_filename = f"{safe_title}_bilibili_{bv_id}.mp4"

        return VideoInfo(
            bv_id=bv_id,
            title=title,
            duration=duration,
            thumbnail=thumbnail,
            output_filename=output_filename,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_video_parser.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/video_parser.py tests/test_video_parser.py
git commit -m "feat: add VideoParser for URL/BV号 extraction"
```

---

## Task 4: Downloader with Progress

**Files:**
- Create: `src/downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_downloader.py
import pytest
from unittest.mock import MagicMock
from src.downloader import Downloader, DownloadState

def test_download_state_enum():
    assert DownloadState.IDLE.name == "IDLE"
    assert DownloadState.DOWNLOADING.name == "DOWNLOADING"
    assert DownloadState.FINISHED.name == "FINISHED"
    assert DownloadState.ERROR.name == "ERROR"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloader.py -v`
Expected: FAIL — `Downloader` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# src/downloader.py
import enum
import yt_dlp
from PyQt6.QtCore import QObject, pyqtSignal

class DownloadState(enum.Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    FINISHED = "finished"
    ERROR = "error"

class Downloader(QObject):
    progress_changed = pyqtSignal(float, str, str)  # percent, speed, size
    state_changed = pyqtSignal(str)  # state name
    finished = pyqtSignal(str)  # output path
    error = pyqtSignal(str)  # error message

    def __init__(self, output_dir: str):
        super().__init__()
        self.output_dir = output_dir
        self._state = DownloadState.IDLE

    @property
    def state(self) -> DownloadState:
        return self._state

    def _set_state(self, state: DownloadState):
        self._state = state
        self.state_changed.emit(state.value)

    def download(self, url: str, output_filename: str):
        self._set_state(DownloadState.DOWNLOADING)

        ydl_opts = {
            'outtmpl': f'{self.output_dir}/{output_filename}',
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self._set_state(DownloadState.FINISHED)
            self.finished.emit(f'{self.output_dir}/{output_filename}')
        except Exception as e:
            self._set_state(DownloadState.ERROR)
            self.error.emit(str(e))

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed') or 0
            if total > 0:
                percent = (downloaded / total) * 100
                speed_str = self._format_speed(speed)
                size_str = self._format_size(downloaded, total)
                self.progress_changed.emit(percent, speed_str, size_str)
        elif d['status'] == 'finished':
            pass

    def _format_speed(self, speed: float) -> str:
        if speed is None:
            return "0B/s"
        if speed >= 1024 * 1024:
            return f"{speed / (1024*1024):.1f}MB/s"
        return f"{speed / 1024:.1f}KB/s"

    def _format_size(self, downloaded: int, total: int) -> str:
        d_mb = downloaded / (1024 * 1024)
        t_mb = total / (1024 * 1024)
        return f"{d_mb:.1f}MB / {t_mb:.1f}MB"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloader.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/downloader.py tests/test_downloader.py
git commit -m "feat: add Downloader with progress signals"
```

---

## Task 5: Config Manager

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest
import tempfile
import os
from src.config import Config

def test_default_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config(tmpdir)
        assert "bilibili" in cfg.output_dir
        assert os.path.isdir(cfg.output_dir)

def test_set_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config(tmpdir)
        new_dir = os.path.join(tmpdir, "new_output")
        cfg.output_dir = new_dir
        assert cfg.output_dir == new_dir

def test_config_persists():
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg1 = Config(tmpdir)
        new_dir = os.path.join(tmpdir, "persist")
        cfg1.output_dir = new_dir
        cfg1.save()

        cfg2 = Config(tmpdir)
        assert cfg2.output_dir == new_dir
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `Config` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# src/config.py
import json
import os

class Config:
    def __init__(self, app_data_dir: str):
        self.app_data_dir = app_data_dir
        self.config_file = os.path.join(app_data_dir, "config.json")
        self._output_dir = ""
        self._load()

    def _load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._output_dir = data.get('output_dir', self._default_output_dir())
        else:
            self._output_dir = self._default_output_dir()

    def _default_output_dir(self) -> str:
        videos = os.path.join(os.path.expanduser("~"), "Videos", "bilibili")
        os.makedirs(videos, exist_ok=True)
        return videos

    @property
    def output_dir(self) -> str:
        return self._output_dir

    @output_dir.setter
    def output_dir(self, value: str):
        os.makedirs(value, exist_ok=True)
        self._output_dir = value
        self.save()

    def save(self):
        os.makedirs(self.app_data_dir, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump({'output_dir': self._output_dir}, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add Config for settings persistence"
```

---

## Task 6: Video Info Panel Widget

**Files:**
- Create: `src/widgets/video_info_panel.py`
- Create: `tests/test_video_info_panel.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video_info_panel.py
import pytest
from PyQt6.QtWidgets import QApplication
from src.widgets.video_info_panel import VideoInfoPanel
from src.video_info import VideoInfo

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_panel_shows_video_info(app):
    panel = VideoInfoPanel()
    info = VideoInfo(
        bv_id="BV1xx411xxx",
        title="测试视频",
        duration=754,
        thumbnail="",
        output_filename="测试视频_bilibili_BV1xx411xxx.mp4"
    )
    panel.set_video_info(info)
    assert "测试视频" in panel.title_label.text()
    assert "BV1xx411xxx" in panel.bv_label.text()
    assert "12:34" in panel.duration_label.text()

def test_panel_empty_by_default(app):
    panel = VideoInfoPanel()
    assert "暂无视频信息" in panel.title_label.text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_video_info_panel.py -v`
Expected: FAIL — widget not defined

- [ ] **Step 3: Write minimal implementation**

```python
# src/widgets/video_info_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from src.video_info import VideoInfo
import urllib.request

class VideoInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.title_label = QLabel("暂无视频信息")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.title_label)

        meta_layout = QHBoxLayout()
        self.bv_label = QLabel("")
        self.duration_label = QLabel("")
        meta_layout.addWidget(self.bv_label)
        meta_layout.addWidget(self.duration_label)
        meta_layout.addStretch()
        layout.addLayout(meta_layout)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(160, 90)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumbnail_label)

        self.filename_label = QLabel("")
        self.filename_label.setStyleSheet("color: #666; font-size: 12px;")
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label)

        self._clear()

    def _clear(self):
        self.title_label.setText("暂无视频信息")
        self.bv_label.setText("")
        self.duration_label.setText("")
        self.thumbnail_label.setText("无封面")
        self.thumbnail_label.setPixmap(QPixmap())
        self.filename_label.setText("")

    def set_video_info(self, info: VideoInfo):
        self.title_label.setText(info.title)
        self.bv_label.setText(f"BV号：{info.bv_id}")
        self.duration_label.setText(f"时长：{info.formatted_duration}")
        self.filename_label.setText(f"文件名：{info.output_filename}")
        self._load_thumbnail(info.thumbnail)

    def _load_thumbnail(self, url: str):
        if not url:
            self.thumbnail_label.setText("无封面")
            return
        try:
            data = urllib.request.urlopen(url, timeout=5).read()
            pixmap = QPixmap()
            pixmap.loadFromData(data)
            scaled = pixmap.scaled(160, 90, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled)
        except Exception:
            self.thumbnail_label.setText("封面加载失败")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_video_info_panel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/widgets/video_info_panel.py tests/test_video_info_panel.py
git commit -m "feat: add VideoInfoPanel widget"
```

---

## Task 7: Download Progress Widget

**Files:**
- Create: `src/widgets/download_progress.py`

- [ ] **Step 1: Write the widget**

```python
# src/widgets/download_progress.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt

class DownloadProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.status_label = QLabel("等待下载...")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        speed_layout = QHBoxLayout()
        self.speed_label = QLabel("")
        self.size_label = QLabel("")
        speed_layout.addWidget(self.speed_label)
        speed_layout.addWidget(self.size_label)
        speed_layout.addStretch()
        layout.addLayout(speed_layout)

    def set_idle(self):
        self.status_label.setText("等待下载...")
        self.status_label.setStyleSheet("color: #888;")
        self.progress_bar.setValue(0)
        self.speed_label.setText("")
        self.size_label.setText("")

    def set_downloading(self, percent: float, speed: str, size: str):
        self.status_label.setText("下载中...")
        self.status_label.setStyleSheet("color: #2196F3;")
        self.progress_bar.setValue(int(percent))
        self.speed_label.setText(speed)
        self.size_label.setText(size)

    def set_finished(self):
        self.status_label.setText("下载完成")
        self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self.progress_bar.setValue(100)
        self.speed_label.setText("")
        self.size_label.setText("")

    def set_error(self, message: str):
        self.status_label.setText(f"下载失败：{message}")
        self.status_label.setStyleSheet("color: #F44336;")
        self.progress_bar.setValue(0)
```

- [ ] **Step 2: Commit**

```bash
git add src/widgets/download_progress.py
git commit -m "feat: add DownloadProgress widget"
```

---

## Task 8: Download History Widget

**Files:**
- Create: `src/widgets/download_history.py`

- [ ] **Step 1: Write the widget**

```python
# src/widgets/download_history.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt

class DownloadHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)

        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(120)
        layout.addWidget(self.list_widget)

    def add_entry(self, title: str, bv_id: str, state: str, size: str = ""):
        text = f"{'✅' if state == 'finished' else '❌'} {title} ({bv_id})"
        if size:
            text += f" — {size}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, {'bv_id': bv_id, 'title': title})
        self.list_widget.insertItem(0, item)

    def clear_history(self):
        self.list_widget.clear()
```

- [ ] **Step 2: Commit**

```bash
git add src/widgets/download_history.py
git commit -m "feat: add DownloadHistoryWidget"
```

---

## Task 9: File Exists Dialog

**Files:**
- Create: `src/widgets/file_exists_dialog.py`

- [ ] **Step 1: Write the widget**

```python
# src/widgets/file_exists_dialog.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt

class FileExistsDialog(QDialog):
    RENAME = "rename"
    OVERWRITE = "overwrite"
    SKIP = "skip"

    def __init__(self, filename: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文件已存在")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"文件已存在：\n{filename}"))
        layout.addWidget(QLabel("请选择操作："))

        btn_layout = QHBoxLayout()
        self.rename_btn = QPushButton("重命名")
        self.overwrite_btn = QPushButton("覆盖")
        self.skip_btn = QPushButton("跳过")
        self.rename_btn.clicked.connect(lambda: self.done(self.RENAME))
        self.overwrite_btn.clicked.connect(lambda: self.done(self.OVERWRITE))
        self.skip_btn.clicked.connect(lambda: self.done(self.SKIP))
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.overwrite_btn)
        btn_layout.addWidget(self.skip_btn)
        layout.addLayout(btn_layout)
```

- [ ] **Step 2: Commit**

```bash
git add src/widgets/file_exists_dialog.py
git commit -m "feat: add FileExistsDialog for R10"
```

---

## Task 10: Main Window

**Files:**
- Create: `src/main_window.py`

- [ ] **Step 1: Write the main window**

```python
# src/main_window.py
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSlot
from src.video_parser import VideoParser, InvalidVideoURLError
from src.downloader import Downloader, DownloadState
from src.config import Config
from src.video_info import VideoInfo
from src.widgets.video_info_panel import VideoInfoPanel
from src.widgets.download_progress import DownloadProgress
from src.widgets.download_history import DownloadHistoryWidget
from src.widgets.file_exists_dialog import FileExistsDialog

class DownloadThread(QThread):
    def __init__(self, downloader: Downloader, url: str, output_filename: str):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_filename = output_filename

    def run(self):
        self.downloader.download(self.url, self.output_filename)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bilibili 视频下载器")
        self.setMinimumSize(600, 500)

        app_data = os.path.join(os.path.expanduser("~"), ".bilibili-downloader")
        os.makedirs(app_data, exist_ok=True)
        self.config = Config(app_data)
        self.parser = VideoParser()
        self.current_video_info: VideoInfo | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        # URL input row
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入 Bilibili 视频链接或 BV号...")
        self.download_btn = QPushButton("下载")
        self.download_btn.clicked.connect(self._on_download_clicked)
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.download_btn)
        layout.addLayout(input_layout)

        # Video info panel
        self.info_panel = VideoInfoPanel()
        layout.addWidget(self.info_panel)

        # Progress
        self.progress_widget = DownloadProgress()
        layout.addWidget(self.progress_widget)

        # History
        history_label = QLabel("下载历史")
        history_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(history_label)
        self.history_widget = DownloadHistoryWidget()
        layout.addWidget(self.history_widget)

        # Output dir
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"输出目录：{self.config.output_dir}")
        self.dir_label.setStyleSheet("color: #666; font-size: 12px;")
        self.change_dir_btn = QPushButton("更改")
        self.change_dir_btn.clicked.connect(self._on_change_dir)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.change_dir_btn)
        layout.addLayout(dir_layout)

        layout.addStretch()

        self.url_input.returnPressed.connect(self._on_download_clicked)

    def _on_change_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录", self.config.output_dir)
        if folder:
            self.config.output_dir = folder
            self.dir_label.setText(f"输出目录：{folder}")

    @pyqtSlot()
    def _on_download_clicked(self):
        raw = self.url_input.text().strip()
        if not raw:
            return

        self.download_btn.setEnabled(False)
        self.progress_widget.set_idle()

        try:
            self.current_video_info = self.parser.parse(raw)
            self.info_panel.set_video_info(self.current_video_info)
            self._start_download()
        except InvalidVideoURLError as e:
            QMessageBox.warning(self, "解析失败", str(e))
            self.download_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"解析时发生错误：{str(e)}")
            self.download_btn.setEnabled(True)

    def _start_download(self):
        if not self.current_video_info:
            return

        output_path = os.path.join(self.config.output_dir, self.current_video_info.output_filename)

        if os.path.exists(output_path):
            dialog = FileExistsDialog(self.current_video_info.output_filename, self)
            result = dialog.exec()
            if result == FileExistsDialog.SKIP:
                self.download_btn.setEnabled(True)
                return
            if result == FileExistsDialog.RENAME:
                base, ext = os.path.splitext(self.current_video_info.output_filename)
                counter = 1
                while os.path.exists(os.path.join(self.config.output_dir, f"{base}_{counter}{ext}")):
                    counter += 1
                self.current_video_info.output_filename = f"{base}_{counter}{ext}"

        bv_id = self.current_video_info.bv_id
        url = f"https://www.bilibili.com/video/{bv_id}"

        self.downloader = Downloader(self.config.output_dir)
        self.downloader.progress_changed.connect(self._on_progress)
        self.downloader.state_changed.connect(self._on_state)
        self.downloader.finished.connect(self._on_finished)
        self.downloader.error.connect(self._on_error)

        self.download_thread = DownloadThread(self.downloader, url, self.current_video_info.output_filename)
        self.download_thread.start()

    @pyqtSlot(float, str, str)
    def _on_progress(self, percent, speed, size):
        self.progress_widget.set_downloading(percent, speed, size)

    @pyqtSlot(str)
    def _on_state(self, state):
        pass

    @pyqtSlot(str)
    def _on_finished(self, path):
        self.progress_widget.set_finished()
        self.history_widget.add_entry(
            self.current_video_info.title,
            self.current_video_info.bv_id,
            "finished"
        )
        self.download_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_error(self, message):
        self.progress_widget.set_error(message)
        self.history_widget.add_entry(
            self.current_video_info.title if self.current_video_info else "未知",
            self.current_video_info.bv_id if self.current_video_info else "",
            "error"
        )
        self.download_btn.setEnabled(True)
```

- [ ] **Step 2: Commit**

```bash
git add src/main_window.py
git commit -m "feat: add MainWindow with full UI"
```

---

## Task 11: Main Entry Point

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write main.py**

```python
# main.py
import sys
from PyQt6.QtWidgets import QApplication
from src.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify project structure is correct**

```bash
find . -name "*.py" | sort
```

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add main entry point"
```

---

## Verification Commands

Run all tests:
```bash
pytest tests/ -v
```

Run the app (requires PyQt6 + yt-dlp installed):
```bash
pip install -r requirements.txt
python main.py
```

---

## Self-Review Checklist

- [ ] All requirements R1-R10 have a corresponding task
- [ ] No placeholder code (TBD, TODO) in any task
- [ ] Task 10 (R10 file exists dialog) fully implements the "覆盖/跳过/重命名" three-way choice
- [ ] Download runs in QThread (not blocking GUI)
- [ ] yt-dlp progress hook emits Qt signals for thread-safe GUI updates
- [ ] Config persists output_dir to JSON file
- [ ] File paths are correct and consistent across all tasks
