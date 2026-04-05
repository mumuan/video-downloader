# Video Downloader

支持 Bilibili 和 某些网站 的视频下载工具。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 功能

- 粘贴 URL 自动解析视频信息
- 支持 Bilibili (BV号 或链接) 
- 下载进度实时显示
- 文件已存在时询问处理方式
- 下载历史记录

## 项目结构

```
src/
  main_window.py      # 主窗口
  video_parser.py    # URL 解析工厂
  video_info.py      # 视频信息模型
  downloader.py      # 下载逻辑
  config.py          # 配置
  parsers/
    bilibili_parser.py
    missav_parser.py
    session_manager.py
  widgets/
    video_info_panel.py
    download_progress.py
    download_history.py
    file_exists_dialog.py
tests/
  *_test.py           # 单元测试
```
