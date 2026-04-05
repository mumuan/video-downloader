from urllib.parse import urlparse

import playwright.sync_api

from src.parsers.session_manager import SessionManager, VideoParseError
from src.video_info import VideoInfo


class MissavParser:
    def __init__(self):
        self._session = SessionManager()

    def _extract_video_id(self, raw_url: str) -> str:
        """从 URL 提取视频 slug（完整路径段）"""
        parsed = urlparse(raw_url)
        path = parsed.path.strip("/")
        # 取最后一个路径段作为 video_id
        segments = [s for s in path.split("/") if s]
        if not segments:
            raise VideoParseError("无法从 URL 中提取视频 ID")
        return segments[-1]

    def _make_filename(self, title: str, video_id: str) -> str:
        """生成安全的输出文件名"""
        safe_title = "".join(
            c for c in title if c not in '<>:"/\\|?*'
        )
        return f"{safe_title}_missav_{video_id}.mp4"

    def parse(self, raw_url: str) -> VideoInfo:
        video_id = self._extract_video_id(raw_url)

        with playwright.sync_api.sync_playwright() as p:
            context, browser = self._session.get_verified_context(p, raw_url)
            try:
                page = context.new_page()

                # 先注册请求拦截，再导航，以便捕获 m3u8 请求
                captured_m3u8: list[str] = []

                def on_request(request):
                    url = request.url
                    if ".m3u8" in url and "master" in url:
                        captured_m3u8.append(url)

                page.on("request", on_request)

                page.goto(raw_url)

                # 等待 video 元素出现
                try:
                    page.wait_for_selector("video", timeout=30000)
                except Exception:
                    raise VideoParseError(
                        "无法获取视频，请检查链接是否有效"
                    )

                # 优先从 page 上下文中提取 window.source1280 / window.source842
                # 这是 missav 提供的完整 VOD playlist（surrit.com CDN）
                # 优先用 1280p，若无则降级到 480p
                video_url = ""
                for source_expr in [
                    "window.source1280 || window.source842 || null",
                    "window.source842 || null",
                ]:
                    try:
                        candidate = page.evaluate(f"() => {source_expr}")
                        if candidate:
                            video_url = candidate
                            break
                    except Exception:
                        pass

                # 若 page 上下文中没有，尝试从拦截的 master m3u8 请求获取
                if not video_url:
                    hls_url = captured_m3u8[0] if captured_m3u8 else None
                    if not hls_url:
                        # 从 video 元素属性获取 media ID 并构造滚动预览 URL
                        try:
                            media_id = page.eval_on_selector("video", "v => v.id")
                            if media_id:
                                hls_url = f"https://edge-hls.saawsedge.com/hls/{media_id}/master/{media_id}_240p.m3u8"
                        except Exception:
                            pass
                    if hls_url:
                        video_url = hls_url

                # 若拿到的是 blob URL 且还没有 video_url，尝试拦截的 m3u8
                if not video_url:
                    try:
                        blob_url = page.eval_on_selector("video", "v => v.src")
                        if blob_url.startswith("blob:") and captured_m3u8:
                            video_url = captured_m3u8[0]
                    except Exception:
                        pass

                # 提取标题
                title = page.title()

                # 提取封面
                try:
                    thumbnail = page.eval_on_selector(
                        'meta[property="og:image"]', "m => m.content"
                    )
                except Exception:
                    thumbnail = ""
            finally:
                browser.close()

        if not video_url:
            raise VideoParseError("无法获取视频直链，请检查链接是否有效")

        return VideoInfo(
            bv_id=video_id,
            title=title or "未知标题",
            duration=0,
            thumbnail=thumbnail or "",
            output_filename=self._make_filename(title or "未知标题", video_id),
            source_site="missav",
            direct_url=video_url,
        )
