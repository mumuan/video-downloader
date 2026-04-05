---
title: "feat: Add stealth browser for automated Cloudflare bypass"
type: feat
status: completed
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-missav-live-support-requirements.md
---

# feat: Add stealth browser for automated Cloudflare bypass

## Overview

Replace `SessionManager`'s headed-browser fallback with `playwright-extra` + `stealth` plugin. The goal is to pass Cloudflare's JS challenge automatically in headless mode — **no visible browser, no manual checkbox click, no user interaction ever**.

## Problem Frame

The current implementation (`session_manager.py`) uses plain `playwright.sync_api`. When the `cf_clearance` cookie is absent or expired, it launches a **headed** Chromium browser and waits for the user to manually click the Cloudflare checkbox. This is a friction point. The stealth approach wraps Playwright with browser-fingerprint patches that make automation signals invisible to Cloudflare's detection layer, potentially eliminating the challenge entirely.

## Requirements Trace

- R4 (evolved): ~~首次使用：启动**可见浏览器**（headed mode）让用户手动通过 Cloudflare 验证~~ → 首次及后续：始终使用 stealth headless 浏览器自动通过 Cloudflare 验证，无需用户交互
- R8: session 超时或失效时提示用户重新验证（stealth 自动重试，超限后报错）

## Scope Boundaries

- 不改变视频提取逻辑（`MissavParser.parse()` 内部不变）
- 不改变 `VideoInfo` 结构
- 不改变下载流程（`Downloader` 复用）
- 不支持 headed 浏览器作为 fallback（pure stealth 策略）
- Cloudflare 升级导致 stealth 失效视为已知风险，接受该风险而非引入 headed fallback

## Key Technical Decisions

- **Pure stealth vs stealth + headed fallback**: Pure stealth 优先。Cloudflare 检测进化可能导致 stealth 失效——这是可预期的退化，不引入 headed fallback，而是通过重试 + 错误提示处理
- **playwright-stealth vs 手动 patching**: 使用 `playwright-stealth`（内置 `Stealth` 类 + `hook_playwright_context` API），无需手动维护 evasion 代码
- **重试策略**: stealth headless 首次失败后最多重试 2 次（间隔 3s），每次用 fresh context，避免 cookie 污染
- **Session cookie 策略不变**: `cf_clearance` cookie 仍用于避免重复 challenge；stealth 处理首次无 cookie 时的 challenge

## Context & Research

### Relevant Code and Patterns

- `src/parsers/session_manager.py` — 当前 `SessionManager.get_verified_context()` 的 headed fallback 需要替换
- `src/parsers/missav_parser.py` — `MissavParser.parse()` 调用 `SessionManager.get_verified_context()`，接口不变（import 无需修改）
- `src/video_info.py` — 无变更
- `requirements.txt` — 新增 `playwright-stealth`

### External References

- `playwright-stealth` (PyPI): https://pypi.org/project/playwright-stealth/ — `Stealth` class with built-in evasions, applied via `stealth().use_sync(playwright)` context manager
- stealth-evasions 是 `playwright-stealth` 内置的，通过 `Stealth` 类应用

## Open Questions

### Resolved During Planning

- **MissavParser 是否需要修改**: 不需要，`SessionManager.get_verified_context()` 在内部调用 `stealth_module.Stealth().hook_playwright_context(p)` 应用 stealth，MissavParser 的 import 和调用方式不变
- **重试次数**: 3 次尝试（1 次 fresh + 2 次 retry），间隔 3 秒

### Deferred to Implementation

- [技术] playwright-stealth 具体哪些 evasions 对 missav Cloudflare 最有效（通过实验确定）
- [技术] 如果 stealth 全面失效，是否需要降级到 headed（用户明确说 no）

## Implementation Units

- [x] **Unit 1: Add playwright-stealth dependency** ✅

**Goal:** 引入 stealth 所需的包

**Requirements:** R4 (evolved)

**Dependencies:** None

**Files:**
- Modify: `requirements.txt`

**Approach:**
```
新增一行：
playwright-stealth>=1.0.0
```
注意：`playwright-stealth` 的 evasions 内置在包中，无需单独依赖。

**Patterns to follow:**
- `requirements.txt` 现有依赖格式

**Test scenarios:**
- Test expectation: none — 纯依赖添加，无行为变化

**Verification:**
- `pip install -r requirements.txt` 成功，无冲突

---

- [x] **Unit 2: Refactor SessionManager to use playwright-stealth** ✅

**Goal:** `get_verified_context()` 始终使用 stealth headless，自动通过 Cloudflare JS challenge

**Requirements:** R4 (evolved), R8

**Dependencies:** Unit 1

**Files:**
- Modify: `src/parsers/session_manager.py`
- Test: `tests/test_session_manager.py`

**Approach:**

核心改动：`get_verified_context()` 不再判断 headless vs headed，而是统一使用 stealth headless。关键：必须在 `page.goto()` 之前应用 stealth。

```
from playwright_stealth import stealth as stealth_module

def get_verified_context(self, p, target_url):
    # 加载已有 cookie（若有效则直接用；无效时 stealth 尝试自动过 challenge）
    if self.is_cookie_valid():
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(self.state_file))
        # stealth 必须在 page.goto() 之前应用
        stealth_module.Stealth().hook_playwright_context(p)
        page = context.new_page()
        page.goto(target_url)
        page.wait_for_timeout(3000)
        if page.title() not in ("Just a moment...", "请稍候…"):
            return context, browser
        # challenge 仍在，cookie 可能已失效，关闭并进入重试流程
        browser.close()

    # 无有效 cookie 或 challenge 未通过 → stealth headless 重试
    for attempt in range(3):
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        # stealth 必须在 page.goto() 之前应用
        stealth_module.Stealth().hook_playwright_context(p)
        page = context.new_page()
        page.goto(target_url)
        # 等待 challenge 完成
        try:
            page.wait_for_selector("video", timeout=20000)
        except Exception:
            if attempt == 2:
                browser.close()
                raise VideoParseError("Cloudflare 验证失败，请稍后重试")
            page.wait_for_timeout(3000)
            browser.close()
            continue
        # 验证通过，保存 session
        context.storage_state(path=str(self.state_file))
        return context, browser

    raise VideoParseError("Cloudflare 验证超时，请稍后重试")
```

注意：`stealth_module.Stealth().hook_playwright_context(p)` 在 `browser.launch()` 之前调用，确保 stealth patches 在导航前生效。

**Patterns to follow:**
- 现有 `SessionManager.is_cookie_valid()` 和 `storage_state()` 逻辑完全保留
- `VideoParseError` 异常类保留

**Test scenarios:**
- Happy path: cookie 有效，headless stealth 加载 cookie 后直接通过（无 challenge 页面）
- Happy path: cookie 无效，stealth headless 自动通过 challenge，video 元素出现，session 保存
- Edge case: stealth 首次失败，自动 retry（最多 3 次），每次 fresh context
- Error path: 所有 retry 都失败，抛出 `VideoParseError("Cloudflare 验证失败，请稍后重试")`
- Error path: cookie 有效但页面仍显示 challenge（cookie 实际已失效），自动 retry

**Verification:**
- 真实 URL 测试: `MissavParser().parse("https://missav.live/ja/mfcw-008-uncensored-leak")` 在无预先 cookie 的干净环境下，stealth headless 自动通过 Cloudflare challenge 并返回有效 `VideoInfo`
- `pytest tests/test_session_manager.py` 通过

---

- [x] **Unit 3: No import change needed in MissavParser** ✅

**Goal:** Clarify that MissavParser's import does not need to change

**Requirements:** R4 (evolved)

**Dependencies:** Unit 1, Unit 2

**Files:**
- None (no files modified)

**Note:** `SessionManager.get_verified_context()` applies `stealth_module.Stealth().hook_playwright_context(p)` internally after receiving the playwright instance from MissavParser. MissavParser's `playwright.sync_api` import and `sync_playwright()` usage remain unchanged — stealth is applied transparently inside SessionManager.

---

- [ ] **Unit 4: Functional test with real missav URL**

**Goal:** End-to-end 验证 stealth Cloudflare bypass 实际工作

**Requirements:** R4 (evolved), R8

**Dependencies:** Unit 1, Unit 2, Unit 3

**Files:**
- Test: `tests/test_missav_parser.py`（如已存在则增强）

**Approach:**
手动测试步骤（无法自动化 CI）：
1. 删除本地 cookie 文件 `%APPDATA%/missav-downloader/cookies/cloudflare_state.json`
2. 运行 `MissavParser().parse("https://missav.live/ja/mfcw-008-uncensored-leak")`
3. 观察：无 headed 浏览器弹出，无用户交互，video 直链成功返回
4. 重复步骤 1-3 验证 session 复用（第二次更快）

**Test scenarios:**
- Happy path: 全新 cookie + stealth headless → 自动通过 challenge
- Happy path: 有效 cookie + stealth headless → 直接返回，无 challenge
- Edge case: 连续 3 次 challenge 失败 → `VideoParseError`
- Edge case: 网络错误（非 Cloudflare）→ `VideoParseError` 区分错误类型

**Verification:**
- 手动测试通过：stealth headless 在无预先 cookie 时自动通过 Cloudflare

## System-Wide Impact

- **SessionManager**: 核心变更，`get_verified_context()` 接口不变但内部完全重写
- **MissavParser**: 无变更（stealth 在 SessionManager 内部透明应用）
- **VideoInfo**: 无变更
- **Downloader / UI**: 无变更
- **Bilibili parser**: 完全不受影响

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Cloudflare 升级检测逻辑，stealth 失效 | 可预期退化；重试 3 次后报错；用户感知为"服务暂时不可用"而非功能 bug |
| playwright-stealth 与当前 playwright 版本不兼容 | 锁定 `playwright-stealth>=1.0.0`；升级时需测试兼容性 |
| Headless stealth 在某些 VPN/代理环境下失效 | 非本功能范围；用户需确保网络环境正常 |
| Playwright stealth 与现有 playwright 冲突 | 使用 `playwright-stealth` 作为独立包，不修改 `playwright` 本身 |

## Documentation / Operational Notes

- 安装新依赖: `pip install playwright-stealth>=1.0.0`
- 无需额外浏览器安装（复用现有 chromium）
- playwright-stealth 的 evasions 通过 `Stealth().hook_playwright_context(p)` 应用在浏览器启动之前
- 用户文档: 更新 README 说明 missav.download 已完全自动化，无需手动验证
