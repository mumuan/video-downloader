---
title: "feat: Add missav.live download support"
type: feat
status: active
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-missav-live-support-requirements.md
---

# feat: Add missav.live download support

## Overview

Bilibili 已支持，missav.live 需要 Playwright 绕过 Cloudflare 才能提取视频直链。核心思路：首次用户在可见浏览器中手动通过 Cloudflare 验证，之后 session cookies 复用实现无感下载。视频直链由 yt-dlp 下载（复用现有 `Downloader`）。

## Problem Frame

missav.live 有 Cloudflare JS 验证质询，yt-dlp 无法直接提取（返回 403）。需要 Playwright 控制真实浏览器完成验证，提取 `<video src>` 直链，再由 yt-dlp 下载。

## Requirements Trace

- R1: URL 输入框接受 `missav.live/*` 链接
- R2: `VideoParser` 工厂模式路由到对应解析器
- R3: 解析失败显示明确错误
- R4: 首次 headed 模式手动验证 + session 复用
- R5: 提取 `<video src>` 直链
- R6: 提取标题和封面
- R7: 返回与 Bilibili一致的 `VideoInfo`
- R8: session 失效提示重新验证
- R9: 复用 `Downloader` 下载直链
- R10: 文件命名 `{title}_missav_{video_id}.mp4`
- R11: missav 模式显示标题和封面
- R12: 历史记录标记来源站点
- R13: Cloudflare 超时提示重试
- R14: 直链获取失败有意义错误

## Scope Boundaries

- 不支持播放列表/批量下载
- 不支持需登录的付费视频
- 不实现 yt-dlp generic extractor fallback

## Key Technical Decisions

- **Session 管理**: `SessionManager.get_verified_context(playwright)` 内部根据 cookie 有效性决定：cookie 有效则启动 headless Chromium 并加载 storage_state；cookie 无效则启动 headed Chromium 让用户手动验证，验证后保存 state。存储用 `context.storage_state()` 保存至 `%APPDATA%/missav-downloader/cookies/cloudflare_state.json`
- **首次验证**: 启动 headed Chromium（窗口可见），等待用户手动通过 Cloudflare 复选框，验证成功后保存 state 文件，关闭浏览器
- **后续访问**: 启动 headless Chromium，加载已有 state 文件，无需再次验证，直接提取直链
- **Parser 工厂**: `VideoParser` 改为返回具体 parser 实例（`BilibiliVideoParser` / `MissavParser`），接口方法统一为 `parse(raw) -> VideoInfo`
- **VideoInfo 扩展**: 新增 `source_site: str` 字段（`"bilibili"` / `"missav"`），`bv_id` 字段在 missav 场景存储 URL slug

## Open Questions

### Resolved During Planning

- **MissavParser 抽象基类**: 不需要，用 duck typing + 统一 `parse()` 接口
- **首次验证 UI**: 保持 headed 浏览器可见，无需独立提示窗口
- **Session 文件路径**: `%APPDATA%/missav-downloader/cookies/cloudflare_state.json`（Windows 标准路径）

### Deferred to Implementation

- MissavParser 内部如何检测 Cloudflare challenge 完成（通过 `<video>` 元素是否出现判断）
- Chromium 在 Windows 上的路径（Playwright 自动处理）

## Implementation Units

- [ ] **Unit 1: VideoInfo 新增 source_site 字段**

**Goal:** `VideoInfo` dataclass 支持多站点来源

**Requirements:** R7, R12

**Dependencies:** None

**Files:**
- Modify: `src/video_info.py`
- Modify: `tests/test_video_info.py`

**Approach:** 新增 `source_site: str` 字段（默认值 `"bilibili"` 保持向后兼容），`output_filename` 生成逻辑移入各 parser（见 Unit 3）

**Patterns to follow:**
- `src/video_info.py` dataclass pattern

**Test scenarios:**
- Happy path: 创建 `VideoInfo(bv_id="BV123", source_site="missav", ...)` 可正常实例化
- Backward compat: 不传 `source_site` 时默认为 `"bilibili"`（测试现有行为不被破坏）

**Verification:**
- `pytest tests/test_video_info.py` 通过

---

- [ ] **Unit 2: VideoParser 重构为工厂模式**

**Goal:** `VideoParser` 内部路由到对应站点解析器，现有调用方（`main_window.py`）代码不变

**Requirements:** R1, R2

**Dependencies:** Unit 1

**Files:**
- Modify: `src/video_parser.py`
- Create: `src/parsers/__init__.py`
- Create: `src/parsers/bilibili_parser.py`（从 `video_parser.py` 提取）
- Create: `tests/test_video_parser.py`（更新）
- Create: `tests/test_bilibili_parser.py`

**Approach:**
```
VideoParser 工厂方法:
  _detect_site(url) -> "bilibili" | "missav" | "unsupported"
  parse(raw) -> 根据 site 分发到对应 parser，返回 VideoInfo

src/parsers/
  __init__.py         # 导出 BilibiliParser, MissavParser
  bilibili_parser.py   # 原 VideoParser 逻辑（重命名）
  missav_parser.py     # MissavParser（见 Unit 3）
```

URL 检测逻辑:
- `missav.live` in url → "missav"
- `bilibili.com` in url or `BV` prefix → "bilibili"
- 否则抛出 `InvalidVideoURLError`

BilibiliParser 从原 `VideoParser` 提取，逻辑不变。

**Patterns to follow:**
- `src/video_parser.py` 现有 `InvalidVideoURLError` 异常模式

**Test scenarios:**
- Happy path: `parse("https://www.bilibili.com/video/BV123")` 返回 BilibiliParser 结果
- Happy path: `parse("https://missav.live/ja/mfcw-008")` 路由到 MissavParser
- Edge case: `parse("https://youtube.com/...")` 抛出 InvalidVideoURLError("不支持的网站")
- Edge case: `parse("invalid-url")` 抛出 InvalidVideoURLError

**Verification:**
- 现有 Bilibili URL 下载流程不受影响
- `pytest tests/test_video_parser.py` 通过

---

- [ ] **Unit 3: MissavParser 实现（Playwright + Cloudflare）**

**Goal:** 用 Playwright 绕过 Cloudflare，提取 missav.live 视频直链

**Requirements:** R3, R4, R5, R6, R7, R8, R10, R13, R14

**Dependencies:** Unit 1, Unit 2（SessionManager 是 MissavParser 内部依赖）

**Files:**
- Create: `src/parsers/missav_parser.py`
- Create: `src/parsers/session_manager.py`
- Create: `tests/test_missav_parser.py`
- Create: `tests/test_session_manager.py`

**Approach:**

```
SessionManager (session_manager.py)
  cookie_dir = %APPDATA%/missav-downloader/cookies
  state_file = cloudflare_state.json

  is_cookie_valid() -> bool
    检查 cf_clearance cookie 存在且未过期（剩余 >1小时）

  get_verified_context(playwright, target_url) -> (BrowserContext, Browser)
    # 内部决定 headless / headed，不向外暴露 browser launch 细节
    if is_cookie_valid():
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(state_file))
        return context, browser
    else:
        browser = playwright.chromium.launch(headless=False)  # 窗口可见，用户手动验证
        context = browser.new_context()
        page = context.new_page()
        page.goto(target_url)
        page.wait_for_selector("input[type='checkbox']", timeout=5000)
        page.click("input[type='checkbox']")
        page.wait_for_selector("video", timeout=30000)  # 验证完成
        context.storage_state(path=str(state_file))
        return context, browser


MissavParser (missav_parser.py)
  class MissavParser:
    def parse(self, raw_url: str) -> VideoInfo:
      video_id = self._extract_video_id(raw_url)  # URL slug
      with sync_playwright() as p:
        context, browser = self._session_manager.get_verified_context(p, raw_url)  # 内部决定 headless 或 headed
        page = context.new_page()
        page.goto(raw_url)
        # 等待 video 元素
        page.wait_for_selector("video", timeout=30000)
        video_url = page.eval_on_selector("video", "v => v.src")
        title = page.title()
        og_image = page.eval_on_selector('meta[property="og:image"]', "m => m.content")
        # 提取视频 ID（从 URL slug）
        return VideoInfo(
          bv_id=video_id,
          title=title,
          duration=0,
          thumbnail=og_image or "",
          output_filename=self._make_filename(title, video_id),
          source_site="missav",
        )
        page.context().browser.close()  # 关闭浏览器
```

关键细节:
- **同步 Playwright**: `sync_playwright()` 配合 `DownloadThread` 使用，与 PyQt 事件循环隔离
- **Headed 首次验证**: `headless=False`，用户手动点复选框
- **Session 复用**: `storage_state()` 保存 cookies 到 JSON 文件，30 天有效
- **cf_clearance 过期**: 若 `is_cookie_valid()` 返回 False，重新 headed 验证
- **视频 ID 提取**: URL path 最后一个 segment（如 `mfcw-008-uncensored-leak` → `mfcw-008`）
- **文件名**: `{safe_title}_missav_{video_id}.mp4`

**Patterns to follow:**
- `src/parsers/bilibili_parser.py` 的 `parse()` 方法签名
- `src/downloader.py` 的 QObject 信号模式（参考，不直接用）

**Test scenarios:**
- Error path: Cookie 过期时，`get_verified_context` 启动 headed 浏览器（需要手动验证）
- Error path: 视频页面无法加载（网络错误）-> `VideoParseError`
- Error path: 页面无 `<video>` 元素（结构变更）-> `VideoParseError("无法获取视频，请检查链接是否有效")`
- Happy path: Cookie 有效时，headless 浏览器直接提取直链（无窗口弹出）

**Verification:**
- 真实 URL 测试: `MissavParser().parse("https://missav.live/ja/mfcw-008-uncensored-leak")` 返回有效 `VideoInfo`
- `pytest tests/test_missav_parser.py` 通过

---

- [ ] **Unit 4: 下载流程适配（URL 来源和历史标记）**

**Goal:** `main_window.py` 的下载流程适配多站点：URL 从 `VideoInfo` 获取，来源标记到历史记录

**Requirements:** R9, R12

**Dependencies:** Unit 1, Unit 2, Unit 3

**Files:**
- Modify: `src/main_window.py`
- Modify: `src/widgets/download_history.py`

**Approach:**

`_start_download()` 修改:
```python
# 之前（硬编码 Bilibili URL）:
url = f"https://www.bilibili.com/video/{bv_id}"

# 改为（所有站点通用）:
# VideoInfo 不再内嵌 URL；各 Parser 在 VideoInfo 中提供下载所需信息
# 对于 missav，直链已在 VideoInfo（待决定：是否加 direct_url 字段）
# 方案：从 VideoInfo.source_site 判断：
#   - bilibili: 构造 https://www.bilibili.com/video/{bv_id}
#   - missav: 直接使用 page 提取的直链 URL
# 更好的方案：VideoInfo 加 optional direct_url 字段，各 parser 填充
```

**Resolved: Option A adopted.** `VideoInfo` 新增 `direct_url: str | None` 字段。MissavParser.parse() 填充直链，BilibiliParser.parse() 保持 None。`_start_download()` 判断：若 `direct_url` 非空则用直链，否则构造 bilibili URL。

**历史记录修改** (`download_history.py`):
```python
# 添加 source_site 参数
def add_entry(self, title, bv_id, state, size="", source_site="bilibili"):
    icon = "✅" if state == "finished" else "❌"
    text = f"{icon} [{source_site}] {title} ({bv_id})"
```

**Patterns to follow:**
- `src/main_window.py` 现有 `_start_download()` 流程

**Test scenarios:**
- Happy path: missav 下载完成后，历史记录显示 `[missav]` 前缀
- Happy path: bilibili 下载完成后，历史记录显示 `[bilibili]` 前缀（向后兼容）
- Error path: missav 解析失败时，`QMessageBox` 显示具体错误

**Verification:**
- 手动启动 app，分别测试 bilibili 和 missav URL，检查历史记录标记正确

---

## System-Wide Impact

- **Downloader**: 无需修改（接受任意 URL 直链下载）
- **DownloadProgress / VideoInfoPanel**: 无需修改（接收 VideoInfo 显示）
- **Config**: 无需修改（session 路径独立于 config）
- **Entry point** (`main.py`): 无需修改

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Cloudflare 升级导致验证逻辑失效 | Session 失效后 headed 重新验证；对用户透明 |
| Headless Chromium cookie 复用失败 | 检查 `cf_clearance` 过期时间，过期则 re-verify |
| missav.live 页面结构变更（无 video 元素） | try/except 捕获，抛出 `VideoParseError` 带 URL |
| Playwright Windows 路径问题 | Playwright 自动管理浏览器安装，用 `p.chromium.executable_path` |

## Documentation / Operational Notes

- 需在 `requirements.txt` 添加 `playwright>=1.40`（已添加）
- 安装后需运行 `playwright install chromium` 下载浏览器二进制（首次安装时需要）
- 用户首次使用 missav 时需手动完成一次 Cloudflare 验证（已记录在需求文档）
