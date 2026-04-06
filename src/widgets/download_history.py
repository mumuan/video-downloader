from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


class DownloadHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

    def add_entry(self, title: str, bv_id: str, state: str, size: str = "", source_site: str = "bilibili"):
        item = QListWidgetItem()
        self.list_widget.insertItem(0, item)

        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(4, 6, 8, 6)
        container_layout.setSpacing(10)

        status_dot = QWidget()
        status_dot.setObjectName("status_dot")
        if state == "finished":
            status_dot.setProperty("class", "success")
        else:
            status_dot.setProperty("class", "error")
        status_dot.setFixedSize(8, 8)

        site_tag = f"[{source_site}] " if source_site != "bilibili" else ""
        title_text = f"{site_tag}{title}"
        title_label = QLabel(title_text)
        title_label.setObjectName("history_title")

        bv_label = QLabel(f"({bv_id})")
        bv_label.setObjectName("history_bv")

        if size:
            size_label = QLabel(f"— {size}")
            size_label.setObjectName("history_size")
            container_layout.addWidget(size_label)

        container_layout.addWidget(status_dot)
        container_layout.addWidget(title_label, 1)
        container_layout.addWidget(bv_label)

        item.setSizeHint(container.sizeHint())
        self.list_widget.setItemWidget(item, container)
