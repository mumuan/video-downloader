import pytest
from PyQt6.QtWidgets import QApplication
from src.widgets.video_player_widget import VideoPlayerWidget


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_widget_has_idle_state_by_default(app):
    """Widget initializes in idle state."""
    widget = VideoPlayerWidget()
    assert widget._state == "idle"


def test_widget_shows_no_video_by_default(app):
    """Thumbnail shows 'No video' when idle."""
    widget = VideoPlayerWidget()
    assert "No video" in widget._thumbnail_label.text()


def test_set_video_info_updates_title(app):
    """set_video_info displays title and BV ID."""
    widget = VideoPlayerWidget()
    widget.set_video_info("Test Video Title", "BV123456")
    assert "Test Video Title" in widget._title_label.text()
    assert "BV123456" in widget._title_label.text()


def test_show_error_displays_error_message(app):
    """show_error displays error message and changes state."""
    widget = VideoPlayerWidget()
    widget.show_error("Download failed: network error")
    assert widget._state == "error"
    assert "network error" in widget._error_label.text()


def test_error_hides_thumbnail(app):
    """Error state hides thumbnail."""
    widget = VideoPlayerWidget()
    widget.show_error("Test error")
    assert not widget._thumbnail_label.isVisible()


def test_controls_disabled_when_idle(app):
    """Playback controls are disabled in idle state."""
    widget = VideoPlayerWidget()
    assert not widget._play_pause_btn.isEnabled()
    assert not widget._stop_btn.isEnabled()
    assert not widget._progress_slider.isEnabled()
    assert not widget._volume_slider.isEnabled()


def test_volume_slider_range(app):
    """Volume slider has range 0-100."""
    widget = VideoPlayerWidget()
    assert widget._volume_slider.minimum() == 0
    assert widget._volume_slider.maximum() == 100


def test_progress_slider_range(app):
    """Progress slider has range 0-1000."""
    widget = VideoPlayerWidget()
    assert widget._progress_slider.minimum() == 0
    assert widget._progress_slider.maximum() == 1000
