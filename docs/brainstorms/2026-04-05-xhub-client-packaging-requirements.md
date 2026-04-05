---
date: 2026-04-05
topic: xhub-client-packaging
---

# xhub 客户端打包

## Problem Frame

xhub 是一个基于 PyQt6 的视频下载器，当前需要从 Python 源代码运行。用户希望将其封装成 Windows 可执行安装程序，降低使用门槛，无需安装 Python 环境即可运行。

## Requirements

**Windows 打包**
- R1. 使用 PyInstaller 将 xhub 打包为 Windows 可执行文件
- R2. 生成 NSIS 安装程序（`.exe`），支持标准安装流程
- R3. 打包后的可执行文件无控制台窗口（`--noconsole` / `winsubsystem`)
- R4. 应用图标使用 `assets/icon.jpg`
- R5. 打包时隐藏所有 PyQt6/yt-dlp/playwright 的隐式导入

**安装程序行为**
- R6. 安装程序在开始菜单和桌面创建快捷方式
- R7. 安装路径默认使用 `C:\Program Files\xhub`，允许用户自定义
- R8. 安装程序包含卸载功能，可通过 Windows 设置卸载

**无自动更新**
- R9. 不包含自动更新功能，用户手动下载新版本安装

## Success Criteria
- 双击安装程序完成安装，无需额外依赖
- 安装后桌面和开始菜单有快捷方式
- 启动 exe 直接运行，无控制台窗口
- PyQt6 GUI 正常显示，支持视频下载功能

## Scope Boundaries
- 仅打包 Windows，macOS 不在本次范围内
- 不包含自动更新机制

## Key Decisions
- **PyInstaller**：成熟稳定，Windows 兼容性好，配置简单
- **NSIS 安装程序**：体积小、配置灵活、Windows 原生感强
- **--noconsole**：GUI 应用无需控制台窗口

## Dependencies / Assumptions
- 依赖 PyQt6、yt-dlp、playwright、playwright-stealth，需在 spec 文件中显式声明隐式导入
- Playwright 浏览器二进制文件需在构建时一并打包（`playwright install --with-deps`）

## Next Steps
- → `/ce:plan` for structured implementation planning
