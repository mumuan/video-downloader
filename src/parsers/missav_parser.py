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

                # 优先从拦截的请求中获取 m3u8
                hls_url = captured_m3u8[0] if captured_m3u8 else None

                # 若未捕获到，尝试从 video 元素属性获取 media ID 并构造 URL
                if not hls_url:
                    try:
                        media_id = page.eval_on_selector("video", "v => v.id")
                        if media_id:
                            hls_url = f"https://edge-hls.saawsedge.com/hls/{media_id}/master/{media_id}_240p.m3u8"
                    except Exception:
                        pass

                # 提取视频直链（HLS 或 blob）
                try:
                    video_url = page.eval_on_selector(
                        "video", "v => v.src"
                    )
                except Exception:
                    video_url = ""

                # 如果拿到的是 blob URL，优先用拦截到的 m3u8 直链
                if video_url.startswith("blob:") and hls_url:
                    video_url = hls_url

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
