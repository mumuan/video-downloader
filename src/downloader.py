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
            'outtmpl': os.path.join(self.output_dir, output_filename),
            'format': 'bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            self._set_state(DownloadState.FINISHED)
            self.finished.emit(os.path.join(self.output_dir, output_filename))
        except Exception as e:
            self._set_state(DownloadState.ERROR)
            self.error.emit(str(e))

    @staticmethod
    def _get_cloudflare_cookies_static() -> str | None:
        """获取 missav Cloudflare cookies 文件路径（供 surrit.com CDN 使用）"""
        try:
            app_data = os.getenv("APPDATA") or os.path.expanduser("~/.config")
            state_file = os.path.join(app_data, "missav-downloader", "cookies", "cloudflare_state.json")
            if not os.path.exists(state_file):
                return None

            with open(state_file, encoding="utf-8") as f:
                state = json.load(f)

            # 写入 Netscape 格式 cookie 文件（过滤掉 expires=-1 的无效项）
            cookie_lines = ["# Netscape HTTP Cookie File"]
            for c in state.get("cookies", []):
                domain = c.get("domain", "missav.ws")
                if not domain.startswith("."):
                    domain = "." + domain
                expires = c.get("expires", -1)
                # 跳过无效的 cookie（如 cf_clearance=-1）
                if expires == -1:
                    continue
                cookie_lines.append(
                    f"{domain}\tTRUE\t/\tFALSE\t{expires}\t{c['name']}\t{c['value']}"
                )

            if len(cookie_lines) <= 1:
                return None

            fd, path = tempfile.mkstemp(suffix=".txt")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(cookie_lines))
            return path
        except Exception:
            return None

    def download_direct(self, direct_url: str, output_filename: str):
        """下载直链（missav 等无需解析的视频直链）"""
        self._set_state(DownloadState.DOWNLOADING)

        ydl_opts = {
            'outtmpl': os.path.join(self.output_dir, output_filename),
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
        }

        # surrit.com CDN 需要 Cloudflare clearance cookie 和 Referer
        if "surrit.com" in direct_url:
            self._cookie_file = self._get_cloudflare_cookies()
            if self._cookie_file:
                ydl_opts["cookiefile"] = self._cookie_file
            ydl_opts["http_headers"] = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
                "Referer": "https://missav.ws/",
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([direct_url])
            self._set_state(DownloadState.FINISHED)
            self.finished.emit(os.path.join(self.output_dir, output_filename))
        except Exception as e:
            self._set_state(DownloadState.ERROR)
            self.error.emit(str(e))
        finally:
            if self._cookie_file:
                try:
                    os.unlink(self._cookie_file)
                except OSError:
                    pass
                self._cookie_file = None

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
