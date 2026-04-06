import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.parsers.missav_parser import MissavParser
from src.parsers.session_manager import VideoParseError
from src.video_info import VideoInfo
from src.search_result import SearchResult


def test_extract_video_id():
    p = MissavParser()
    assert p._extract_video_id("https://missav.live/ja/mfcw-008") == "mfcw-008"
    assert (
        p._extract_video_id("https://missav.live/ja/mfcw-008-uncensored-leak")
        == "mfcw-008-uncensored-leak"
    )
    assert p._extract_video_id("https://missav.live/mfcw-008") == "mfcw-008"


def test_extract_video_id_invalid():
    p = MissavParser()
    with pytest.raises(VideoParseError):
        p._extract_video_id("https://missav.live/")


def test_make_filename():
    p = MissavParser()
    result = p._make_filename("测试标题", "mfcw-008")
    assert result == "测试标题_missav_mfcw-008.mp4"


def test_make_filename_sanitizes_chars():
    p = MissavParser()
    result = p._make_filename('测试<>:"/\\|?*标题', "mfcw-008")
    assert "<" not in result
    assert ">" not in result
    assert ":" not in result
    assert '"' not in result
    assert "/" not in result
    assert "\\" not in result
    assert "|" not in result
    assert "?" not in result
    assert "*" not in result
    assert "mfcw-008" in result


@patch("src.parsers.missav_parser.playwright")
def test_parse_success(mock_playwright):
    mock_page = MagicMock()
    mock_page.title.return_value = "测试视频"
    # page.evaluate 用于 window.source1280 / window.source842 提取
    # 第一次返回 surrit.com URL（模拟完整 VOD playlist）
    mock_page.evaluate.side_effect = [
        "https://surrit.com/test-id/1280x720/video.m3u8",  # window.source1280
    ]
    # eval_on_selector 只在 fallback 路径使用（thumbnail）
    mock_page.eval_on_selector.side_effect = [
        "https://cdn.example.com/thumb.jpg",  # og:image
    ]

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser

    mock_playwright.sync_playwright.return_value.__enter__ = MagicMock(
        return_value=mock_p
    )
    mock_playwright.sync_playwright.return_value.__exit__ = MagicMock(
        return_value=False
    )

    # Mock SessionManager.get_verified_context at module level
    with patch(
        "src.parsers.missav_parser.SessionManager.get_verified_context"
    ) as mock_get_ctx:
        mock_get_ctx.return_value = (mock_context, mock_browser)

        parser = MissavParser()
        result = parser.parse("https://missav.live/ja/mfcw-008")

    assert isinstance(result, VideoInfo)
    assert result.bv_id == "mfcw-008"
    assert result.source_site == "missav"
    assert result.direct_url == "https://surrit.com/test-id/1280x720/video.m3u8"
    assert result.thumbnail == "https://cdn.example.com/thumb.jpg"
    assert "mfcw-008" in result.output_filename
    assert "_missav_" in result.output_filename


@patch("src.parsers.missav_parser.playwright")
def test_parse_no_video_raises_error(mock_playwright):
    mock_page = MagicMock()
    mock_page.wait_for_selector.side_effect = Exception("timeout")

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_p = MagicMock()
    mock_p.chromium.launch.return_value = mock_browser

    mock_playwright.sync_playwright.return_value.__enter__ = MagicMock(
        return_value=mock_p
    )
    mock_playwright.sync_playwright.return_value.__exit__ = MagicMock(
        return_value=False
    )

    with patch(
        "src.parsers.missav_parser.SessionManager.get_verified_context"
    ) as mock_get_ctx:
        mock_get_ctx.return_value = (mock_context, mock_browser)

        parser = MissavParser()
        with pytest.raises(VideoParseError, match="无法获取视频"):
            parser.parse("https://missav.live/ja/mfcw-008")


class TestSearchParse:
    """Tests for MissavParser.search_parse()"""

    def test_search_with_curl_returns_results(self):
        """Curl path successfully parses search results HTML."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html><body>
            <div class="video-item">
                <a href="/mfcw-008"></a>
                <span class="title">测试视频1</span>
                <img src="https://cdn.example.com/thumb1.jpg">
                <span class="duration">10:30</span>
            </div>
            <div class="video-item">
                <a href="/abc-123"></a>
                <span class="title">测试视频2</span>
                <img src="https://cdn.example.com/thumb2.jpg">
                <span class="duration">1:05:20</span>
            </div>
        </body></html>
        """

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_response

        with patch(
            "src.parsers.missav_parser.CurlSessionManager.get_session",
            return_value=mock_session_instance,
        ):
            parser = MissavParser()
            results, total_pages = parser._search_with_curl(
                "https://missav.live/search/test?page=1"
            )

        assert results is not None
        assert len(results) >= 1
        video = next((r for r in results if r.video_id == "mfcw-008"), None)
        assert video is not None
        assert video.thumbnail == "https://cdn.example.com/thumb1.jpg"
        assert video.duration == 630  # 10*60 + 30
        assert video.detail_url == "https://missav.live/mfcw-008"

    def test_search_with_curl_returns_none_on_cloudflare(self):
        """Returns None when curl gets a Cloudflare challenge page."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Just a moment...</body></html>"

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_response

        with patch(
            "src.parsers.missav_parser.CurlSessionManager.get_session",
            return_value=mock_session_instance,
        ):
            parser = MissavParser()
            result = parser._search_with_curl("https://missav.live/search/test")

        assert result is None

    def test_search_with_curl_returns_none_when_session_fails(self):
        """Returns None when session manager can't get a session."""
        with patch(
            "src.parsers.missav_parser.CurlSessionManager.get_session",
            return_value=None,
        ):
            parser = MissavParser()
            result = parser._search_with_curl("https://missav.live/search/test")

        assert result is None

    def test_search_with_curl_returns_none_on_bad_status(self):
        """Returns None when HTTP status is not 200."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "<html></html>"

        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_response

        with patch(
            "src.parsers.missav_parser.CurlSessionManager.get_session",
            return_value=mock_session_instance,
        ):
            parser = MissavParser()
            result = parser._search_with_curl("https://missav.live/search/test")

        assert result is None

    def test_search_parse_falls_back_to_playwright_when_curl_fails(self):
        """search_parse falls back to playwright when curl returns None."""
        with patch(
            "src.parsers.missav_parser.CurlSessionManager.get_session",
            return_value=None,
        ):
            with patch(
                "src.parsers.missav_parser.PlaywrightSessionManager.is_available",
                return_value=False,
            ):
                parser = MissavParser()
                with pytest.raises(VideoParseError, match="未安装 Playwright"):
                    parser.search_parse("test actor")

    def test_parse_search_html_video_item_div(self):
        """HTML parser extracts video items from div.video-item pattern."""
        html = """
        <html><body>
            <div class="video-item">
                <a href="/xyz-999"></a>
                <span class="title">卡牌视频</span>
                <img src="https://cdn.example.com/card.jpg">
                <span class="duration">25:00</span>
            </div>
        </body></html>
        """
        parser = MissavParser()
        results, total_pages = parser._parse_search_html(html)

        assert len(results) >= 1
        video = next((r for r in results if r.video_id == "xyz-999"), None)
        assert video is not None
        assert video.title == "卡牌视频"
        assert video.thumbnail == "https://cdn.example.com/card.jpg"
        assert video.duration == 1500

    def test_parse_search_html_pagination_defaults_to_one(self):
        """Returns total_pages=1 when no pagination is found."""
        html = "<html><body><p>No results</p></body></html>"
        parser = MissavParser()
        _, total_pages = parser._parse_search_html(html)
        assert total_pages == 1

    def test_search_result_video_id_extracted_from_url_path(self):
        """Video ID is correctly extracted from a /path/video-id URL."""
        html = """
        <html><body>
            <div class="video-item">
                <a href="/ja/sim-004-uncensored"></a>
                <span class="title">测试标题</span>
            </div>
        </body></html>
        """
        parser = MissavParser()
        results, _ = parser._parse_search_html(html)

        assert len(results) >= 1
        video = next((r for r in results if r.video_id == "sim-004-uncensored"), None)
        assert video is not None
