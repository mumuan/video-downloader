# src/main_window.py
import os
import re

from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.config import Config
from src.downloader import Downloader
from src.i18n import _
from src.video_info import VideoInfo
from src.video_parser import InvalidVideoURLError, VideoParser
from src.widgets.actor_search_tab import ActorSearchTab
from src.widgets.download_list_widget import DownloadItem, DownloadListWidget
from src.widgets.file_exists_dialog import FileExistsDialog
from src.widgets.video_player_widget import VideoPlayerWidget


class ParseVideoThread(QThread):
    parsed = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, raw_url: str):
        super().__init__()
        self._raw_url = raw_url

    def run(self):
        try:
            video_info = VideoParser().parse(self._raw_url)
        except InvalidVideoURLError as exc:
            self.error.emit(str(exc))
            return
        except Exception as exc:
            self.error.emit(f"{_('An error occurred during parsing')}: {exc}")
            return

        self.parsed.emit(video_info)


class DownloadThread(QThread):
    download_finished = pyqtSignal(str)
    download_paused = pyqtSignal(str)
    error = pyqtSignal(str)
    progress_changed = pyqtSignal(str, float, str, str)

    def __init__(
        self,
        output_dir: str,
        url: str | None,
        direct_url: str | None,
        output_filename: str,
        item_id: str,
        cookie_file: str | None = None,
        continuedl: bool = True,
    ):
        super().__init__()
        self.output_dir = output_dir
        self.url = url
        self.direct_url = direct_url
        self.output_filename = output_filename
        self.item_id = item_id
        self.cookie_file = cookie_file
        self.continuedl = continuedl
        self._pause_requested = False

    def request_pause(self):
        self._pause_requested = True

    def run(self):
        import yt_dlp
        from yt_dlp import utils as yt_utils

        output_path = os.path.join(self.output_dir, self.output_filename)
        download_url = self.direct_url or self.url

        ydl_opts = {
            "outtmpl": output_path,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [self._progress_hook],
            "continuedl": self.continuedl,
            "retries": 3,
            "fragment_retries": 3,
            "concurrent_fragment_downloads": 4,
            "nopart": False,
        }

        if self.direct_url and ("m3u8" in self.direct_url or "master" in self.direct_url):
            ydl_opts["hls_use_mpegts"] = True

        if self.direct_url and "surrit.com" in self.direct_url:
            if self.cookie_file:
                ydl_opts["cookiefile"] = self.cookie_file
            ydl_opts["http_headers"] = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/140.0.0.0 Safari/537.36"
                ),
                "Referer": "https://missav.ws/",
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([download_url])
            if self._pause_requested:
                self.download_paused.emit(output_path)
                return
            self.download_finished.emit(output_path)
        except yt_utils.DownloadCancelled:
            if self._pause_requested:
                self.download_paused.emit(output_path)
            else:
                self.error.emit(_("Download was cancelled"))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            if self.cookie_file:
                try:
                    os.unlink(self.cookie_file)
                except OSError:
                    pass

    def _progress_hook(self, data):
        from yt_dlp import utils as yt_utils

        if self._pause_requested:
            raise yt_utils.DownloadCancelled(_("Download paused"))

        if data["status"] != "downloading":
            return

        total = data.get("total_bytes") or data.get("total_bytes_estimate", 0)
        downloaded = data.get("downloaded_bytes", 0)
        speed = data.get("speed") or 0
        if total <= 0:
            return

        percent = (downloaded / total) * 100
        self.progress_changed.emit(
            self.item_id,
            percent,
            self._format_speed(speed),
            self._format_size(downloaded, total),
        )

    @staticmethod
    def _format_speed(speed: float) -> str:
        if speed is None:
            return "0B/s"
        if speed >= 1024 * 1024:
            return f"{speed / (1024 * 1024):.1f}MB/s"
        return f"{speed / 1024:.1f}KB/s"

    @staticmethod
    def _format_size(downloaded: int, total: int) -> str:
        downloaded_mb = downloaded / (1024 * 1024)
        total_mb = total / (1024 * 1024)
        return f"{downloaded_mb:.1f}MB / {total_mb:.1f}MB"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("xhub")
        self.setMinimumSize(900, 700)
        self.resize(1100, 800)

        app_data = os.path.join(os.path.expanduser("~"), ".xhub")
        os.makedirs(app_data, exist_ok=True)
        self.config = Config(app_data)
        self.current_video_info: VideoInfo | None = None
        self._parse_thread: ParseVideoThread | None = None
        self._active_thread: DownloadThread | None = None
        self._active_item_id: str | None = None
        self._current_playing_item_id: str | None = None
        self._player_started_for_item: set[str] = set()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_download_tab(), _("Video Download"))
        self._actor_tab = ActorSearchTab(self.config, self.download_list)
        self._tabs.addTab(self._actor_tab, _("Actor Search"))
        layout.addWidget(self._tabs)

        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"{_('Output Directory')}: {self.config.output_dir}")
        self.dir_label.setObjectName("dir_label")
        self.change_dir_btn = QPushButton(_("Change"))
        self.change_dir_btn.setObjectName("change_dir_btn")
        self.change_dir_btn.clicked.connect(self._on_change_dir)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.change_dir_btn)
        layout.addLayout(dir_layout)

        self.url_input.returnPressed.connect(self._on_download_clicked)

    def _create_download_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(10)

        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(_("Enter Bilibili/YouTube URL or BV号/Video ID..."))
        self.download_btn = QPushButton(_("Download"))
        self.download_btn.clicked.connect(self._on_download_clicked)
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.download_btn)
        tab_layout.addLayout(input_layout)

        self.status_label = QLabel("")
        self.status_label.setObjectName("status_label")
        self.status_label.hide()
        tab_layout.addWidget(self.status_label)

        self.player_panel = VideoPlayerWidget()
        tab_layout.addWidget(self.player_panel)

        self.download_list = DownloadListWidget(action_callback=self._on_action)
        self.download_list.setFixedHeight(220)
        tab_layout.addWidget(self.download_list)

        tab_layout.addStretch()
        return tab

    def _set_busy_state(self, busy: bool, message: str = "", button_text: str | None = None):
        self.download_btn.setEnabled(not busy)
        self.url_input.setEnabled(not busy)
        self.download_btn.setText(button_text or _("Download"))
        self.status_label.setText(message)
        self.status_label.setVisible(bool(message))

    def _set_current_playing_item(self, item_id: str | None):
        if self._current_playing_item_id and self._current_playing_item_id != item_id:
            self.download_list.update_item(self._current_playing_item_id, is_playing=False)
        self._current_playing_item_id = item_id
        if item_id:
            self.download_list.update_item(item_id, is_playing=True)

    def _clear_current_playing_item(self, item_id: str):
        if self._current_playing_item_id == item_id:
            self.download_list.update_item(item_id, is_playing=False)
            self._current_playing_item_id = None

    def _set_player_source(self, item: DownloadItem, file_path: str, preserve_position: bool = False):
        if not os.path.exists(file_path):
            return
        if self.player_panel.load_file(file_path, preserve_position=preserve_position):
            self.player_panel.set_video_info(item.title, item.id)
            self._set_current_playing_item(item.id)

    def _try_start_preview(self, item_id: str):
        if item_id in self._player_started_for_item:
            return

        item = self.download_list.get_item(item_id)
        if item is None:
            return

        full_path = os.path.join(self.config.output_dir, item.output_filename)
        part_path = full_path + ".part"
        candidate = part_path if os.path.exists(part_path) else full_path
        if not os.path.exists(candidate):
            return

        if os.path.getsize(candidate) < 512 * 1024:
            return

        self.download_list.update_item(item_id, file_path=candidate)
        self._set_player_source(item, candidate)
        self._player_started_for_item.add(item_id)

    def _make_download_target(self, video_info: VideoInfo) -> tuple[str | None, str | None]:
        bv_id = video_info.bv_id
        source_site = video_info.source_site
        if source_site == "bilibili":
            return f"https://www.bilibili.com/video/{bv_id}", None
        if source_site == "youtube":
            return f"https://www.youtube.com/watch?v={bv_id}", None
        if source_site == "missav":
            return None, getattr(video_info, "direct_url", None)
        return None, None

    def _on_change_dir(self):
        folder = QFileDialog.getExistingDirectory(self, _("Select output directory"), self.config.output_dir)
        if folder:
            self.config.output_dir = folder
            self.dir_label.setText(f"{_('Output Directory')}: {folder}")

    @pyqtSlot()
    def _on_download_clicked(self):
        raw = self.url_input.text().strip()
        if not raw or self._parse_thread or self._active_thread:
            return

        self.current_video_info = None
        self._set_busy_state(True, "Resolving video information...", "Resolving...")

        self._parse_thread = ParseVideoThread(raw)
        self._parse_thread.parsed.connect(self._on_parse_success)
        self._parse_thread.error.connect(self._on_parse_error)
        self._parse_thread.finished.connect(self._on_parse_thread_finished)
        self._parse_thread.start()

    @pyqtSlot(object)
    def _on_parse_success(self, video_info: VideoInfo):
        self.current_video_info = video_info
        self.player_panel.set_video_info(video_info.title, video_info.bv_id)
        self.status_label.setText("Starting download...")
        self._start_download()

    @pyqtSlot(str)
    def _on_parse_error(self, message: str):
        QMessageBox.warning(self, _("Parse failed"), message)
        self._set_busy_state(False)

    @pyqtSlot()
    def _on_parse_thread_finished(self):
        if self._parse_thread is not None:
            self._parse_thread.deleteLater()
            self._parse_thread = None

    def _start_download(self):
        if not self.current_video_info:
            self._set_busy_state(False)
            return

        output_path = os.path.join(self.config.output_dir, self.current_video_info.output_filename)
        if os.path.exists(output_path):
            dialog = FileExistsDialog(self.current_video_info.output_filename, self)
            result = dialog.exec()
            if result == FileExistsDialog.Result.SKIP:
                self._set_busy_state(False)
                return
            if result == FileExistsDialog.Result.RENAME:
                base, ext = os.path.splitext(self.current_video_info.output_filename)
                counter = 1
                while os.path.exists(os.path.join(self.config.output_dir, f"{base}_{counter}{ext}")):
                    counter += 1
                self.current_video_info.output_filename = f"{base}_{counter}{ext}"

        url, direct_url = self._make_download_target(self.current_video_info)
        if not direct_url and not url:
            self._set_busy_state(False)
            return

        cookie_file = None
        if self.current_video_info.source_site == "missav" and direct_url and "surrit.com" in direct_url:
            cookie_file = Downloader._get_cloudflare_cookies_static()

        item = DownloadItem(
            id=self.current_video_info.bv_id,
            title=self.current_video_info.title,
            output_filename=self.current_video_info.output_filename,
            source_site=self.current_video_info.source_site,
            state="downloading",
            progress=0.0,
            speed="",
            size_str="Waiting for data",
            file_path=None,
            direct_url=direct_url,
            is_playing=False,
        )
        self.download_list.add_item(item)

        self._active_item_id = item.id
        self._player_started_for_item.discard(item.id)
        self._active_thread = DownloadThread(
            self.config.output_dir,
            url,
            direct_url,
            self.current_video_info.output_filename,
            item.id,
            cookie_file=cookie_file,
        )
        self._active_thread.progress_changed.connect(self._on_progress)
        self._active_thread.download_finished.connect(self._on_finished)
        self._active_thread.download_paused.connect(self._on_paused)
        self._active_thread.error.connect(self._on_error)
        self._active_thread.finished.connect(self._on_download_thread_finished)
        self._active_thread.start()

        self._set_busy_state(True, "Download started", "Downloading...")

    @pyqtSlot(str, float, str, str)
    def _on_progress(self, item_id: str, percent: float, speed: str, size: str):
        self.download_list.update_item(
            item_id,
            progress=percent,
            speed=speed,
            size_str=size,
        )
        self._try_start_preview(item_id)

    @pyqtSlot(str)
    def _on_finished(self, path: str):
        if not self._active_item_id:
            return

        item_id = self._active_item_id
        self.download_list.update_item(
            item_id,
            state="finished",
            progress=100.0,
            file_path=path,
        )

        item = self.download_list.get_item(item_id)
        if item and self._current_playing_item_id == item_id:
            self._set_player_source(item, path, preserve_position=True)

        self.status_label.setText("Download finished")

    @pyqtSlot(str)
    def _on_paused(self, path: str):
        if not self._active_item_id:
            return

        item_id = self._active_item_id
        part_path = path + ".part"
        preview_path = part_path if os.path.exists(part_path) else path
        self.download_list.update_item(
            item_id,
            state="paused",
            file_path=preview_path if os.path.exists(preview_path) else None,
        )
        self.status_label.setText("Download paused")

    @pyqtSlot(str)
    def _on_error(self, message: str):
        if self._active_item_id:
            self.download_list.update_item(
                self._active_item_id,
                state="error",
                error_message=message,
                is_playing=False,
            )
            self._clear_current_playing_item(self._active_item_id)
        self.player_panel.show_error(message)
        self.status_label.setText(message)

    @pyqtSlot()
    def _on_download_thread_finished(self):
        if self._active_thread is not None:
            self._active_thread.deleteLater()
            self._active_thread = None
        self._active_item_id = None
        self.download_btn.setEnabled(True)
        self.url_input.setEnabled(True)
        self.download_btn.setText(_("Download"))

    def _on_action(self, item_id: str, action: str) -> None:
        if action == "pause":
            self._on_pause(item_id)
        elif action == "resume":
            self._on_resume(item_id)
        elif action == "play":
            self._on_play(item_id)
        elif action == "stop_play":
            self._on_stop_play(item_id)

    def _on_pause(self, item_id: str) -> None:
        if self._active_thread is None or self._active_item_id != item_id:
            return
        self.download_list.update_item(item_id, state="paused")
        self._active_thread.request_pause()

    def _on_resume(self, item_id: str) -> None:
        if self._active_thread is not None:
            return

        item = self.download_list.get_item(item_id)
        if item is None:
            return

        url = None
        direct_url = getattr(item, "direct_url", None)
        cookie_file = None
        if item.source_site == "missav" and direct_url and "surrit.com" in direct_url:
            cookie_file = Downloader._get_cloudflare_cookies_static()
        elif item.source_site == "bilibili":
            url = f"https://www.bilibili.com/video/{item.id}"
        elif item.source_site == "youtube":
            url = f"https://www.youtube.com/watch?v={item.id}"

        self.download_list.update_item(item_id, state="downloading")
        self._active_item_id = item_id
        self._active_thread = DownloadThread(
            self.config.output_dir,
            url,
            direct_url,
            item.output_filename,
            item_id,
            cookie_file=cookie_file,
            continuedl=True,
        )
        self._active_thread.progress_changed.connect(self._on_progress)
        self._active_thread.download_finished.connect(self._on_finished)
        self._active_thread.download_paused.connect(self._on_paused)
        self._active_thread.error.connect(self._on_error)
        self._active_thread.finished.connect(self._on_download_thread_finished)
        self._active_thread.start()
        self._set_busy_state(True, "Download resumed", "Downloading...")

    def _on_play(self, item_id: str) -> None:
        item = self.download_list.get_item(item_id)
        if item is None:
            return

        full_path = os.path.join(self.config.output_dir, item.output_filename)
        part_path = full_path + ".part"
        candidate = None
        if os.path.exists(full_path):
            candidate = full_path
        elif os.path.exists(part_path):
            candidate = part_path

        if candidate is None:
            return

        self.download_list.update_item(item_id, file_path=candidate)
        self._set_player_source(item, candidate)
        self._player_started_for_item.add(item_id)

    def _on_stop_play(self, item_id: str) -> None:
        self.player_panel.stop()
        self.download_list.update_item(item_id, is_playing=False)
        if self._current_playing_item_id == item_id:
            self._current_playing_item_id = None

    def closeEvent(self, event):
        download_in_progress = (
            self._active_thread is not None and self._active_thread.isRunning()
        )
        parse_in_progress = (
            self._parse_thread is not None and self._parse_thread.isRunning()
        )
        actor_downloading = (
            self._actor_tab._download_state
            in (ActorSearchTab.DOWNLOAD_EXTRACTING, ActorSearchTab.DOWNLOAD_DOWNLOADING)
        )

        if download_in_progress or parse_in_progress or actor_downloading:
            reply = QMessageBox.question(
                self,
                _("Confirm exit"),
                _("Download in progress, confirm exit?"),
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return

        event.accept()
