# src/main_window.py
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSlot
from src.video_parser import VideoParser, InvalidVideoURLError
from src.downloader import Downloader, DownloadState
from src.config import Config
from src.video_info import VideoInfo
from src.widgets.video_info_panel import VideoInfoPanel
from src.widgets.download_progress import DownloadProgress
from src.widgets.download_history import DownloadHistoryWidget
from src.widgets.file_exists_dialog import FileExistsDialog


class DownloadThread(QThread):
    def __init__(self, downloader: Downloader, url: str, output_filename: str):
        super().__init__()
        self.downloader = downloader
        self.url = url
        self.output_filename = output_filename

    def run(self):
        self.downloader.download(self.url, self.output_filename)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bilibili 视频下载器")
        self.setMinimumSize(600, 500)

        app_data = os.path.join(os.path.expanduser("~"), ".bilibili-downloader")
        os.makedirs(app_data, exist_ok=True)
        self.config = Config(app_data)
        self.parser = VideoParser()
        self.current_video_info: VideoInfo | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)

        # URL input row
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入 Bilibili 视频链接或 BV号...")
        self.download_btn = QPushButton("下载")
        self.download_btn.clicked.connect(self._on_download_clicked)
        input_layout.addWidget(self.url_input)
        input_layout.addWidget(self.download_btn)
        layout.addLayout(input_layout)

        # Video info panel
        self.info_panel = VideoInfoPanel()
        layout.addWidget(self.info_panel)

        # Progress
        self.progress_widget = DownloadProgress()
        layout.addWidget(self.progress_widget)

        # History
        history_label = QLabel("下载历史")
        history_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(history_label)
        self.history_widget = DownloadHistoryWidget()
        layout.addWidget(self.history_widget)

        # Output dir
        dir_layout = QHBoxLayout()
        self.dir_label = QLabel(f"输出目录：{self.config.output_dir}")
        self.dir_label.setStyleSheet("color: #666; font-size: 12px;")
        self.change_dir_btn = QPushButton("更改")
        self.change_dir_btn.clicked.connect(self._on_change_dir)
        dir_layout.addWidget(self.dir_label)
        dir_layout.addWidget(self.change_dir_btn)
        layout.addLayout(dir_layout)

        layout.addStretch()

        self.url_input.returnPressed.connect(self._on_download_clicked)

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

        self.downloader = Downloader(self.config.output_dir)
        self.downloader.progress_changed.connect(self._on_progress)
        self.downloader.state_changed.connect(self._on_state)
        self.downloader.finished.connect(self._on_finished)
        self.downloader.error.connect(self._on_error)

        self.download_thread = DownloadThread(self.downloader, url, self.current_video_info.output_filename)
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
        self.history_widget.add_entry(
            self.current_video_info.title,
            self.current_video_info.bv_id,
            "finished"
        )
        self.download_btn.setEnabled(True)

    @pyqtSlot(str)
    def _on_error(self, message):
        self.progress_widget.set_error(message)
        self.history_widget.add_entry(
            self.current_video_info.title if self.current_video_info else "未知",
            self.current_video_info.bv_id if self.current_video_info else "",
            "error"
        )
        self.download_btn.setEnabled(True)
