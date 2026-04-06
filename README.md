# xhub Video Downloader

> A sleek desktop application for downloading videos from Bilibili, MissAV, and more.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **One-Click Download** — Paste a URL and get video info instantly
- **Multi-Platform Support** — Bilibili (BV号或链接), MissAV, and growing
- **Real-Time Progress** — Live download progress with speed indicators
- **Smart File Handling** — Ask to skip, overwrite, or rename when files exist
- **Download History** — Track all your downloads with resume capability
- **Actor Search** — Search and batch download by actor on supported sites

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Screenshots

```
┌─────────────────────────────────────────────────────┐
│  xhub Video Downloader                              │
├─────────────────────────────────────────────────────┤
│  [Paste URL here...]              [Parse]          │
│                                                     │
│  Video Title: ...                                   │
│  Duration: 05:32 | Size: 256 MB                     │
│  [▶ Download]                                       │
└─────────────────────────────────────────────────────┘
```

## Project Structure

```
src/
├── main_window.py          # Main application window
├── video_parser.py         # URL parsing factory
├── video_info.py           # Video metadata model
├── downloader.py           # Download engine
├── config.py               # Configuration
├── parsers/
│   ├── bilibili_parser.py  # Bilibili parser
│   ├── missav_parser.py    # MissAV parser
│   └── session_manager.py  # Session management
├── widgets/
│   ├── video_info_panel.py
│   ├── download_progress.py
│   ├── download_history.py
│   └── file_exists_dialog.py
tests/
└── *_test.py              # Unit tests
```

## Supported Sites

| Site | URL Format | Status |
|------|------------|--------|
| Bilibili | `BV...` or full URL | Stable |
| MissAV | Direct link | Stable |

## Tech Stack

- **Python 3.10+**
- **PyQt6** — Modern Qt bindings for Python
- **yt-dlp** — Video extraction backend

## License

MIT License — free to use, modify, and distribute.

---

## 中文说明

xhub 是一款简洁高效的桌面视频下载工具，支持 Bilibili 和 MissAV 等平台。

### 功能特点

- 粘贴 URL 自动解析视频信息
- 支持 Bilibili（BV号或链接）
- 下载进度实时显示
- 文件已存在时询问处理方式
- 下载历史记录
- 演员搜索与批量下载（MissAV）

### 安装运行

```bash
pip install -r requirements.txt
python main.py
```

### 项目结构

```
src/
├── main_window.py      # 主窗口
├── video_parser.py     # URL 解析工厂
├── video_info.py       # 视频信息模型
├── downloader.py       # 下载逻辑
├── config.py           # 配置
├── parsers/            # 解析器
│   ├── bilibili_parser.py
│   ├── missav_parser.py
│   └── session_manager.py
├── widgets/            # UI 组件
└── tests/              # 单元测试
```
