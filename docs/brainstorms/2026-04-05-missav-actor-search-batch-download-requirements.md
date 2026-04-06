---
date: 2026-04-05
topic: missav-actor-search-batch-download
---

# missav 演员搜索批量下载

## Problem Frame

用户已可以在 xhub 中下载单个 missav.live 视频。现在需要新增功能：输入演员名字，搜索该演员在 missav 上的所有视频，选择性批量下载。

## Requirements

**新建 Tab 页面**

- R1. MainWindow 重构为 QTabWidget，新增 "演员搜索" Tab（与现有单视频下载 Tab 并列）
- R2. Tab 内包含搜索输入框和搜索按钮，输入演员名后访问 `https://missav.live/search/{actor_name}`
- R3. 搜索结果分页展示，每页显示视频列表（封面、标题、时长），支持翻页
- R2a. MissavParser 扩展 `search_parse(actor_name, page)` 方法，解析搜索结果页的 HTML 结构（视频标题、封面 URL、时长、video_id）及分页结构

**视频列表展示与选择**

- R4. 搜索结果列表中每项显示：复选框、封面缩略图、标题、时长
- R5. 列表顶部提供 "全选" / "取消全选" 按钮
- R6. 已下载过的视频（根据 video_id 判断）自动勾选并标记为"跳过"状态（显示状态标识），用户可手动取消勾选以强制重新下载
- R7. 显示当前页已选中数量
- R7a. 跨页选择持久化：用户切换页码后，已勾选 video_id 集合全局记忆；切换回某页时恢复该页勾选状态

**批量下载**

- R8. Tab 内提供 "下载选中" 按钮，点击后开始下载已勾选且未跳过的视频
- R9. 可配置同时下载数（默认 2），设置项放在 Tab 内
- R10. 下载失败自动跳过，继续下载下一队列中的视频
- R11. 下载完成后显示汇总信息：成功 N 个，失败 N 个（列出失败项）

**下载流程复用**

- R12. 复用现有 `Downloader.download_direct()` 方法和 `MissavParser` 的 session 管理
- R13. 文件命名格式保持现有：`{title}_missav_{video_id}.mp4`

**进度展示**

- R14. Tab 内显示批量下载总体进度条（X/Y 已完成）
- R15. 当前下载项显示子进度（单个视频的百分比）

**下载历史**

- R16. 批量下载的条目同样写入 `DownloadHistoryWidget`，source_site 标记为 "missav"

## Success Criteria

- 输入演员名 "三上悠亚" 能正确搜索并展示该演员在 missav 上的所有视频
- 用户可通过翻页浏览全部视频列表
- 用户勾选视频后点击下载，已下载的 video_id 自动跳过
- 下载失败不影响其他视频，最终显示汇总报告
- Bilibili 单视频下载功能不受影响

## Scope Boundaries

- 不实现按专辑/系列筛选（仅按演员搜索）
- 不实现下载完成后的自动重命名或分类整理
- 不支持同时搜索多个演员
- 不支持下载过程中暂停/继续（失败直接跳下一条）

## Key Decisions

- **MainWindow 重构**：接受较大改动，将 MainWindow 从单垂直布局重构为 QTabWidget，两个 Tab 并列
- **跳过状态可覆盖**：用户可手动取消已下载视频的跳过勾选，强制重新下载
- **跨页选择持久化**：已勾选 video_id 在内存中全局记忆，切换页后恢复勾选状态

- **搜索结果分页**：每页固定数量（如 20 条），由 missav 搜索页 pagination 控制
- **去重策略**：基于 video_id 判断，跳过已下载文件（不弹窗询问）
- **并发下载**：可配置 1-5 个同时下载，超出需用户确认
- **失败处理**：失败 video_id 记录到汇总报告，不阻塞后续下载

## Dependencies / Assumptions

- D1. missav.live 搜索页结构稳定（每个视频有可提取的标题、封面、时长、视频 ID）
- D2. missav 搜索结果页面支持分页（URL 格式如 `?page=2`）
- D3. `playwright` session manager 可复用（演员搜索页也受 Cloudflare 保护）
- D4. 下载直链从视频详情页提取，不从搜索列表页直接获取
