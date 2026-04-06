import pytest
from src.video_parser import VideoParser, InvalidVideoURLError


def test_detect_site_bilibili_url():
    p = VideoParser()
    assert p._detect_site("https://www.bilibili.com/video/BV1xxxx") == "bilibili"
    assert p._detect_site("https://bilibili.com/video/BV1xxxx") == "bilibili"
    assert p._detect_site("BV1xxxx") == "bilibili"


def test_detect_site_missav():
    p = VideoParser()
    assert p._detect_site("https://missav.ws/ja/mfcw-008") == "missav"
    assert p._detect_site("https://missav.ws/mfcw-008-uncensored-leak") == "missav"


def test_detect_site_unsupported():
    p = VideoParser()
    with pytest.raises(InvalidVideoURLError):
        p._detect_site("https://example.com/video")


def test_detect_site_youtube():
    p = VideoParser()
    assert p._detect_site("https://www.youtube.com/watch?v=abc123") == "youtube"
    assert p._detect_site("https://youtube.com/watch?v=abc123") == "youtube"
    assert p._detect_site("https://youtu.be/abc123") == "youtube"


def test_detect_site_empty():
    p = VideoParser()
    with pytest.raises(InvalidVideoURLError):
        p._detect_site("")
