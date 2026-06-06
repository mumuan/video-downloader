import enum
import json
import os
import tempfile

import yt_dlp
from yt_dlp import utils as yt_utils
from PyQt6.QtCore import QObject, pyqtSignal


class DownloadState(enum.Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    FINISHED = "finished"
    ERROR = "error"


class DownloadPaused(Exception):
    """Raised when a download is intentionally paused by the user."""


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
        self._pause_checker = None

    @property
    def state(self) -> DownloadState:
        return self._state

    def _set_state(self, state: DownloadState):
        self._state = state
        self.state_changed.emit(state.value)

    def download(self, url: str, output_filename: str):
        try:
            path = self.download_media(url=url, output_filename=output_filename)
            self.finished.emit(path)
        except Exception as exc:
            self.error.emit(str(exc))

    def _build_ydl_options(
        self,
        output_filename: str,
        *,
        direct_url: str | None = None,
        cookie_file: str | None = None,
        continuedl: bool = True,
        quiet: bool = False,
        no_warnings: bool = False,
        retries: int | None = None,
        fragment_retries: int | None = None,
        concurrent_fragment_downloads: int | None = None,
    ) -> dict:
        ydl_opts = {
            "outtmpl": os.path.join(self.output_dir, output_filename),
            "quiet": quiet,
            "no_warnings": no_warnings,
            "progress_hooks": [self._progress_hook],
            "continuedl": continuedl,
        }

        if direct_url is None:
            ydl_opts.update(
                {
                    "format": (
                        "bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/"
                        "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                        "best[ext=mp4]/best"
                    ),
                    "merge_output_format": "mp4",
                }
            )

        if retries is not None:
            ydl_opts["retries"] = retries
        if fragment_retries is not None:
            ydl_opts["fragment_retries"] = fragment_retries
        if concurrent_fragment_downloads is not None:
            ydl_opts["concurrent_fragment_downloads"] = concurrent_fragment_downloads

        if direct_url and ("m3u8" in direct_url or "master" in direct_url):
            ydl_opts["hls_use_mpegts"] = True

        if direct_url and "surrit.com" in direct_url:
            if cookie_file:
                ydl_opts["cookiefile"] = cookie_file
            ydl_opts["http_headers"] = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36"
                ),
                "Referer": "https://missav.ws/",
            }

        return ydl_opts

    def download_media(
        self,
        *,
        url: str | None = None,
        direct_url: str | None = None,
        output_filename: str,
        cookie_file: str | None = None,
        continuedl: bool = True,
        quiet: bool = False,
        no_warnings: bool = False,
        retries: int | None = None,
        fragment_retries: int | None = None,
        concurrent_fragment_downloads: int | None = None,
        pause_checker=None,
    ) -> str:
        download_url = direct_url or url
        if not download_url:
            raise ValueError("No download URL provided")

        self._pause_checker = pause_checker
        self._set_state(DownloadState.DOWNLOADING)
        ydl_opts = self._build_ydl_options(
            output_filename,
            direct_url=direct_url,
            cookie_file=cookie_file,
            continuedl=continuedl,
            quiet=quiet,
            no_warnings=no_warnings,
            retries=retries,
            fragment_retries=fragment_retries,
            concurrent_fragment_downloads=concurrent_fragment_downloads,
        )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([download_url])
        except yt_utils.DownloadCancelled as exc:
            if pause_checker and pause_checker():
                self._set_state(DownloadState.IDLE)
                raise DownloadPaused(str(exc)) from exc
            self._set_state(DownloadState.ERROR)
            raise
        except Exception:
            self._set_state(DownloadState.ERROR)
            raise
        finally:
            self._pause_checker = None

        self._set_state(DownloadState.FINISHED)
        return os.path.join(self.output_dir, output_filename)

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
        cookie_file = None
        if "surrit.com" in direct_url:
            cookie_file = self._get_cloudflare_cookies_static()
            self._cookie_file = cookie_file

        try:
            path = self.download_media(
                direct_url=direct_url,
                output_filename=output_filename,
                cookie_file=cookie_file,
            )
            self.finished.emit(path)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            if self._cookie_file:
                try:
                    os.unlink(self._cookie_file)
                except OSError:
                    pass
                self._cookie_file = None

    def _progress_hook(self, data):
        if self._pause_checker and self._pause_checker():
            raise yt_utils.DownloadCancelled("Download paused")

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
