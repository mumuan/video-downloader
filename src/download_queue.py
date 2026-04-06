from PyQt6.QtCore import QObject, QThread, pyqtSignal

from src.downloader import Downloader, DownloadState
from src.video_info import VideoInfo


class DownloaderWorker(QThread):
    """Individual download worker running in its own QThread."""

    finished = pyqtSignal(str, bool, str)  # video_id, success, error
    progress = pyqtSignal(str, float)  # video_id, percent

    def __init__(self, video_info: VideoInfo, output_dir: str):
        super().__init__()
        self._video_info = video_info
        self._output_dir = output_dir
        self._downloader = Downloader(output_dir)

    def run(self):
        video_id = self._video_info.bv_id
        try:
            self._downloader.progress_changed.connect(
                lambda pct, _, __: self._on_progress(pct)
            )
            self._downloader.download_direct(
                self._video_info.direct_url,
                self._video_info.output_filename,
            )
            success = self._downloader.state == DownloadState.FINISHED
            error = "" if success else "unknown error"
            self.finished.emit(video_id, success, error)
        except Exception as e:
            self.finished.emit(video_id, False, str(e))

    def _on_progress(self, percent: float):
        self.progress.emit(self._video_info.bv_id, percent)


class DownloadQueue(QObject):
    """
    Manages concurrent video downloads using DownloaderWorker threads.

    Signals:
        batch_progress(int done, int total): overall batch progress
        item_progress(str video_id, float percent): per-item progress
        item_finished(str video_id): a single item finished
        item_failed(str video_id, str error): a single item failed
        batch_finished(list success_ids, list failed_ids): all items processed
    """

    batch_progress = pyqtSignal(int, int)  # done, total
    item_progress = pyqtSignal(str, float)  # video_id, percent
    item_finished = pyqtSignal(str)
    item_failed = pyqtSignal(str, str)  # video_id, error
    batch_finished = pyqtSignal(list, list)  # success_ids, failed_ids

    def __init__(self, output_dir: str, concurrent_downloads: int = 2):
        super().__init__()
        self._output_dir = output_dir
        self._concurrent = concurrent_downloads
        self._workers: list[DownloaderWorker] = []
        self._pending: list[VideoInfo] = []
        self._done_count = 0
        self._total_count = 0
        self._success_ids: list[str] = []
        self._failed_ids: list[str] = []
        self._started = False

    def start(self, video_infos: list[VideoInfo]):
        """Begin downloading the given list of VideoInfo items."""
        if self._started:
            return  # ignore re-entry
        self._started = True
        self._pending = list(video_infos)
        self._total_count = len(video_infos)
        self._done_count = 0
        self._success_ids = []
        self._failed_ids = []

        for _ in range(min(self._concurrent, len(self._pending))):
            self._launch_next()

    def _launch_next(self):
        """Start the next pending VideoInfo if any."""
        if not self._pending:
            return
        video_info = self._pending.pop(0)
        worker = DownloaderWorker(video_info, self._output_dir)
        worker.progress.connect(self._on_item_progress)
        worker.finished.connect(self._on_worker_done)
        self._workers.append(worker)
        worker.start()

    def _on_worker_done(self, video_id: str, success: bool, error: str):
        self._done_count += 1
        self.batch_progress.emit(self._done_count, self._total_count)

        if success:
            self._success_ids.append(video_id)
            self.item_finished.emit(video_id)
        else:
            self._failed_ids.append(video_id)
            self.item_failed.emit(video_id, error)

        # Remove the finished worker
        sender = self.sender()
        if sender in self._workers:
            self._workers.remove(sender)

        if self._done_count == self._total_count:
            self.batch_finished.emit(self._success_ids, self._failed_ids)
        else:
            self._launch_next()

    def _on_item_progress(self, video_id: str, percent: float):
        self.item_progress.emit(video_id, percent)
