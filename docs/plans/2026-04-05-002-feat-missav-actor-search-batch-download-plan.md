---
title: "feat: missav actor search and batch download"
type: feat
status: active
date: 2026-04-05
origin: docs/brainstorms/2026-04-05-missav-actor-search-batch-download-requirements.md
---

# missav 演员搜索批量下载

## Overview

在 xhub 中新增演员搜索 Tab，支持按演员名搜索 missav.live 所有视频，选择性批量下载。MainWindow 从单窗口重构为 QTabWidget（两个 Tab 并列），新建 DownloadQueue 支持并发下载。

## Problem Frame

用户已可下载单个 missav 视频。新功能需要：输入演员名搜索 → 展示分页视频列表 → 选择性批量下载。核心挑战：搜索页 Cloudflare 处理、分页 UI、跨页选择持久化、两阶段下载（先提直链再并发下）、MainWindow 重构为 Tab。

## Requirements Trace

### UI / Layout

- R1. MainWindow 重构为 QTabWidget，新增"演员搜索" Tab
- R2. 搜索输入框 + 按钮，访问 `https://missav.live/search/{actor_name}`
- R3. 分页展示搜索结果（每页20条）
- R4-R5. 视频列表：复选框、封面缩略图、标题、时长、全选/取消全选
- R7. 显示当前页已选中数量
- R8. "下载选中"按钮；无可选视频时按钮禁用
- R14. 批量下载总体进度条（X/Y）
- R15. 单视频子进度（百分比）

### Parser / Search

- R2a. MissavParser 新增 `search_parse(actor_name, page)` 解析搜索结果页
- R12. 复用 Downloader.download_direct() 和 MissavParser session 管理

### Download Behavior

- R6. 已下载视频自动勾选并标记"跳过"，用户可手动取消强制重新下载（右键菜单或独立按钮，非禁用复选框）
- R7a. 跨页选择全局持久化：`_checked_ids` 在会话内持久化（内存 Set，关闭应用清空）
- R9. 可配置同时下载数（默认2）
- R10. 下载失败自动跳下一条
- R11. 完成后汇总成功/失败信息
- R13. 文件命名格式 `{title}_missav_{video_id}.mp4`

### Persistence / History

- R16. 下载历史写入 DownloadHistoryWidget；missav 批量下载标记 source_site="missav"

### Implementation Priority Tiers

- **P0**: Unit 2 (search_parse — 核心新能力)
- **P1**: Units 1, 3, 4 (数据模型、下载队列、UI Tab)
- **P2**: Unit 5 (MainWindow 集成，可较晚交付)

## Scope Boundaries

- 不支持专辑/系列筛选（仅按演员）
- 不支持下载后自动分类整理
- 不支持多演员同时搜索
- 不支持暂停/继续

## Key Technical Decisions

- **两阶段处理**：先批量提取选中视频的直链（访问详情页），再启动 DownloadQueue 下载。用户体验更流畅。
- **已下载判断**：基于 DownloadHistoryWidget 历史记录（source_site="missav" + state="finished"）查询 video_id Set，O(1) 判断。
- **SearchResult dataclass**：搜索结果元数据（标题、封面、时长、video_id）独立于 VideoInfo，职责清晰。直链在两阶段处理后填充。
- **DownloadQueue 新类**：管理下载队列和 N 个并发 Worker，不修改现有 Downloader。
- **Config 扩展**：新增 `concurrent_downloads` 字段，默认2，持久化到 config.json。
- **DownloadHistoryWidget 扩展**：add_entry() 增加可选 `video_id` 参数，向后兼容。

## Context & Research

### Relevant Code and Patterns

| File | Role | Key pattern |
|------|------|-------------|
| `src/downloader.py` | Downloader (QObject) | pyqtSignal 模式复用 |
| `src/parsers/missav_parser.py` | MissavParser | PlaywrightSessionManager 复用 |
| `src/parsers/session_manager.py` | PlaywrightSessionManager | stealth hook + cookie 持久化 |
| `src/main_window.py` | MainWindow | QThread worker 模式 |
| `src/widgets/download_history.py` | DownloadHistoryWidget | add_entry() 扩展 |
| `src/config.py` | Config | JSON 持久化扩展 |

### Institutional Learnings

- `docs/solutions/runtime-errors/yt-dlp-float-duration-2026-04-05.md`: yt-dlp duration 返回 float，需 cast int
- Playwright stealth: `Stealth().hook_playwright_context(p)` 须在 `browser.launch()` 前调用
- Cookie 持久化路径: `%APPDATA%/missav-downloader/cookies/cloudflare_state.json`
- `cf_clearance` 有效期 >1 小时才认为 session 有效

### External References

- PyQt6 QTabWidget: `QTabWidget.addTab()` 添加 Tab
- Playwright sync_api: `page.goto()`, `page.wait_for_selector()`, `page.evaluate()`

## High-Level Technical Design

> *Directional guidance for review, not implementation specification.*

```
User Input: actor_name
     │
     ▼
┌─────────────────────────┐
│ ActorSearchTab._on_search_clicked() │
│  actor_name = self.search_input.text().strip()          │
│  if not actor_name: return                             │
│  self._set_state("searching")                          │
│  MissavParser.search_parse(actor_name, page=1)          │
└──────────────┬──────────────────┘
               │ returns List[SearchResult]
               ▼
┌─────────────────────────┐
│ _display_results(results, total_pages) │
│  self.search_results = results           │
│  self.total_pages = total_pages           │
│  self._restore_checkstates()  # R7a     │
└──────────────────────────────────────────┘
               │
               ▼  User checks items, clicks "下载选中"
┌──────────────────────────────────────────┐
│ _on_download_selected_clicked()            │
│  selected = [r for r in self.search_results│
│              if r.video_id in self._checked_set] │
│  ExtractPhase: for each SearchResult:      │
│    MissavParser.parse(detail_url)          │
│    → VideoInfo with direct_url             │
│  ExtractPhase 错误处理: 单个失败不阻塞其余   │
│    → 失败项记录到 failed_extracts          │
│    → DownloadQueue 仅接收成功项            │
│  DownloadQueue.start(video_infos)           │
└──────────────────────────────────────────┘
```

### DownloadQueue Architecture

```
DownloadQueue (QObject)
  ├─ signals: batch_progress(int done, int total), item_progress(str video_id, float percent),
  │           item_finished(str video_id), item_failed(str video_id, str error),
  │           batch_finished(List[success], List[failed])
  ├─ _workers: List[DownloaderWorker]   # max = concurrent_downloads
  ├─ _pending: List[VideoInfo]           # to be downloaded
  ├─ start(List[VideoInfo])
  └─ _on_item_done(video_id)

DownloaderWorker (QThread)
  ├─ _downloader: Downloader
  ├─ _video_info: VideoInfo
  ├─ run() → _downloader.download_direct(direct_url, output_filename)
  └─ signals: progress, finished, error
```

## Implementation Units

- [ ] **Unit 1: SearchResult dataclass + Config concurrent_downloads**

**Goal:** 建立搜索结果数据模型，扩展 Config 支持并发下载数持久化

**Requirements:** R9, R13 (数据模型部分)

**Dependencies:** None

**Files:**
- Create: `src/search_result.py`
- Modify: `src/config.py`
- Test: `tests/test_search_result.py`

**Approach:**
- `SearchResult` dataclass: `video_id`, `title`, `thumbnail`, `duration`, `detail_url`（**Deferred**: detail_url URL 模式待验证——如 `https://missav.live/{video_id}` 或 `/video/{video_id}`，需访问页面确认）
- `Config` 新增 `concurrent_downloads: int = 2`，序列化到 config.json

**Patterns to follow:** `src/video_info.py` 的 dataclass 模式，`src/config.py` 的 save() 自动持久化模式

**Test scenarios:**
- Happy path: SearchResult 实例化，所有字段正确
- Edge case: duration 为 float（来自 yt-dlp）时 cast to int
- Config: concurrent_downloads 默认值 2，序列化/反序列化正确

**Verification:** `SearchResult(video_id="abc", title="test", thumbnail="", duration=120, detail_url="https://missav.live/abc")` 可正常实例化

---

- [ ] **Unit 2: MissavParser.search_parse() 扩展**

**Goal:** 新增演员搜索解析方法，返回 `List[SearchResult]` 和总页数

**Requirements:** R2, R3, R2a, R12

**Dependencies:** None — `search_parse()` 独立于 SearchResult dataclass，可立即实现

**Files:**
- Modify: `src/parsers/missav_parser.py`
- Test: `tests/test_missav_parser.py`（扩展现有测试）

**Approach:**
- `search_parse(actor_name: str, page: int) -> Tuple[List[SearchResult], int]`
- URL: `https://missav.live/search/{actor_name}?page={page}` 或 `https://missav.live/search/{actor_name}/{page}`
- HTML 结构解析（具体 selector 需实现时检查页面）：`<a class="video-item">` 或类似结构
- 返回视频标题、封面、时长、video_id（从 URL 提取）
- 总页数从分页导航区提取（如 `.pagination`）
- 复用 `CurlSessionManager` 优先，失败则 `PlaywrightSessionManager`

**Deferred:** HTML selector 具体结构 —— 需访问 missav.live 验证（标注为 "Needs research"）

**Patterns to follow:** 现有 `MissavParser._parse_with_curl()` 的 HTML regex 解析模式，`session_manager.py` 的 cookie 复用

**Test scenarios:**
- Edge case: 演员名含特殊字符（空格 URL encode）
- Edge case: 搜索结果为空（返回空列表 + total_pages=0）
- Error path: curl 返回 Cloudflare block，fallback 到 playwright
- Error path: curl 和 playwright 均失败，抛出 `VideoParseError`

**Verification:** `MissavParser().search_parse("三上悠亚", 1)` 返回非空列表和总页数

---

- [ ] **Unit 3: DownloadQueue 并发下载管理器**

**Goal:** 支持 N 个视频同时下载，聚合进度信号

**Requirements:** R9, R10, R11, R14, R15

**Dependencies:** Unit 1

**Files:**
- Create: `src/download_queue.py`
- Test: `tests/test_download_queue.py`

**Approach:**
- `DownloadQueue(QObject)` 持有 N 个 `DownloaderWorker(QThread)`
- `start(List[VideoInfo])` 填充 `_pending`，立即启动 up to `concurrent_downloads` 个 Worker
- 每个 Worker 完成后 emit `item_finished`/`item_failed`，Queue 取下一个 `_pending` 启动
- 信号: `batch_progress(done, total)`, `item_progress(video_id, percent)`, `item_finished(video_id)`, `item_failed(video_id, error)`, `batch_finished(success_ids, failed_ids)`
- 失败记录到 failed_ids，不阻塞队列

**Technical design:**
```
class DownloadQueue(QObject):
    batch_progress = pyqtSignal(int, int)    # done, total
    item_progress = pyqtSignal(str, float)  # video_id, percent
    item_finished = pyqtSignal(str)
    item_failed = pyqtSignal(str, str)       # video_id, error
    batch_finished = pyqtSignal(list, list) # success_ids, failed_ids

    def start(self, video_infos: List[VideoInfo]): ...
    def _on_worker_done(self, video_id: str, success: bool, error: str = ""): ...

class DownloaderWorker(QThread):
    finished = pyqtSignal(str, bool, str)  # video_id, success, error
    progress = pyqtSignal(str, float)        # video_id, percent

    def __init__(self, video_info, output_dir, cookies): ...
    def run(self): ...
```

**Patterns to follow:** `src/main_window.py` 中 `DownloadThread(QThread)` 模式，`Downloader` 的 pyqtSignal 模式

**Test scenarios:**
- Happy path: 3个视频，并发数2，验证先启动2个，第1个完成后立即启动第3个
- Edge case: 所有视频下载成功，batch_finished 收到3个 success，0个 failed
- Error path: 1个失败，队列继续处理剩余2个，最终 batch_finished 包含正确的 success_ids 和 failed_ids
- Edge case: start() 被调用时已有 pending 任务（应该忽略新调用或排队）

**Verification:** DownloadQueue 处理混合 success/failure 视频列表，最终 batch_finished 正确汇总

---

- [ ] **Unit 4: ActorSearchTab UI 组件**

**Goal:** 完整的演员搜索 Tab 组件（搜索框 → 列表 → 翻页 → 批量下载 → 进度）

**Requirements:** R1, R2-R7a, R8-R11, R14-R15

**Dependencies:** Unit 1, Unit 2, Unit 3

**Files:**
- Create: `src/widgets/actor_search_tab.py`
- Test: `tests/test_actor_search_tab.py`

**Approach:**
- `ActorSearchTab(QWidget)` 组合以下子组件：
  - 搜索行：`QLineEdit` + `QPushButton("搜索")`
  - 结果列表：`QListWidget` 或 `QTableWidget`，每行：复选框、QLabel(封面)、QLabel(标题)、QLabel(时长)
  - 翻页区：`QPushButton("上一页")` `QLabel("1 / 10")` `QPushButton("下一页")`
  - 下载控制行：`QSpinBox`（1-5，并发数）+ `QPushButton("下载选中")` + `QLabel`（已选N个）
  - 进度区：`QProgressBar`（总体 X/Y）+ `QLabel`（当前项百分比 + 文件名）
- 状态管理：
  - `_search_state: Literal["idle", "searching", "error"]`
  - `_download_state: Literal["idle", "extracting", "downloading", "finished"]`
  - `_checked_ids: Set[str]` — 全局已选 video_id 集合（跨页持久化，R7a）
  - `_page_results: Dict[int, List[SearchResult]]]` — 每页缓存（避免切页重新请求）
- 搜索 → loading 状态禁用输入 → 失败弹窗提示 → 空结果显示提示
- 全选：遍历当页所有项设置复选框；取消全选：清除当页
- "跳过"视觉标识：视频项背景灰色 + 左侧标签"已下载"；复选框保持勾选。取消跳过强制重新下载：通过右键菜单"强制重新下载"实现（非禁用复选框）

**UI 组件细节:**
- 并发数设置：`QSpinBox` 范围 1-5，默认值 `Config.concurrent_downloads`
- 进度条：`QProgressBar` 设置 `minimum=0 maximum=100`，百分比格式
- 子进度：QLabel 显示 `"正在下载: {title} ({percent}%)"`
- 下载完成汇总：`QMessageBox.information` 显示"成功 N 个，失败 M 个"列表
- 无障碍：Tab 键可聚焦所有交互元素（搜索框、按钮、复选框、翻页）；回车键触发搜索；Ctrl+A 全选
- 窗口缩放：QTableWidget 列宽随窗口拉伸，封面缩略图最小 80×60px
- 翻页按钮状态：current_page==1 时"上一页"禁用；current_page==total_pages 时"下一页"禁用；搜索/加载中全禁用
- 下载按钮状态：`_download_state != "idle"` 时"下载选中"禁用；提取阶段显示"正在提取直链..."
- 关闭应用确认：下载进行中关闭应用时弹出确认对话框"下载进行中，确定退出？"

**Patterns to follow:** `src/widgets/download_progress.py` 的进度更新模式；`src/widgets/download_history.py` 的 add_entry 模式

**Test scenarios:**
- Happy path: 输入演员名 → 显示搜索结果 → 全选 → 翻页 → 下载选中 → 进度更新 → 汇总
- Edge case: 搜索结果为空 → 显示"未找到该演员的相关视频"
- Edge case: 搜索中网络错误 → 显示错误 + 重试按钮
- Edge case: 切换页后返回，已选状态恢复
- Error path: 下载进行中切到其他 Tab，下载继续，完成后写入历史
- Edge case: 无选中项时"下载选中"按钮禁用

**Verification:** 完整用户流程：搜索 → 全选 → 翻页 → 返回 → 下载 → 汇总

---

- [ ] **Unit 5: MainWindow QTabWidget 重构**

**Goal:** MainWindow 从单垂直布局改为 QTabWidget，现有下载 UI 为 Tab 1，新增 ActorSearchTab 为 Tab 2

**Requirements:** R1, R16

**Dependencies:** Unit 4

**Files:**
- Modify: `src/main_window.py`
- Modify: `src/widgets/download_history.py`（add_entry 扩展）

**Approach:**
- `MainWindow` 用 `QTabWidget` 替代 `QVBoxLayout(central)`
- Tab 1 "视频下载"：将现有 URL 输入框 + VideoInfoPanel + DownloadProgress + History + 输出目录 放入 `QWidget` 后 `addTab()`
- Tab 2 "演员搜索"：嵌入 `ActorSearchTab()`
- 保持所有现有功能不变（Bilibili 下载不受影响）
- `DownloadHistoryWidget.add_entry()` 增加可选 `video_id` 参数（向后兼容，传 None 则用 bv_id）

**Patterns to follow:** 现有 MainWindow 的 widget 组合模式

**Test scenarios:**
- Happy path: 启动应用，两个 Tab 可切换，内容各自正确
- Edge case: 切换 Tab 不影响另一 Tab 的下载/搜索状态
- 下载历史: Bilibili 单视频下载后，history 显示 "[bilibili]" 标签；missav 批量下载后显示 "[missav]" 标签

**Verification:** 现有 Bilibili URL 下载流程不受影响，两个 Tab 均可正常操作

---

## System-Wide Impact

- **Interaction graph:** MainWindow 新增 Tab；DownloadHistoryWidget.add_entry() 接收新参数
- **Error propagation:** ActorSearchTab 中 MissavParser 异常 → Tab 内显示错误，不影响 Bilibili Tab
- **State lifecycle risks:** DownloadQueue Worker 完成信号在 QThread 退出时 emit；需确保 ActorSearchTab 在窗口关闭时正确清理 Worker
- **API surface parity:** Bilibili 视频下载路径（URL → VideoParser → Downloader → DownloadHistory）完全不变
- **Integration coverage:** ActorSearchTab.start_download() 调用 MissavParser.parse() 获取直链，再传入 DownloadQueue

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| missav 搜索页 HTML 结构变更 | D1 标注为 assumption，实现时发现结构变化需更新 selector |
| Cloudflare 搜索页拦截 | 复用 PlaywrightSessionManager stealth，与详情页同策略 |
| 并发下载 cookie 竞争 | 每个 Worker 独立创建 cookie file（`tempfile.mkstemp`），主进程管理生命周期 |
| 大演员视频量（数百个） | 翻页缓存 `_page_results`；DownloadQueue 队列内存线性于选中数 |

## Open Questions

### Resolved During Planning

- **两阶段处理**：先批量提取直链（访问详情页获取 direct_url），再启动 DownloadQueue 下载
- **已下载判断**：基于 DownloadHistoryWidget 历史（source_site="missav" + state="finished"）的 video_id Set
- **SearchResult dataclass**：独立于 VideoInfo，只包含搜索页元数据
- **add_entry 扩展**：增加可选 video_id 参数，向后兼容

### Deferred to Implementation

- **HTML selector 结构**：搜索结果页的具体 CSS selector（title、thumbnail、duration、video_id、pagination），需访问页面验证
- **分页 URL 格式**：`?page=N` 还是 `/N` 路径格式，需访问页面验证
- **详情页直链提取**：复用现有 `MissavParser.parse()` 逻辑，已验证可行
- **session 复用策略**：搜索页和详情页是否共用同一个 Playwright session（cookie 共享）—— PlaywrightSessionManager 的 storage_state 可跨页面复用

## Documentation / Operational Notes

- 实现时需验证 missav.live 搜索页实际 HTML 结构，selector 可能需要随网站更新调整
- 并发下载数过高（5）可能导致 Cloudflare 请求频率限制，需提示用户
