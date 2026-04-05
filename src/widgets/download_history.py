from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt

class DownloadHistoryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

    def add_entry(self, title: str, bv_id: str, state: str, size: str = ""):
        text = f"{'✅' if state == 'finished' else '❌'} {title} ({bv_id})"
        if size:
            text += f" — {size}"
        item = QListWidgetItem(text)
        self.list_widget.insertItem(0, item)

    def clear_history(self):
        self.list_widget.clear()