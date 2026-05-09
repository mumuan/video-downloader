import enum
import json
import os
import tempfile

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
        self._cookie_file: str | None = None

    @property
    def state(self) -> DownloadState:
        return self._state

    def _set_state(self, state: DownloadState):
        self._state = state
        self.state_changed.emit(state.value)

    def download(self, url: str, output_filename: str):
        self._set_state(DownloadState.DOWNLOADING)
        ydl_opts = {
            "outtmpl": os.path.join(self.output_dir, output_filename),
            "format": (
                "bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/"
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "best[ext=mp4]/best"
            ),
            "merge_output_format": "mp4",
            "quiet": False,
            "no_warnings": False,
            "progress_hooks": [self._progress_hook],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self._set_state(DownloadState.FINISHED)
            self.finished.emit(os.path.join(self.output_dir, output_filename))
        except Exception as exc:
            self._set_state(DownloadState.ERROR)
            self.error.emit(str(exc))

    @staticmethod
    def _get_cloudflare_cookies_static() -> str | None:
        try:
            app_data = os.getenv("APPDATA") or os.path.expanduser("~/.config")
            state_file = os.path.join(
                app_data,
                "missav-downloader",
                "cookies",
                "cloudflare_state.json",
            )
            if not os.path.exists(state_file):
                return None

            with open(state_file, encoding="utf-8") as handle:
                state = json.load(handle)

            cookie_lines = ["# Netscape HTTP Cookie File"]
            for cookie in state.get("cookies", []):
                domain = cookie.get("domain", "missav.ws")
                if not domain.startswith("."):
                    domain = "." + domain
                expires = cookie.get("expires", -1)
                if expires == -1:
                    continue
                cookie_lines.append(
                    f"{domain}\tTRUE\t/\tFALSE\t{expires}\t{cookie['name']}\t{cookie['value']}"
                )

            if len(cookie_lines) <= 1:
                return None

            fd, path = tempfile.mkstemp(suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("\n".join(cookie_lines))
            return path
        except Exception:
            return None

    def download_direct(self, direct_url: str, output_filename: str):
        self._set_state(DownloadState.DOWNLOADING)

        ydl_opts = {
            "outtmpl": os.path.join(self.output_dir, output_filename),
            "quiet": False,
            "no_warnings": False,
            "progress_hooks": [self._progress_hook],
        }

        if "surrit.com" in direct_url:
            self._cookie_file = self._get_cloudflare_cookies_static()
            if self._cookie_file:
                ydl_opts["cookiefile"] = self._cookie_file
            ydl_opts["http_headers"] = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36"
                ),
                "Referer": "https://missav.ws/",
            }

        if "m3u8" in direct_url or "master" in direct_url:
            ydl_opts["hls_use_mpegts"] = True

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([direct_url])
            self._set_state(DownloadState.FINISHED)
            self.finished.emit(os.path.join(self.output_dir, output_filename))
        except Exception as exc:
            self._set_state(DownloadState.ERROR)
            self.error.emit(str(exc))
        finally:
            if self._cookie_file:
                try:
                    os.unlink(self._cookie_file)
                except OSError:
                    pass
                self._cookie_file = None

    def _progress_hook(self, data):
        if data["status"] != "downloading":
            return
        total = data.get("total_bytes") or data.get("total_bytes_estimate", 0)
        downloaded = data.get("downloaded_bytes", 0)
        speed = data.get("speed") or 0
        if total <= 0:
            return
        percent = (downloaded / total) * 100
        self.progress_changed.emit(
            percent,
            self._format_speed(speed),
            self._format_size(downloaded, total),
        )

    def _format_speed(self, speed: float) -> str:
        if speed is None:
            return "0B/s"
        if speed >= 1024 * 1024:
            return f"{speed / (1024 * 1024):.1f}MB/s"
        return f"{speed / 1024:.1f}KB/s"

    def _format_size(self, downloaded: int, total: int) -> str:
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        return f"{downloaded_mb:.1f}MB / {total_mb:.1f}MB"
