from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
from src.video_info import VideoInfo
from src.i18n import _
import urllib.request


class _ThumbnailLoader(QThread):
    loaded = pyqtSignal(QPixmap)

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            with urllib.request.urlopen(self._url, timeout=10) as response:
                data = response.read()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.loaded.emit(pixmap)
        except Exception:
            pass


class VideoInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("video_info_panel")
        self._thumbnail_loader: _ThumbnailLoader | None = None
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.title_label = QLabel(_("No video info"))
        self.title_label.setObjectName("video_title")
        layout.addWidget(self.title_label)

        meta_layout = QHBoxLayout()
        self.bv_label = QLabel("")
        self.bv_label.setObjectName("video_meta")
        self.duration_label = QLabel("")
        self.duration_label.setObjectName("video_meta")
        meta_layout.addWidget(self.bv_label)
        meta_layout.addWidget(self.duration_label)
        meta_layout.addStretch()
        layout.addLayout(meta_layout)

        thumbnail_container = QWidget()
        thumbnail_container.setObjectName("thumbnail_container")
        thumbnail_layout = QVBoxLayout(thumbnail_container)
        thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setObjectName("thumbnail_label")
        self.thumbnail_label.setFixedSize(160, 90)
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail_layout.addWidget(self.thumbnail_label)
        layout.addWidget(thumbnail_container)

        self.filename_label = QLabel("")
        self.filename_label.setObjectName("filename_label")
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label)

        self._clear()

    def _clear(self):
        self.title_label.setText(_("No video info"))
        self.bv_label.setText("")
        self.duration_label.setText("")
        self.thumbnail_label.setText(_("No thumbnail"))
        self.thumbnail_label.setPixmap(QPixmap())
        self.filename_label.setText("")

    def set_video_info(self, info: VideoInfo):
        self.title_label.setText(info.title)
        self.bv_label.setText(f"{_("BV: ")}{info.bv_id}")
        self.duration_label.setText(f"{_("Duration: ")}{info.formatted_duration}")
        self.filename_label.setText(f"{_("Filename: ")}{info.output_filename}")
        self._load_thumbnail(info.thumbnail)

    def _load_thumbnail(self, url: str):
        if not url:
            self.thumbnail_label.setText(_("No thumbnail"))
            self.thumbnail_label.setPixmap(QPixmap())
            return
        self.thumbnail_label.setText(_("Loading thumbnail..."))
        self.thumbnail_label.setPixmap(QPixmap())
        if self._thumbnail_loader:
            self._thumbnail_loader.deleteLater()
            self._thumbnail_loader = None
        self._thumbnail_loader = _ThumbnailLoader(url, self)
        self._thumbnail_loader.loaded.connect(self._on_thumbnail_loaded)
        self._thumbnail_loader.start()

    def _on_thumbnail_loaded(self, pixmap: QPixmap):
        scaled = pixmap.scaled(160, 90, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.thumbnail_label.setPixmap(scaled)
