# src/main_window.py
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
    QTabWidget
)
from PyQt6.QtCore import QThread, pyqtSlot, Qt
from src.video_parser import VideoParser, InvalidVideoURLError
from src.downloader import Downloader, DownloadState
from src.config import Config
from src.video_info import VideoInfo
from src.widgets.video_info_panel import VideoInfoPanel
from src.widgets.download_progress import DownloadProgress
from src.widgets.download_history import DownloadHistoryWidget
from src.widgets.file_exists_dialog import FileExistsDialog
from src.widgets.actor_search_tab import ActorSearchTab


class DownloadThread(QThread):
    def __init__(self, downloader: Downloader, url: str, output_filename: str, direct_url: str | None = None):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_filename = output_filename
        self.direct_url = direct_url

    def run(self):
        if self.direct_url:
            self.downloader.download_direct(self.direct_url, self.output_filename)
        else:
            self.downloader.download(self.url, self.output_filename)


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

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        # Shared history widget (visible below tabs)
        self.history_widget = DownloadHistoryWidget()
        self.history_widget.setObjectName("download_history")

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.addTab(self._create_bilibili_tab(), "Bilibili 下载")
        self._actor_tab = ActorSearchTab(self.config, self.history_widget)
        self._tabs.addTab(self._actor_tab, "演员搜索")
        layout.addWidget(self._tabs)

        # History (shared, below tabs)
        history_label = QLabel("下载历史")
        history_label.setObjectName("history_label")
        layout.addWidget(history_label)
        layout.addWidget(self.history_widget)

        # Output dir (shared)
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"输出目录：{self.config.output_dir}")
        self.dir_label.setObjectName("dir_label")
        self.change_dir_btn = QPushButton("更改")
        self.change_dir_btn.setObjectName("change_dir_btn")
        self.change_dir_btn.clicked.connect(self._on_change_dir)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.change_dir_btn)
        layout.addLayout(dir_layout)

        layout.addStretch()

        self.url_input.returnPressed.connect(self._on_download_clicked)

    def _create_bilibili_tab(self) -> QWidget:
        """Build the Bilibili download tab content."""
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setSpacing(10)

        # URL input row
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入 Bilibili 视频链接或 BV号...")
        self.download_btn = QPushButton("下载")
        self.download_btn.clicked.connect(self._on_download_clicked)
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.download_btn)
        tab_layout.addLayout(input_layout)

        # Video info panel
        self.info_panel = VideoInfoPanel()
        tab_layout.addWidget(self.info_panel)

        # Progress
        self.progress_widget = DownloadProgress()
        tab_layout.addWidget(self.progress_widget)

        tab_layout.addStretch()
        return tab

    def _on_change_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录", self.config.output_dir)
        if folder:
            self.config.output_dir = folder
            self.dir_label.setText(f"输出目录：{folder}")

    @pyqtSlot()
    def _on_download_clicked(self):
        raw = self.url_input.text().strip()
        if not raw:
            return

        self.download_btn.setEnabled(False)
        self.progress_widget.set_idle()

        try:
            self.current_video_info = self.parser.parse(raw)
            self.info_panel.set_video_info(self.current_video_info)
            self._start_download()
        except InvalidVideoURLError as e:
            QMessageBox.warning(self, "解析失败", str(e))
            self.download_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"解析时发生错误：{str(e)}")
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
        url = f"https://www.bilibili.com/video/{bv_id}"
        direct_url = getattr(self.current_video_info, 'direct_url', None)

        self.downloader = Downloader(self.config.output_dir)
        self.downloader.progress_changed.connect(self._on_progress)
        self.downloader.state_changed.connect(self._on_state)
        self.downloader.finished.connect(self._on_finished)
        self.downloader.error.connect(self._on_error)

        self.download_thread = DownloadThread(
            self.downloader, url, self.current_video_info.output_filename, direct_url
        )
        self.download_thread.start()

    @pyqtSlot(float, str, str)
    def _on_progress(self, percent, speed, size):
        self.progress_widget.set_downloading(percent, speed, size)

    @pyqtSlot(str)
    def _on_state(self, state):
        pass

    @pyqtSlot(str)
    def _on_finished(self, path):
        self.progress_widget.set_finished()
        source_site = getattr(self.current_video_info, 'source_site', 'bilibili')
        self.history_widget.add_entry(
            self.current_video_info.title,
            self.current_video_info.bv_id,
            "finished",
            source_site=source_site,
        )
        self.download_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_error(self, message):
        self.progress_widget.set_error(message)
        source_site = getattr(self.current_video_info, 'source_site', 'bilibili') if self.current_video_info else 'bilibili'
        self.history_widget.add_entry(
            self.current_video_info.title if self.current_video_info else "未知",
            self.current_video_info.bv_id if self.current_video_info else "",
            "error",
            source_site=source_site,
        )
        self.download_btn.setEnabled(True)

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
                self, "确认退出",
                "下载进行中，确定退出？",
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()
