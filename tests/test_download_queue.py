import sys
import pytest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication

from src.download_queue import DownloadQueue, DownloaderWorker
from src.video_info import VideoInfo


@pytest.fixture
def qapp():
    """Provide a QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_video_infos():
    """Create 3 mock VideoInfo objects for testing."""
    return [
        VideoInfo(
            bv_id=f"video-{i}",
            title=f"Video {i}",
            duration=120,
            thumbnail="",
            output_filename=f"Video_{i}_missav_video-{i}.mp4",
            source_site="missav",
            direct_url=f"https://example.com/video-{i}.mp4",
        )
        for i in range(1, 4)
    ]


def _simulate_worker_run_sync(worker):
    """Simulate a worker completing its download synchronously."""
    vid = worker._video_info.bv_id
    # Emit progress then finished as if run() completed
    worker.progress.emit(vid, 100.0)
    worker.finished.emit(vid, True, "")


class TestDownloadQueue:
    """Tests for DownloadQueue concurrent download manager."""

    def test_batch_finished_signal_on_all_success(self, mock_video_infos, qapp):
        """All downloads succeed → batch_finished has 3 success_ids, 0 failed_ids."""
        queue = DownloadQueue(output_dir="/tmp/downloads", concurrent_downloads=2)

        results = {}
        queue.batch_finished.connect(
            lambda success, failed: results.update(
                {"success": list(success), "failed": list(failed)}
            )
        )

        with patch.object(DownloaderWorker, "start"):
            queue.start(mock_video_infos)
            QCoreApplication.processEvents()

            # Use while-loop (not for-loop) because workers can be added during iteration
            while queue._workers:
                worker = queue._workers[0]
                _simulate_worker_run_sync(worker)
                QCoreApplication.processEvents()

        assert queue._done_count == 3
        assert len(results.get("success", [])) == 3
        assert len(results.get("failed", [])) == 0

    def test_batch_finished_signal_with_failures(self, mock_video_infos, qapp):
        """One download fails → batch_finished has correct success and failed lists."""
        queue = DownloadQueue(output_dir="/tmp/downloads", concurrent_downloads=2)

        results = {}
        queue.batch_finished.connect(
            lambda success, failed: results.update(
                {"success": list(success), "failed": list(failed)}
            )
        )

        with patch.object(DownloaderWorker, "start"):
            queue.start(mock_video_infos)
            QCoreApplication.processEvents()

            # Phase 1: video-1 finishes → worker for video-3 is launched
            worker1 = queue._workers[0]
            worker1.finished.emit("video-1", True, "")
            QCoreApplication.processEvents()

            # After worker1 finishes, worker3 should have been launched
            worker3 = next(
                (w for w in queue._workers if w._video_info.bv_id == "video-3"), None
            )
            assert worker3 is not None, "Third worker should have been launched"

            # Phase 2: video-2 fails (it was started initially as second concurrent worker)
            worker2 = next(
                (w for w in queue._workers if w._video_info.bv_id == "video-2"), None
            )
            assert worker2 is not None
            worker2.finished.emit("video-2", False, "download failed")
            QCoreApplication.processEvents()

            # Phase 3: video-3 finishes
            worker3.finished.emit("video-3", True, "")
            QCoreApplication.processEvents()

        assert set(results.get("success", [])) == {"video-1", "video-3"}
        assert results.get("failed", []) == ["video-2"]

    def test_concurrent_workers_launched_up_to_limit(self, mock_video_infos):
        """With concurrent=2 and 3 videos, exactly 2 workers start immediately."""
        queue = DownloadQueue(output_dir="/tmp/downloads", concurrent_downloads=2)

        started_workers = []

        def tracking_start(self):
            started_workers.append(self)
            # Don't actually start the thread - just track that it was asked to start

        with patch.object(DownloaderWorker, "start", tracking_start):
            queue.start(mock_video_infos)

        assert len(started_workers) == 2  # Only 2 started (concurrent limit)
        assert len(queue._pending) == 1  # 1 still pending

    def test_start_ignores_reentry(self, mock_video_infos):
        """Calling start() twice does not restart the batch."""
        queue = DownloadQueue(output_dir="/tmp/downloads", concurrent_downloads=2)

        started_count = 0

        def counting_start(self):
            nonlocal started_count
            started_count += 1

        with patch.object(DownloaderWorker, "start", counting_start):
            queue.start(mock_video_infos)
            queue.start(mock_video_infos)  # re-entry

        assert started_count == 2  # Only first call launches workers

    def test_item_progress_signal_emitted(self, mock_video_infos, qapp):
        """item_progress signal is forwarded from workers."""
        queue = DownloadQueue(output_dir="/tmp/downloads", concurrent_downloads=2)

        progress_signals = []
        queue.item_progress.connect(
            lambda vid, pct: progress_signals.append((vid, pct))
        )

        with patch.object(DownloaderWorker, "start"):
            queue.start(mock_video_infos)
            QCoreApplication.processEvents()

            worker = queue._workers[0]
            worker.progress.emit("video-1", 50.0)
            QCoreApplication.processEvents()

        assert ("video-1", 50.0) in progress_signals

    def test_item_finished_signal_emitted(self, mock_video_infos, qapp):
        """item_finished signal is emitted when a worker succeeds."""
        queue = DownloadQueue(output_dir="/tmp/downloads", concurrent_downloads=2)

        finished_ids = []
        queue.item_finished.connect(lambda vid: finished_ids.append(vid))

        with patch.object(DownloaderWorker, "start"):
            queue.start(mock_video_infos)
            QCoreApplication.processEvents()

            worker = queue._workers[0]
            worker.finished.emit("video-1", True, "")
            QCoreApplication.processEvents()

        assert "video-1" in finished_ids

    def test_item_failed_signal_emitted(self, mock_video_infos, qapp):
        """item_failed signal is emitted when a worker fails."""
        queue = DownloadQueue(output_dir="/tmp/downloads", concurrent_downloads=2)

        failed = []
        queue.item_failed.connect(lambda vid, err: failed.append((vid, err)))

        with patch.object(DownloaderWorker, "start"):
            queue.start(mock_video_infos)
            QCoreApplication.processEvents()

            worker = queue._workers[0]
            worker.finished.emit("video-1", False, "network error")
            QCoreApplication.processEvents()

        assert ("video-1", "network error") in failed


class TestDownloaderWorker:
    """Tests for DownloaderWorker QThread."""

    def test_worker_initializes_with_video_info(self):
        """Worker stores the VideoInfo it will download."""
        vi = VideoInfo(
            bv_id="test-123",
            title="Test",
            duration=60,
            thumbnail="",
            output_filename="Test_missav_test-123.mp4",
            source_site="missav",
            direct_url="https://example.com/test.mp4",
        )
        worker = DownloaderWorker(vi, "/tmp/dl")
        assert worker._video_info == vi
        assert worker._output_dir == "/tmp/dl"

    def test_worker_has_finished_signal(self):
        """Worker has finished(str, bool, str) signal."""
        vi = VideoInfo(
            bv_id="x",
            title="x",
            duration=0,
            thumbnail="",
            output_filename="x.mp4",
            source_site="missav",
            direct_url="https://x.com/x.mp4",
        )
        worker = DownloaderWorker(vi, "/tmp")
        assert hasattr(worker, "finished")
        assert hasattr(worker, "progress")
