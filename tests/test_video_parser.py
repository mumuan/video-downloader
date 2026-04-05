import pytest
from src.video_parser import VideoParser, InvalidVideoURLError

def test_normalize_bv_id():
    p = VideoParser()
    assert p._normalize_bv_id("BV1xxxx") == "BV1xxxx"
    assert p._normalize_bv_id("https://www.bilibili.com/video/BV1xxxx") == "BV1xxxx"
    assert p._normalize_bv_id("https://bilibili.com/video/BV1xxxx") == "BV1xxxx"

def test_normalize_bv_id_invalid():
    p = VideoParser()
    with pytest.raises(InvalidVideoURLError):
        p._normalize_bv_id("https://youtube.com/watch?v=xxx")

def test_normalize_bv_id_empty():
    p = VideoParser()
    with pytest.raises(InvalidVideoURLError):
        p._normalize_bv_id("")