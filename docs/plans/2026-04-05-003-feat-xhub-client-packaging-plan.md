---
title: "feat: Package xhub as Windows installer"
type: feat
status: active
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-xhub-client-packaging-requirements.md
---

# Package xhub as Windows Installer

## Overview

使用 PyInstaller 将 xhub 打包为单文件 exe，再用 NSIS 生成安装程序，实现双击安装、开始菜单和桌面快捷方式、卸载功能。

## Requirements Trace

- R1. 使用 PyInstaller 打包为 Windows exe
- R2. 生成 NSIS 安装程序
- R3. 无控制台窗口
- R4. 应用图标为 `assets/icon.png`（构建前需转换为 .ico 格式供 PyInstaller 使用）
- R5. 隐藏所有隐式导入
- R6. 开始菜单和桌面快捷方式
- R7. 默认安装路径 `C:\Program Files\xhub`，支持自定义
- R8. 安装程序含卸载功能
- R9. 无自动更新

## Scope Boundaries

- 仅打包 Windows，macOS 不在范围内
- 不包含自动更新

## Context & Research

### Relevant Code and Patterns

- `main.py` — 入口文件，PyInstaller 分析目标
- `src/main_window.py` — GUI 主窗口，窗口标题已改为 "xhub"
- `assets/icon.png` — 应用图标（构建前需用 Pillow 转为 .ico 格式）
- `requirements.txt` — PyQt6, yt-dlp, playwright, playwright-stealth

### Key Technical Decisions

- **Spec file approach**：先 `pyi-makespec` 生成骨架，再手动添加 hiddenimports，比完全手写更可靠
- **console=False**：`--noconsole` 等效参数，Windows subsystem 模式
- **Playwright browser path**：构建前设 `PLAYWRIGHT_BROWSERS_PATH=0`，使浏览器下载到可打包位置
- **NSIS 钩子**：在 spec `Analysis()` 中通过 `binaries` 注入 ms-playwright 目录

## Implementation Units

- [ ] **Unit 1: Create PyInstaller spec file**

**Goal:** 生成包含所有隐式导入和数据的 spec 文件

**Requirements:** R1, R3, R4, R5

**Files:**
- Create: `xhub.spec`（位于仓库根目录，与 main.py 同级）

**Approach:**
1. 用 Pillow 将 `assets/icon.png` 转换为 Windows 所需的 .ico 格式：`Image.open('assets/icon.png').resize((256,256)).save('assets/icon.ico')`
2. 运行 `pyi-makespec --noconsole --onefile --name xhub --icon assets/icon.ico main.py` 生成骨架
3. 编辑 spec，手动添加 `hiddenimports`：
   - `PyQt6.sip`
   - `playwright.sync_api`
   - `playwright_stealth.stealth`
   - `brotli`, `certifi`, `mutagen`, `websockets`（yt_dlp 隐式依赖）
   - `yt_dlp` 及子模块（通过 `collect_submodules`），重点包括 `yt_dlp.utils`, `yt_dlp.extractor`
4. 通过 `collect_data_files` 收集 PyQt6 和 yt_dlp 数据文件
5. 通过 `copy_metadata` 收集 playwright 和 yt-dlp 元数据
6. Playwright 浏览器二进制：通过 `binaries` 列表注入 `ms-playwright` 目录（见 Unit 2）

**Test scenarios:**
- Happy path: `pyinstaller xhub.spec` 成功，无 import 错误
- Error path: 运行时出现 `ModuleNotFoundError`，补充对应 hiddenimport

**Verification:**
- `pyinstaller --debug=imports xhub.spec 2>&1 | grep "ModuleNotFoundError"` 无输出
- 构建完成后运行 `dist/xhub.exe`，PyQt6 窗口正常显示

---

- [ ] **Unit 2: Bundle Playwright browser binaries**

**Goal:** Playwright chromium 浏览器随包分发，运行时不依赖外部安装

**Requirements:** R1 (隐式)

**Files:**
- Modify: `xhub.spec`

**Approach:**
1. 构建前设置环境变量：`set PLAYWRIGHT_BROWSERS_PATH=0`
2. 运行 `python -m playwright install chromium --with-deps`，浏览器下载到 `%USERPROFILE%\AppData\Local\ms-playwright`
3. 在 spec 的 `binaries` 中添加：`(os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'ms-playwright'), 'ms-playwright')`
4. 在应用代码中添加路径检测逻辑（使用 `sys._MEIPASS`），使 playwright 在打包后能找到浏览器

**Test scenarios:**
- Happy path: `dist/xhub.exe` 运行时，playwright 能启动 chromium 无报错
- Error path: 浏览器找不到，检查 ms-playwright 目录是否被正确打包

**Verification:**
- 运行 `dist/xhub.exe`，下载一个视频，观察 playwright 是否正常调用 chromium

---

- [ ] **Unit 3: Create NSIS installer script**

**Goal:** 生成 Windows 安装程序，支持快捷方式、卸载功能

**Requirements:** R2, R6, R7, R8

**Files:**
- Create: `xhub-installer.nsi`

**Approach:**
- 标准的 NSIS 脚本，包含：
  - MUI2 界面，支持简体中文
  - `OutFile "xhub-installer.exe"`
  - `InstallDir "$PROGRAMFILES\xhub"`，支持用户自定义路径
  - R6: `CreateShortcut` 创建开始菜单和桌面快捷方式
  - R7: 注册 `HKLM\Software\xhub` 存储安装路径
  - R8: 写入 `Uninstall\` 注册表项，含卸载exe路径和图标
  - Section Uninstall 删除文件、快捷方式、注册表项
  - 用户数据（`%APPDATA%` 下的配置）保留不删除（标准 Windows 约定）

**Test scenarios:**
- Happy path: `makensis xhub-installer.nsi` 成功生成 exe
- Happy path: 双击安装程序，完成安装，桌面和开始菜单有快捷方式
- Error path: 卸载后检查注册表 `Uninstall\` 项是否已清除

**Verification:**
- 安装后从开始菜单和桌面都能正常启动 xhub
- Windows 设置 → 应用 → 已安装程序中能看到 xhub，可正常卸载

---

- [ ] **Unit 4: Create Windows build script**

**Goal:** 一键构建脚本，自动化完整构建流程

**Requirements:** R1, R2 (隐式)

**Files:**
- Create: `build.bat`

**Approach:**
- 顺序执行：
  1. `pip install -r requirements.txt`
  2. `set PLAYWRIGHT_BROWSERS_PATH=0 && python -m playwright install chromium --with-deps`
  3. `pyinstaller xhub.spec`
  4. `makensis xhub-installer.nsi`
- 输出文件：`dist/xhub.exe` 和 `xhub-installer.exe`

**Test scenarios:**
- Happy path: 在干净 Windows 环境（或 CI）运行 `build.bat`，最终生成 `xhub-installer.exe`
- Error path: 某步骤失败，根据错误日志定位问题

**Verification:**
- `xhub-installer.exe` 文件存在且可执行

---

## System-Wide Impact

- **Entry point**: `main.py` 不变，打包后行为与源码运行一致
- **Config storage**: `~/.bilibili-downloader/` 和 `%APPDATA%/missav-downloader/` 保持不变，打包后路径解析需通过 `sys._MEIPASS` 判断是否为 frozen 环境

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Playwright 浏览器未正确打包 | 验证 `dist/xhub.exe` 运行时 chromium 正常启动 |
| PyInstaller 漏检隐式导入 | 使用 `--debug=imports` 检查，补充 hiddenimports |
| NSIS 安装后快捷方式无效 | 使用绝对路径 `$INSTDIR\xhub.exe`，避免 PATH 依赖 |
| Windows 安全策略阻止未签名 exe | 说明用户需允许运行或签名（签名不在本次范围） |

## Documentation / Operational Notes

- 构建需要在 Windows 环境下运行（PyInstaller + NSIS 均无跨平台构建能力）
- 生成的安装程序建议由用户手动允许运行（Windows SmartScreen 首次拦截属正常）
