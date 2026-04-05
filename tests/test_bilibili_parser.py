import pytest
from src.parsers.bilibili_parser import BilibiliParser


def test_normalize_bv_id():
    p = BilibiliParser()
    assert p._normalize_bv_id("BV1xxxx") == "BV1xxxx"
    assert p._normalize_bv_id("https://www.bilibili.com/video/BV1xxxx") == "BV1xxxx"
    assert p._normalize_bv_id("https://bilibili.com/video/BV1xxxx") == "BV1xxxx"


def test_normalize_bv_id_invalid():
    p = BilibiliParser()
    with pytest.raises(ValueError):
        p._normalize_bv_id("https://youtube.com/watch?v=xxx")


def test_normalize_bv_id_empty():
    p = BilibiliParser()
    with pytest.raises(ValueError):
        p._normalize_bv_id("")
