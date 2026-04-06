# src/main_window.py
import os
import re
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
    QTabWidget
)
from PyQt6.QtCore import QThread, pyqtSlot, pyqtSignal, Qt, QObject
from src.video_parser import VideoParser, InvalidVideoURLError
from src.downloader import Downloader, DownloadState
from src.config import Config
from src.video_info import VideoInfo
from src.widgets.video_info_panel import VideoInfoPanel
from src.widgets.download_list_widget import DownloadListWidget, DownloadItem
from src.widgets.file_exists_dialog import FileExistsDialog
from src.widgets.actor_search_tab import ActorSearchTab
from src.i18n import _


class DownloadThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress_changed = pyqtSignal(str, float, str, str)  # item_id, percent, speed, size

    def __init__(self, output_dir: str, url: str | None, direct_url: str | None, output_filename: str, item_id: str, cookie_file: str | None = None, continuedl: bool = True):
        super().__init__()
        self.output_dir = output_dir
        self.url = url
        self.direct_url = direct_url
        self.output_filename = output_filename
        self.item_id = item_id
        self.cookie_file = cookie_file
        self.continuedl = continuedl

    def run(self):
        import yt_dlp

        output_path = os.path.join(self.output_dir, self.output_filename)
        download_url = self.direct_url if self.direct_url else self.url

        ydl_opts = {
            'outtmpl': output_path,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [self._progress_hook],
            'continuedl': self.continuedl,
        }

        if self.direct_url and "surrit.com" in self.direct_url:
            if self.cookie_file:
                ydl_opts['cookiefile'] = self.cookie_file
            ydl_opts['http_headers'] = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
                'Referer': 'https://missav.ws/',
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([download_url])
            self.finished.emit(output_path)
        except Exception as e:
            self.error.emit(str(e))

    def _parse_progress(self, line: str):
        # Example: [download] 0.0% of ~   1.23GiB at    252.01B/s ETA --:--:-- (frag 0/886)
        match = re.search(r'\[download\]\s+([\d.]+)%\s+of ~   ([\d.]+[A-Za-z]+)\s+at\s+([\d.]+[A-Za-z]+/s)', line)
        if match:
            percent = float(match.group(1))
            size_str = match.group(2)
            speed = match.group(3)
            self.progress_changed.emit(percent, speed, size_str)

    def _progress_hook(self, d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed') or 0
            if total > 0:
                percent = (downloaded / total) * 100
                speed_str = self._format_speed(speed)
                size_str = self._format_size(downloaded, total)
                self.progress_changed.emit(self.item_id, percent, speed_str, size_str)

    def _format_speed(self, speed):
        if speed is None:
            return "0B/s"
        if speed >= 1024 * 1024:
            return f"{speed / (1024*1024):.1f}MB/s"
        return f"{speed / 1024:.1f}KB/s"

    def _format_size(self, downloaded, total):
        d_mb = downloaded / (1024 * 1024)
        t_mb = total / (1024 * 1024)
        return f"{d_mb:.1f}MB / {t_mb:.1f}MB"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("xhub")
        self.setMinimumSize(700, 600)

        app_data = os.path.join(os.path.expanduser("~"), ".bilibili-downloader")
        os.makedirs(app_data, exist_ok=True)
        self.config = Config(app_data)
        self.parser = VideoParser()
        self.current_video_info: VideoInfo | None = None
        self._active_thread: DownloadThread | None = None
        self._active_item_id: str | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_bilibili_tab(), _("Video Download"))
        self._actor_tab = ActorSearchTab(self.config, self.download_list)
        self._tabs.addTab(self._actor_tab, _("Actor Search"))
        layout.addWidget(self._tabs)

        # Output dir (shared) - at the bottom
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"{_("Output Directory")}: {self.config.output_dir}")
        self.dir_label.setObjectName("dir_label")
        self.change_dir_btn = QPushButton(_("Change"))
        self.change_dir_btn.setObjectName("change_dir_btn")
        self.change_dir_btn.clicked.connect(self._on_change_dir)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.change_dir_btn)
        layout.addLayout(dir_layout)

        self.url_input.returnPressed.connect(self._on_download_clicked)

    def _create_bilibili_tab(self) -> QWidget:
        """Build the Bilibili download tab content."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(10)

        # URL input row
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(_("Enter Bilibili/YouTube URL or BV号/Video ID..."))
        self.download_btn = QPushButton(_("Download"))
        self.download_btn.clicked.connect(self._on_download_clicked)
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.download_btn)
        tab_layout.addLayout(input_layout)

        # Video info panel
        self.info_panel = VideoInfoPanel()
        tab_layout.addWidget(self.info_panel)

        # Download list with fixed height
        self.download_list = DownloadListWidget(action_callback=self._on_action)
        self.download_list.setFixedHeight(200)  # Fixed height for download list
        tab_layout.addWidget(self.download_list)

        tab_layout.addStretch()
        return tab

    def _on_change_dir(self):
        folder = QFileDialog.getExistingDirectory(self, _("Select output directory"), self.config.output_dir)
        if folder:
            self.config.output_dir = folder
            self.dir_label.setText(f"{_("Output Directory")}: {folder}")

    @pyqtSlot()
    def _on_download_clicked(self):
        raw = self.url_input.text().strip()
        if not raw:
            return

        self.download_btn.setEnabled(False)

        try:
            self.current_video_info = self.parser.parse(raw)
            self.info_panel.set_video_info(self.current_video_info)
            self._start_download()
        except InvalidVideoURLError as e:
            QMessageBox.warning(self, _("Parse failed"), str(e))
            self.download_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, _("Error"), f"{_("An error occurred during parsing")}: {str(e)}")
            self.download_btn.setEnabled(True)

    def _start_download(self):
        if not self.current_video_info:
            return

        output_path = os.path.join(self.config.output_dir, self.current_video_info.output_filename)

        if os.path.exists(output_path):
            dialog = FileExistsDialog(self.current_video_info.output_filename, self)
            result = dialog.exec()
            if result == FileExistsDialog.Result.SKIP:
                self.download_btn.setEnabled(True)
                return
            if result == FileExistsDialog.Result.RENAME:
                base, ext = os.path.splitext(self.current_video_info.output_filename)
                counter = 1
                while os.path.exists(os.path.join(self.config.output_dir, f"{base}_{counter}{ext}")):
                    counter += 1
                self.current_video_info.output_filename = f"{base}_{counter}{ext}"

        bv_id = self.current_video_info.bv_id
        source_site = self.current_video_info.source_site
        if source_site == "bilibili":
            url = f"https://www.bilibili.com/video/{bv_id}"
            direct_url = None
        elif source_site == "youtube":
            url = f"https://www.youtube.com/watch?v={bv_id}"
            direct_url = None
        elif source_site == "missav":
            url = None
            direct_url = getattr(self.current_video_info, 'direct_url', None)
            if not direct_url:
                self.download_btn.setEnabled(True)
                return
        else:
            self.download_btn.setEnabled(True)
            return

        # Get cookie file for surrit.com CDN if needed
        cookie_file = None
        if source_site == "missav" and direct_url and "surrit.com" in direct_url:
            cookie_file = Downloader._get_cloudflare_cookies_static()

        # Add to download list
        item = DownloadItem(
            id=bv_id,
            title=self.current_video_info.title,
            output_filename=self.current_video_info.output_filename,
            source_site=source_site,
            state="downloading",
            progress=0.0,
            speed="",
            size_str="",
            file_path=None,
            direct_url=direct_url,
        )
        self.download_list.add_item(item)

        self._active_item_id = bv_id
        self._active_thread = DownloadThread(
            self.config.output_dir, url, direct_url, self.current_video_info.output_filename, bv_id, cookie_file
        )
        self._active_thread.progress_changed.connect(self._on_progress)
        self._active_thread.finished.connect(self._on_finished)
        self._active_thread.error.connect(self._on_error)
        self._active_thread.start()

    @pyqtSlot(str, float, str, str)
    def _on_progress(self, item_id, percent, speed, size):
        self.download_list.update_item(
            item_id,
            progress=percent,
            speed=speed,
            size_str=size,
        )

    @pyqtSlot(str)
    def _on_state(self, state):
        pass

    @pyqtSlot(str)
    def _on_finished(self, path):
        if self._active_item_id:
            self.download_list.update_item(
                self._active_item_id,
                state="finished",
                progress=100.0,
                file_path=path,
            )
        self._active_thread = None
        self._active_item_id = None
        self.download_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_error(self, message):
        if self._active_item_id:
            self.download_list.update_item(
                self._active_item_id,
                state="error",
                error_message=message,
            )
        self._active_thread = None
        self._active_item_id = None
        self.download_btn.setEnabled(True)

    def _on_action(self, item_id: str, action: str) -> None:
        """Route action button click to pause/resume/open."""
        if action == "pause":
            self._on_pause(item_id)
        elif action == "resume":
            self._on_resume(item_id)

    def _on_pause(self, item_id: str) -> None:
        """Pause the active download."""
        if self._active_thread is None:
            return
        self._active_thread.terminate()
        self._active_thread = None
        self.download_list.update_item(item_id, state="paused")
        self._active_item_id = None

    def _on_resume(self, item_id: str) -> None:
        """Resume a paused download."""
        item = self.download_list.get_item(item_id)
        if not item:
            return
        # Disconnect old signals if any
        if self._active_thread:
            try:
                self._active_thread.progress_changed.disconnect()
                self._active_thread.finished.disconnect()
                self._active_thread.error.disconnect()
            except Exception:
                pass
        # Get cookie file for surrit.com CDN
        cookie_file = None
        direct_url = getattr(item, 'direct_url', None)
        url = None
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
        self._active_thread.finished.connect(self._on_finished)
        self._active_thread.error.connect(self._on_error)
        self._active_thread.start()

    def closeEvent(self, event):
        """Warn user if a download is in progress."""
        # Check bilibili tab download
        bilibili_downloading = (
            hasattr(self, 'downloader')
            and self.downloader.state == DownloadState.DOWNLOADING
        )
        # Check actor tab download
        actor_downloading = (
            self._actor_tab._download_state
            in (ActorSearchTab.DOWNLOAD_EXTRACTING, ActorSearchTab.DOWNLOAD_DOWNLOADING)
        )

        if bilibili_downloading or actor_downloading:
            reply = QMessageBox.question(
                self, _("Confirm exit"),
                _("Download in progress, confirm exit?"),
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()
