import re
import importlib
from urllib.parse import urlparse, quote

from src.i18n import _
from src.parsers.session_manager import (
    CurlSessionManager,
    PlaywrightSessionManager,
    VideoParseError,
)
from src.search_result import SearchResult
from src.video_info import VideoInfo


class MissavParser:
    def __init__(self):
        self._curl_session = CurlSessionManager()
        self._playwright_session = PlaywrightSessionManager()

    def _extract_video_id(self, raw_url: str) -> str:
        parsed = urlparse(raw_url)
        path = parsed.path.strip("/")
        segments = [s for s in path.split("/") if s]
        if not segments:
            raise VideoParseError(_("Unable to extract video ID from URL"))
        return segments[-1]

    def _make_filename(self, title: str, video_id: str) -> str:
        safe_title = "".join(c for c in title if c not in '<>:"/\\|?*')
        return f"{safe_title}_missav_{video_id}.mp4"

    def _extract_video_url(self, html: str) -> str:
        for pattern in [
            r'window\.source1280\s*=\s*["\']([^"\']+)["\']',
            r'window\.source842\s*=\s*["\']([^"\']+)["\']',
            r'source1280\s*:\s*["\']([^"\']+)["\']',
            r'source842\s*:\s*["\']([^"\']+)["\']',
        ]:
            match = re.search(pattern, html)
            if match:
                url = match.group(1)
                if url.startswith("http"):
                    return url

        m3u8_match = re.search(r'["\']([^"\']*master[^"\']*\.m3u8[^"\']*)["\']', html)
        if m3u8_match:
            return m3u8_match.group(1)

        media_id_match = re.search(r'data-media-id=["\']([^"\']+)["\']', html)
        if media_id_match:
            media_id = media_id_match.group(1)
            return f"https://edge-hls.saawsedge.com/hls/{media_id}/master/{media_id}_240p.m3u8"

        video_src = re.search(r'<video[^>]+src=["\']([^"\']+)["\']', html)
        if video_src:
            return video_src.group(1)

        return ""

    def _extract_title(self, html: str) -> str:
        match = re.search(r'<title>([^<]+)</title>', html)
        return match.group(1).strip() if match else _("Unknown title")

    def _extract_thumbnail(self, html: str) -> str:
        match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html
        )
        if match:
            return match.group(1)
        match = re.search(
            r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html
        )
        return match.group(1) if match else ""

    def _parse_with_curl(self, raw_url: str) -> VideoInfo | None:
        """使用 curl_cffi 解析。返回 None 表示 curl_cffi 方案失败。"""
        video_id = self._extract_video_id(raw_url)
        session = self._curl_session.get_session(raw_url)
        if session is None:
            return None

        resp = session.get(raw_url)
        if resp.status_code != 200:
            return None

        # Use content and decode manually to handle encoding properly
        raw_content = resp.content
        # Force Shift-JIS for this site - it always uses Shift-JIS even if meta tag says UTF-8
        encoding = 'shift_jis'
        try:
            html = raw_content.decode(encoding, errors='replace')
        except (LookupError, UnicodeDecodeError):
            html = raw_content.decode('utf-8', errors='replace')
        if "cloudflare" in html.lower() or "just a moment" in html.lower():
            return None

        video_url = self._extract_video_url(html)
        title = self._extract_title(html)
        thumbnail = self._extract_thumbnail(html)

        if not video_url:
            return None

        return VideoInfo(
            bv_id=video_id,
            title=title or _("Unknown title"),
            duration=0,
            thumbnail=thumbnail or "",
            output_filename=self._make_filename(title or _("Unknown title"), video_id),
            source_site="missav",
            direct_url=video_url,
        )

    def _parse_with_playwright(self, raw_url: str) -> VideoInfo:
        """使用系统 Playwright 解析（仅当 curl_cffi 失败时调用）"""
        if not self._playwright_session.is_available():
            raise VideoParseError(
                "Cloudflare 验证失败，且系统未安装 Playwright 浏览器。"
                "请在命令行运行: pip install playwright && playwright install chromium"
            )

        video_id = self._extract_video_id(raw_url)
        context, browser, p = self._playwright_session.get_browser(raw_url)

        try:
            page = context.new_page()

            captured_m3u8: list[str] = []

            def on_request(request):
                url = request.url
                if ".m3u8" in url and "master" in url:
                    captured_m3u8.append(url)

            page.on("request", on_request)
            # Use domcontentloaded for Cloudflare pages (load event may never fire)
            page.goto(raw_url, wait_until="domcontentloaded", timeout=60000)

            # Wait for page to load (not for visible video since videos may be hidden)
            try:
                page.wait_for_load_state("networkidle", timeout=45000)
            except Exception:
                page.wait_for_timeout(5000)  # fallback to just waiting

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

            if not video_url:
                hls_url = captured_m3u8[0] if captured_m3u8 else None
                if not hls_url:
                    try:
                        media_id = page.eval_on_selector("video", "v => v.id")
                        if media_id:
                            hls_url = f"https://edge-hls.saawsedge.com/hls/{media_id}/master/{media_id}_240p.m3u8"
                    except Exception:
                        pass
                if hls_url:
                    video_url = hls_url

            if not video_url:
                try:
                    blob_url = page.eval_on_selector("video", "v => v.src")
                    if blob_url.startswith("blob:") and captured_m3u8:
                        video_url = captured_m3u8[0]
                except Exception:
                    pass

            title = page.title()

            try:
                thumbnail = page.eval_on_selector(
                    'meta[property="og:image"]', "m => m.content"
                )
            except Exception:
                thumbnail = ""

        finally:
            browser.close()
            p.stop()

        if not video_url:
            raise VideoParseError(_("Unable to get video direct link, please check if the link is valid"))

        return VideoInfo(
            bv_id=video_id,
            title=title or _("Unknown title"),
            duration=0,
            thumbnail=thumbnail or "",
            output_filename=self._make_filename(title or _("Unknown title"), video_id),
            source_site="missav",
            direct_url=video_url,
        )

    def parse(self, raw_url: str) -> VideoInfo:
        # 先尝试 curl_cffi（轻量，无浏览器依赖）
        result = self._parse_with_curl(raw_url)
        if result is not None:
            return result

        # curl_cffi 失败，回退到 Playwright（如果系统已安装）
        return self._parse_with_playwright(raw_url)

    def search_parse(self, actor_name: str, page: int = 1) -> tuple[list[SearchResult], int]:
        """
        Search for videos by actor name on missav.ws.

        Returns (list_of_search_results, total_pages).
        Raises VideoParseError on total failure.
        """
        search_url = f"https://missav.ws/search/{quote(actor_name)}?page={page}"

        # Try curl first
        result = self._search_with_curl(search_url)
        if result is not None:
            return result

        # Fall back to playwright
        return self._search_with_playwright(search_url)

    def _search_with_curl(self, search_url: str) -> tuple[list[SearchResult], int] | None:
        """Use curl_cffi to search. Returns None on failure."""
        session = self._curl_session.get_session(search_url)
        if session is None:
            return None

        resp = session.get(search_url)
        if resp.status_code != 200:
            return None

        html = resp.text
        if "cloudflare" in html.lower() or "just a moment" in html.lower():
            return None

        return self._parse_search_html(html)

    def _search_with_playwright(self, search_url: str) -> tuple[list[SearchResult], int]:
        """Use system Playwright to search (only called when curl fails)."""
        if not self._playwright_session.is_available():
            raise VideoParseError(
                "Cloudflare 验证失败，且系统未安装 Playwright 浏览器。"
                "请在命令行运行: pip install playwright && playwright install chromium"
            )

        # Use base URL for Cloudflare bypass, then navigate to search
        context, browser, p = self._playwright_session.get_browser("https://missav.ws")

        try:
            page = context.new_page()
            page.goto(search_url, timeout=60000)
            page.wait_for_timeout(8000)

            # Extract video data using JavaScript (Vue.js SPA, no server-side rendered HTML)
            raw_data = page.evaluate(r"""() => {
                var seenIds = {};
                var results = [];
                var allAnchors = document.querySelectorAll('a');

                for (var i = 0; i < allAnchors.length; i++) {
                    var a = allAnchors[i];
                    var href = a.href || '';

                    // Match video detail URLs: /XXX-YYY or /XXX-YYY-uncensored-leak
                    // Exclude known non-video paths: /ms/, /makers, /dm, /vip, /actresses, /genres, /search, etc.
                    var match = href.match(/https:\\/\\/missav\\.live\\/(?!ms\\/|makers|dm\\d|actresses|genres|vip|search|chinese|uncensored)([a-zA-Z0-9]+-\\d+(?:-[a-z]+-leak)?)(?:\\/|\\?|$)/);
                    if (!match) continue;

                    var videoId = match[1].toLowerCase();
                    if (seenIds[videoId]) continue;
                    seenIds[videoId] = true;

                    // Get detail URL
                    var detailUrl = href.split('?')[0];  // remove query params

                    // Get duration from nearby text (duration appears near the video link)
                    var duration = 0;
                    var parent = a.closest('div');
                    if (parent) {
                        var text = parent.innerText || '';
                        var timeMatch = text.match(/(\\d{1,2}:\\d{2}(?::\\d{2})?)/);
                        if (timeMatch) {
                            var parts = timeMatch[1].split(':');
                            if (parts.length === 3) {
                                duration = parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
                            } else {
                                duration = parseInt(parts[0]) * 60 + parseInt(parts[1]);
                            }
                        }
                    }

                    // Get thumbnail from img inside the anchor (prefer data-src for lazy load)
                    var thumbnail = '';
                    var img = a.querySelector('img');
                    if (img) {
                        thumbnail = img.getAttribute('data-src') || img.src || '';
                        if (thumbnail.startsWith('data:')) thumbnail = '';
                    }

                    // Get title from sibling title element:
                    // The title <a> is in a sibling div: div.my-2.text-sm > a.text-secondary
                    var titleEl = null;
                    var container = parent ? parent.parentElement : null;
                    if (container) {
                        titleEl = container.querySelector('div.my-2.text-sm a.text-secondary, div.my-2 a, div a.text-secondary');
                    }
                    var title = '';
                    if (titleEl) {
                        title = titleEl.innerText.trim();
                        // Remove video ID prefix if present (e.g. "MIDA-585 " prefix)
                        title = title.replace(/^[A-Z]+-\d+\s*/i, '');
                    }

                    results.push({
                        videoId: videoId,
                        title: (title && title.length > 0) ? title.slice(0, 200) : videoId,
                        thumbnail: thumbnail,
                        duration: duration,
                        detailUrl: detailUrl
                    });
                }

                // Pagination: find highest page number from pagination links
                var totalPages = 1;
                var allAnchors = document.querySelectorAll('a');
                for (var i = 0; i < allAnchors.length; i++) {
                    var href = allAnchors[i].href || '';
                    // Match ?page=N or /page/N in URL
                    var pageMatch = href.match(/[?&]page=(\d+)/);
                    if (pageMatch) {
                        totalPages = Math.max(totalPages, parseInt(pageMatch[1]) || 1);
                    }
                }

                return { videos: results, totalPages: totalPages };
            }""")

            results = []
            for v in raw_data.get("videos", []):
                if v.get("videoId") and v.get("detailUrl"):
                    results.append(SearchResult(
                        video_id=v["videoId"],
                        title=v.get("title", "") or v["videoId"],
                        thumbnail=v.get("thumbnail", ""),
                        duration=v.get("duration", 0) or 0,
                        detail_url=v["detailUrl"],
                    ))

            return results, raw_data.get("totalPages", 1)

        finally:
            browser.close()
            p.stop()

    def _parse_search_html(self, html: str) -> tuple[list[SearchResult], int]:
        """Parse search results from HTML text. Used by curl path."""
        # NOTE: All CSS/XPath selectors need live-page verification against actual DOM
        results: list[SearchResult] = []

        # Find all video item blocks
        # Try multiple common selector patterns
        item_patterns = [
            r'<div[^>]+class=["\'][^"\']*video[-_]?(item|card)[^"\']*["\'][^>]*>(.*?)</div>',
            r'<article[^>]+class=["\'][^"\']*video[^"\']*["\'][^>]*>(.*?)</article>',
            r'<a[^>]+class=["\'][^"\']*video[^"\']*["\'][^>]*href=["\'](/[^"\']+)["\'][^>]*>(.*?)</a>',
        ]

        for pattern in item_patterns:
            matches = re.finditer(pattern, html, re.DOTALL | re.IGNORECASE)
            for match in matches:
                block = match.group(0) if match.lastindex == 1 else match.group(2) or match.group(0)

                # Extract detail URL
                detail_url = ""
                url_match = re.search(r'href=["\']([^"\']+)["\']', block)
                if url_match:
                    detail_url = url_match.group(1)

                # Extract video ID from URL
                video_id = ""
                if detail_url:
                    parsed = urlparse(detail_url)
                    segments = [s for s in parsed.path.strip("/").split("/") if s]
                    if segments:
                        video_id = segments[-1]

                # Extract title
                title = ""
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', block, re.IGNORECASE)
                if not title_match:
                    title_match = re.search(r'class=["\'][^"\']*(?:title|video[-_]?title)[^"\']*["\'][^>]*>([^<]+)', block, re.IGNORECASE)
                if not title_match:
                    title_match = re.search(r'alt=["\']([^"\']+)["\']', block)
                if title_match:
                    title = title_match.group(1).strip()

                # Extract thumbnail
                thumbnail = ""
                thumb_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', block, re.IGNORECASE)
                if not thumb_match:
                    thumb_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html)
                if thumb_match:
                    thumbnail = thumb_match.group(1)

                # Extract duration
                duration = 0
                duration_match = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>([^<]+)<', block, re.IGNORECASE)
                if duration_match:
                    duration_text = duration_match.group(1).strip()
                    parts = duration_text.split(":")
                    try:
                        if len(parts) == 3:
                            duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        elif len(parts) == 2:
                            duration = int(parts[0]) * 60 + int(parts[1])
                    except ValueError:
                        pass

                if video_id and title:
                    full_url = detail_url if detail_url.startswith("http") else f"https://missav.ws{detail_url}"
                    results.append(SearchResult(
                        video_id=video_id,
                        title=title,
                        thumbnail=thumbnail,
                        duration=duration,
                        detail_url=full_url,
                    ))

        # Extract total pages from pagination
        total_pages = 1
        page_matches = re.findall(r'class=["\'][^"\']*page[-_]?(?:number|link|item)[^"\']*["\'][^>]*>\s*(\d+)\s*<', html, re.IGNORECASE)
        if page_matches:
            total_pages = max(int(p) for p in page_matches if p.isdigit())

        return results, total_pages
