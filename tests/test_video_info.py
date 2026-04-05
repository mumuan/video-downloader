import pytest
from src.video_info import VideoInfo

def test_video_info_creation():
    info = VideoInfo(
        bv_id="BV1xx411xxx",
        title="测试视频标题",
        duration=754,  # seconds
        thumbnail="https://example.com/thumb.jpg",
        output_filename="测试视频标题_bilibili_BV1xx411xxx.mp4"
    )
    assert info.bv_id == "BV1xx411xxx"
    assert info.title == "测试视频标题"
    assert info.duration == 754
    assert info.formatted_duration == "12:34"
    assert info.output_filename == "测试视频标题_bilibili_BV1xx411xxx.mp4"
    assert info.source_site == "bilibili"  # 默认值
    assert info.direct_url is None  # 默认值


def test_video_info_missav():
    info = VideoInfo(
        bv_id="mfcw-008",
        title="测试视频",
        duration=0,
        thumbnail="https://example.com/thumb.jpg",
        output_filename="测试视频_missav_mfcw-008.mp4",
        source_site="missav",
        direct_url="https://cdn.example.com/video.mp4",
    )
    assert info.source_site == "missav"
    assert info.direct_url == "https://cdn.example.com/video.mp4"

def test_formatted_duration_short():
    info = VideoInfo(bv_id="BV1", title="t", duration=65, thumbnail="", output_filename="t.mp4")
    assert info.formatted_duration == "1:05"

def test_formatted_duration_zero():
    info = VideoInfo(bv_id="BV1", title="t", duration=0, thumbnail="", output_filename="t.mp4")
    assert info.formatted_duration == "0:00"


def test_formatted_duration_float():
    # yt-dlp returns float duration (e.g. 4869.48)
    info = VideoInfo(bv_id="BV1", title="t", duration=4869.48, thumbnail="", output_filename="t.mp4")
    assert info.formatted_duration == "1:21:09"


def test_formatted_duration_hours():
    info = VideoInfo(bv_id="BV1", title="t", duration=3661, thumbnail="", output_filename="t.mp4")
    assert info.formatted_duration == "1:01:01"