---
date: 2026-04-05
topic: bilibili-video-downloader
---

# Bilibili 视频下载工具

## Problem Frame

用户需要一个图形界面的工具来下载 Bilibili 普通视频，无需使用命令行。目前市面上的工具要么是纯命令行（yt-dlp），要么体验不佳或安全性存疑。一个简洁、安全、自已可控的桌面工具可以解决这个问题。

## Requirements

**核心下载**
- R1. 支持通过完整 URL（如 `https://www.bilibili.com/video/BVxxxxx`）或纯 BV号（如 `BV1xxxx`）识别视频
- R2. 调用 yt-dlp 完成下载，默认选择最高可用画质
- R3. 文件命名模板：`{视频标题}_bilibili_{BV号}.{后缀}`

**用户界面**
- R4. 主窗口包含：URL输入框 + 下载按钮、视频信息预览区、下载进度条、下载历史列表、输出目录选择
- R5. 实时显示下载进度：百分比、当前速度、已下载/总大小
- R6. 视频信息预览：标题、封面图（缩略图）、时长、BV号
- R7. 可更改输出目录，默认为用户 Videos/bilibili 文件夹

**异常处理**
- R8. 解析失败时显示明确错误信息（如"视频不存在"、"网络错误"）
- R9. 下载失败时显示错误原因，允许重试
- R10. 文件已存在时弹窗询问用户：覆盖、跳过、或手动重命名

## Success Criteria

- 用户粘贴 BV号 或 URL 后 3 秒内显示视频信息预览
- 下载过程中进度条实时更新，速度显示准确
- 下载完成的文件可用默认播放器直接播放
- 工具本身无需管理员权限即可运行

## Scope Boundaries

**本次不做：**
- 番剧、电影、电视剧等多 P 内容下载
- YouTube、Missav 等其他平台支持
- 多线程并发下载
- 断点续传 UI（yt-dlp 底层支持但 GUI 层面不暴露）
- 音频单独下载

## Key Decisions

- **GUI 框架**: PyQt6 — Python 原生，性能足够，界面美观
- **下载核心**: yt-dlp — 最成熟稳定的 Bilibili 下载方案，自己维护解析逻辑的性价比极低
- **文件命名**: 标题_BV号 — 兼顾可读性和来源识别

## Dependencies / Assumptions

- 用户已安装 Python 3.10+ 环境
- yt-dlp 通过 pip 安装，非系统打包版本
- Windows 10/11 系统（主要目标平台）

## Next Steps

→ `/ce:plan` for structured implementation planning
