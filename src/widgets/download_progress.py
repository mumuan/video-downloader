from PyQt6.QtWidgets import QWidget, QVBoxLayout, QProgressBar, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt

class DownloadProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("download_progress")
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self.status_label = QLabel("等待下载...")
        self.status_label.setObjectName("status_label")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        speed_layout = QHBoxLayout()
        speed_layout.setSpacing(12)
        self.speed_label = QLabel("")
        self.speed_label.setObjectName("speed_label")
        self.size_label = QLabel("")
        self.size_label.setObjectName("size_label")
        speed_layout.addWidget(self.speed_label)
        speed_layout.addWidget(self.size_label)
        speed_layout.addStretch()
        layout.addLayout(speed_layout)

    def set_idle(self):
        self.status_label.setText("等待下载...")
        self.status_label.setStyleSheet("color: #888;")
        self.progress_bar.setValue(0)
        self.speed_label.setText("")
        self.size_label.setText("")

    def set_downloading(self, percent: float, speed: str, size: str):
        self.status_label.setText("下载中...")
        self.status_label.setStyleSheet("color: #2196F3;")
        self.progress_bar.setValue(int(percent))
        self.speed_label.setText(speed)
        self.size_label.setText(size)

    def set_finished(self):
        self.status_label.setText("下载完成")
        self.status_label.setStyleSheet("color: #4CAF50;")
        self.progress_bar.setValue(100)
        self.speed_label.setText("")
        self.size_label.setText("")

    def set_error(self, message: str):
        self.status_label.setText(f"下载失败：{message}")
        self.status_label.setStyleSheet("color: #F44336;")
        self.progress_bar.setValue(0)
