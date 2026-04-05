from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from src.video_info import VideoInfo
import urllib.request

class VideoInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.title_label = QLabel("暂无视频信息")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.title_label)

        meta_layout = QHBoxLayout()
        self.bv_label = QLabel("")
        self.duration_label = QLabel("")
        meta_layout.addWidget(self.bv_label)
        meta_layout.addWidget(self.duration_label)
        meta_layout.addStretch()
        layout.addLayout(meta_layout)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(160, 90)
        self.thumbnail_label.setStyleSheet("border: 1px solid #ccc; background: #f0f0f0;")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.thumbnail_label)

        self.filename_label = QLabel("")
        self.filename_label.setStyleSheet("color: #666; font-size: 12px;")
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label)

        self._clear()

    def _clear(self):
        self.title_label.setText("暂无视频信息")
        self.bv_label.setText("")
        self.duration_label.setText("")
        self.thumbnail_label.setText("无封面")
        self.thumbnail_label.setPixmap(QPixmap())
        self.filename_label.setText("")

    def set_video_info(self, info: VideoInfo):
        self.title_label.setText(info.title)
        self.bv_label.setText(f"BV号：{info.bv_id}")
        self.duration_label.setText(f"时长：{info.formatted_duration}")
        self.filename_label.setText(f"文件名：{info.output_filename}")
        self._load_thumbnail(info.thumbnail)

    def _load_thumbnail(self, url: str):
        if not url:
            self.thumbnail_label.setText("无封面")
            return
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = response.read()
            pixmap = QPixmap()
            if not pixmap.loadFromData(data):
                self.thumbnail_label.setText("封面加载失败")
                return
            scaled = pixmap.scaled(160, 90, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled)
        except Exception:
            self.thumbnail_label.setText("封面加载失败")
