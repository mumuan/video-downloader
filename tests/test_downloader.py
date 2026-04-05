import pytest
from unittest.mock import MagicMock
from src.downloader import Downloader, DownloadState

def test_download_state_enum():
    assert DownloadState.IDLE.name == "IDLE"
    assert DownloadState.DOWNLOADING.name == "DOWNLOADING"
    assert DownloadState.FINISHED.name == "FINISHED"
    assert DownloadState.ERROR.name == "ERROR"


def test_download_state_enum_values():
    assert DownloadState.IDLE.value == "idle"
    assert DownloadState.DOWNLOADING.value == "downloading"
    assert DownloadState.FINISHED.value == "finished"
    assert DownloadState.ERROR.value == "error"


def test_downloader_initial_state():
    downloader = Downloader("/tmp")
    assert downloader.state == DownloadState.IDLE


def test_downloader_signals_exist():
    downloader = Downloader("/tmp")
    assert hasattr(downloader, 'progress_changed')
    assert hasattr(downloader, 'state_changed')
    assert hasattr(downloader, 'finished')
    assert hasattr(downloader, 'error')


def test_downloader_has_output_dir():
    downloader = Downloader("/output")
    assert downloader.output_dir == "/output"


def test_progress_hook_emits_signals():
    downloader = Downloader("/tmp")
    mock_slot = MagicMock()
    downloader.progress_changed.connect(mock_slot)

    # Simulate yt-dlp progress hook data
    d = {
        'status': 'downloading',
        'downloaded_bytes': 1024 * 1024 * 50,  # 50 MB
        'total_bytes': 1024 * 1024 * 100,       # 100 MB
        'speed': 1024 * 1024 * 2                  # 2 MB/s
    }
    downloader._progress_hook(d)

    mock_slot.assert_called_once()
    call_args = mock_slot.call_args[0]
    assert 49 < call_args[0] < 51  # approximately 50%
    assert "KB/s" in call_args[1] or "MB/s" in call_args[1]
    assert "MB" in call_args[2]


def test_format_speed():
    downloader = Downloader("/tmp")

    # Test KB/s
    assert "KB/s" in downloader._format_speed(512 * 1024)

    # Test MB/s
    assert "MB/s" in downloader._format_speed(2 * 1024 * 1024)

    # Test None
    assert "0B/s" in downloader._format_speed(None)


def test_format_size():
    downloader = Downloader("/tmp")
    result = downloader._format_size(50 * 1024 * 1024, 100 * 1024 * 1024)
    assert "50.0MB" in result
    assert "100.0MB" in result