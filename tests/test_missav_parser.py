import pytest
from unittest.mock import MagicMock, patch

from src.parsers.missav_parser import MissavParser
from src.parsers.session_manager import VideoParseError
from src.video_info import VideoInfo


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
