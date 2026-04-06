import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QHBoxLayout, QLabel, QPushButton, QProgressBar
)
from PyQt6.QtCore import Qt

from src.i18n import _


@dataclass
class DownloadItem:
    """Represents a single download item in the list."""
    id: str  # unique key (bv_id or video_id)
    title: str  # display name
    output_filename: str
    source_site: str  # "bilibili", "youtube", "missav"
    state: str = "pending"  # "pending", "downloading", "finished", "error"
    progress: float = 0.0  # 0.0 - 100.0
    speed: str = ""  # e.g. "1.2MB/s"
    size_str: str = ""  # e.g. "10.5MB / 50.0MB"
    file_path: str | None = None
    added_at: datetime = field(default_factory=datetime.now)
    error_message: str | None = None


class _ListItemWidget(QWidget):
    """Internal widget representing a single row in the download list."""

    def __init__(self, item: DownloadItem, parent=None):
        super().__init__(parent)
        self._item = item
        self._open_btn: QPushButton | None = None
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        # Title label
        self._title_label = QLabel(self._item.title)
        self._title_label.setObjectName("download_item_title")
        self._title_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(self._title_label, 1)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(int(self._item.progress))
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedWidth(120)
        layout.addWidget(self._progress_bar)

        # Speed label
        self._speed_label = QLabel(self._item.speed)
        self._speed_label.setObjectName("download_item_speed")
        self._speed_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self._speed_label.setFixedWidth(80)
        layout.addWidget(self._speed_label)

        # Open button (visible only when finished)
        self._open_btn = QPushButton(_("Open"))
        self._open_btn.setFixedSize(50, 24)
        self._open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._open_btn.clicked.connect(self._on_open_clicked)
        self._open_btn.setVisible(self._item.state == "finished" and self._item.file_path)
        layout.addWidget(self._open_btn)

        self._update_state_style()

    def _update_state_style(self):
        """Update appearance based on state."""
        if self._item.state == "downloading":
            self._title_label.setStyleSheet("color: #2196F3;")
        elif self._item.state == "finished":
            self._title_label.setStyleSheet("color: #4CAF50;")
        elif self._item.state == "error":
            self._title_label.setStyleSheet("color: #F44336;")
        else:
            self._title_label.setStyleSheet("")

    def _on_open_clicked(self):
        """Open the downloaded file."""
        if self._item.file_path and os.path.exists(self._item.file_path):
            file_path = os.path.normpath(self._item.file_path)
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # macOS / Linux
                subprocess.run(
                    ["open", file_path] if sys.platform == "darwin" else ["xdg-open", file_path]
                )

    def update(self, item: DownloadItem):
        """Update the widget with new item data."""
        self._item = item
        self._title_label.setText(item.title)
        self._progress_bar.setValue(int(item.progress))
        self._speed_label.setText(item.speed)
        if self._open_btn:
            self._open_btn.setVisible(item.state == "finished" and item.file_path is not None)
        self._update_state_style()


class DownloadListWidget(QWidget):
    """
    Unified download list widget showing name, progress, speed per item.
    Completed items show an "Open" button.
    List sorted by date (desc), then name (asc).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: dict[str, DownloadItem] = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list_widget = QListWidget()
        self._list_widget.setObjectName("download_list")
        layout.addWidget(self._list_widget)

    def add_item(self, item: DownloadItem) -> None:
        """Add a new download item to the list."""
        self._items[item.id] = item
        self._sort_and_refresh()

    def update_item(self, id: str, **kwargs) -> None:
        """Update an existing download item with new values."""
        if id not in self._items:
            return
        item = self._items[id]
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        self._sort_and_refresh()

    def remove_item(self, id: str) -> None:
        """Remove a download item from the list."""
        if id in self._items:
            del self._items[id]
            self._sort_and_refresh()

    def get_item(self, id: str) -> DownloadItem | None:
        """Get a download item by id."""
        return self._items.get(id)

    def _sort_and_refresh(self) -> None:
        """Sort items and rebuild the list widget."""
        # Sort by added_at DESC, then title ASC
        sorted_items = sorted(
            self._items.values(),
            key=lambda x: (-x.added_at.timestamp(), x.title.lower())
        )

        # Build a mapping of item id to list widget items
        existing_items = {}
        for i in range(self._list_widget.count()):
            lw_item = self._list_widget.item(i)
            widget = self._list_widget.itemWidget(lw_item)
            if isinstance(widget, _ListItemWidget):
                existing_items[widget._item.id] = (lw_item, widget)

        # Rebuild list preserving existing widgets where possible
        self._list_widget.clear()
        for item in sorted_items:
            lw_item = QListWidgetItem()
            if item.id in existing_items:
                _, existing_widget = existing_items[item.id]
                existing_widget.update(item)
                widget = existing_widget
            else:
                widget = _ListItemWidget(item)
            lw_item.setSizeHint(widget.sizeHint())
            self._list_widget.addItem(lw_item)
            self._list_widget.setItemWidget(lw_item, widget)
