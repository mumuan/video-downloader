---
date: 2026-04-05
topic: missav-live-support
---

# missav.live 下载支持

## Problem Frame

用户希望在同一工具中支持 Bilibili 和 missav.live 两个视频网站的下载。Bilibili 已通过 yt-dlp 原生支持；missav.live 有 Cloudflare 反爬保护，yt-dlp 无法直接提取，需引入 Playwright 绕过。

调研发现：missav.live 有 Cloudflare JS 验证质询，headless 浏览器无法自动通过。第一次访问需要用户在**可见浏览器**中手动完成一次验证，之后 session cookies 复用可实现无感下载。

## Requirements

**站点识别与路由**
- R1. URL 输入框接受 `missav.live/*` 链接，自动识别站点类型
- R2. `VideoParser` 扩展为工厂模式，根据 URL 路由到对应站点解析器
- R3. 解析阶段失败（如 Cloudflare 拦截）显示明确错误信息

**missav.live 解析（Playwright + Cloudflare 处理）**
- R4. 首次使用：启动**可见浏览器**（headed mode）让用户手动通过 Cloudflare 验证，复用 session 后续自动跳过
- R5. 提取页面 `<video>` 标签的 `src` 属性作为视频直链
- R6. 从页面提取标题（`<title>`）、封面（`og:image` meta）
- R7. 解析器返回结构与 Bilibili 解析器一致的 `VideoInfo` 对象
- R8. session 超时或失效时提示用户重新验证

**下载流程**
- R9. missav 视频下载复用现有 `Downloader`（yt-dlp），直接传入视频直链作为 URL
- R10. 文件命名格式：`{title}_missav_{video_id}.mp4`

**UI 集成**
- R11. 视频信息面板在 missav 模式下显示标题、封面
- R12. 下载历史记录正确标记来源站点（bilibili / missav）

**错误处理**
- R13. Cloudflare 验证超时提示用户并允许重试
- R14. 视频直链获取失败（如页面结构变更）给出有意义的错误提示

## Success Criteria
- 用户首次粘贴 missav.live 链接时弹出可见浏览器完成一次 Cloudflare 验证
- 后续访问同一链接无需再次验证（session 复用）
- 下载的视频可正常播放（画面+声音）
- Bilibili 现有功能不受影响

## Scope Boundaries
- 不支持播放列表/批量下载（单视频下载）
- 不支持需要登录的付费/私有视频
- 不实现 yt-dlp 通用 extractor fallback——missav 用专属解析路径

## Key Decisions
- **Headed + session 复用 vs 完全自动化**: Cloudflare 验证在 headless 下无法自动通过，采用 headed 模式首次手动验证 + session cookies 复用的方案
- **复用 Downloader vs 新建**: 复用，`Downloader.download(url)` 支持任意直链下载
- **VideoInfo 字段**: missav 无 BV 号，用 URL slug（如 `mfcw-008`）作为 `bv_id` 占位，保持 dataclass 结构兼容

## Dependencies / Assumptions
- D1. `playwright` 包已安装（`pip install playwright && playwright install chromium`）
- D2. missav.live 视频以直链 MP4 嵌入（`<video src="...">`），非 m3u8/hls 流
- D3. 无需登录即可访问和下载公开视频
- D4. Playwright session cookies 在合理期限内（如 7 天）可复用跳过 Cloudflare

## Outstanding Questions

### Resolve Before Planning
- (无 blocking 问题，以上问题均可通过技术调研在 planning 阶段解决)

### Deferred to Planning
- [技术] Playwright session 生命周期管理：首次验证后 cookies 如何持久化存储（文件路径、过期策略）
- [技术] Chromium 安装和路径处理（Windows 环境兼容性）
- [技术] MissavParser 与 BilibiliVideoParser 的接口对齐（是否需要抽象基类）
- [技术] 首次验证时 UI 交互流程（弹出窗口提示用户等待验证完成）
