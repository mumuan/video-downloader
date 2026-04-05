import enum
import yt_dlp
from PyQt6.QtCore import QObject, pyqtSignal


class DownloadState(enum.Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    FINISHED = "finished"
    ERROR = "error"


class Downloader(QObject):
    progress_changed = pyqtSignal(float, str, str)
    state_changed = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, output_dir: str):
        super().__init__()
        self.output_dir = output_dir
        self._state = DownloadState.IDLE

    @property
    def state(self) -> DownloadState:
        return self._state

    def _set_state(self, state: DownloadState):
        self._state = state
        self.state_changed.emit(state.value)

    def download(self, url: str, output_filename: str):
        self._set_state(DownloadState.DOWNLOADING)
        ydl_opts = {
            'outtmpl': f'{self.output_dir}/{output_filename}',
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self._set_state(DownloadState.FINISHED)
            self.finished.emit(f'{self.output_dir}/{output_filename}')
        except Exception as e:
            self._set_state(DownloadState.ERROR)
            self.error.emit(str(e))

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed') or 0
            if total > 0:
                percent = (downloaded / total) * 100
                speed_str = self._format_speed(speed)
                size_str = self._format_size(downloaded, total)
                self.progress_changed.emit(percent, speed_str, size_str)
        elif d['status'] == 'finished':
            pass

    def _format_speed(self, speed: float) -> str:
        if speed is None:
            return "0B/s"
        if speed >= 1024 * 1024:
            return f"{speed / (1024*1024):.1f}MB/s"
        return f"{speed / 1024:.1f}KB/s"

    def _format_size(self, downloaded: int, total: int) -> str:
        d_mb = downloaded / (1024 * 1024)
        t_mb = total / (1024 * 1024)
        return f"{d_mb:.1f}MB / {t_mb:.1f}MB"
