import pytest
from PyQt6.QtWidgets import QApplication
from src.widgets.video_info_panel import VideoInfoPanel
from src.video_info import VideoInfo

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_panel_shows_video_info(app):
    panel = VideoInfoPanel()
    info = VideoInfo(
        bv_id="BV1xx411xxx",
        title="测试视频",
        duration=754,
        thumbnail="",
        output_filename="测试视频_bilibili_BV1xx411xxx.mp4"
    )
    panel.set_video_info(info)
    assert "测试视频" in panel.title_label.text()
    assert "BV1xx411xxx" in panel.bv_label.text()
    assert "12:34" in panel.duration_label.text()

def test_panel_empty_by_default(app):
    panel = VideoInfoPanel()
    assert "暂无视频信息" in panel.title_label.text()