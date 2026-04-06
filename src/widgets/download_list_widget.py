import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHBoxLayout, QLabel, QPushButton, QProgressBar, QHeaderView,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor

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


class _NameProgressWidget(QWidget):
    """Combined widget showing name, percentage and progress bar."""

    def __init__(self, title: str, progress: float = 0.0, parent=None):
        super().__init__(parent)
        self._title = title
        self._progress = progress
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)

        # Top row: name + percentage
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self._name_label = QLabel(self._title)
        self._name_label.setObjectName("download_item_name")
        self._name_label.setToolTip(self._title)
        self._name_label.setStyleSheet("color: #1e293b;")
        self._name_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        top_layout.addWidget(self._name_label, stretch=1)

        self._percent_label = QLabel("0%")
        self._percent_label.setObjectName("download_item_percent")
        self._percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._percent_label.setFixedWidth(40)
        self._percent_label.setStyleSheet("color: #64748b;")
        top_layout.addWidget(self._percent_label)

        layout.addLayout(top_layout)

        # Bottom: progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(int(self._progress))
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setObjectName("download_progress_bar")
        layout.addWidget(self._progress_bar)

    def set_progress(self, progress: float) -> None:
        self._progress = progress
        self._percent_label.setText(f"{int(progress)}%")
        self._progress_bar.setValue(int(progress))

    def set_title(self, title: str) -> None:
        self._title = title
        self._name_label.setText(title)
        self._name_label.setToolTip(title)

    def sizeHint(self) -> QSize:
        return QSize(200, 44)


class DownloadListWidget(QWidget):
    """
    Table-style download list widget with columns:
    文件名+进度 (name+progress), 大小 (size), 操作 (action)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: dict[str, DownloadItem] = {}
        self._name_progress_widgets: dict[str, _NameProgressWidget] = {}
        self._open_buttons: dict[str, QPushButton] = {}
        self._row_for_id: dict[str, int] = {}  # Track row index for each id
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create table - 3 columns: Name+Progress, Size, Action
        self._table = QTableWidget()
        self._table.setObjectName("download_list")
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([
            _("文件名"), _("大小"), _("操作")
        ])

        # Enable alternating row colors
        self._table.setAlternatingRowColors(True)

        # Header styling
        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Name+Progress stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)   # Size fixed
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)   # Action fixed

        self._table.setColumnWidth(1, 120)  # Size
        self._table.setColumnWidth(2, 70)   # Action

        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setShowGrid(False)

        layout.addWidget(self._table)

    def add_item(self, item: DownloadItem) -> None:
        """Add a new download item to the list."""
        self._items[item.id] = item
        self._insert_row(item)

    def update_item(self, id: str, **kwargs) -> None:
        """Update an existing download item with new values."""
        if id not in self._items:
            return
        item = self._items[id]
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        self._update_row(item)

    def remove_item(self, id: str) -> None:
        """Remove a download item from the list."""
        if id in self._items:
            del self._items[id]
            self._remove_row(id)

    def get_item(self, id: str) -> DownloadItem | None:
        """Get a download item by id."""
        return self._items.get(id)

    def _find_row_by_id(self, id: str) -> int:
        """Find the row index for a given item id."""
        return self._row_for_id.get(id, -1)

    def _insert_row(self, item: DownloadItem) -> None:
        """Insert a new row for the item."""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._row_for_id[item.id] = row

        # Column 0: Name+Progress (as widget)
        name_progress_widget = _NameProgressWidget(item.title, item.progress)
        self._table.setCellWidget(row, 0, name_progress_widget)
        self._name_progress_widgets[item.id] = name_progress_widget

        # Column 1: Size
        size_label = QLabel(item.size_str)
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_label.setObjectName("download_size_label")
        self._table.setCellWidget(row, 1, size_label)

        # Column 2: Action button
        open_btn = QPushButton(_("打开"))
        open_btn.setFixedSize(50, 24)
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.setObjectName("download_open_btn")
        open_btn.clicked.connect(lambda: self._open_file(item.file_path) if item.file_path else None)
        open_btn.setVisible(item.state == "finished" and item.file_path)
        self._table.setCellWidget(row, 2, open_btn)
        self._open_buttons[item.id] = open_btn

        # Set row height
        self._table.setRowHeight(row, 44)

    def _update_row(self, item: DownloadItem) -> None:
        """Update an existing row with new values."""
        row = self._find_row_by_id(item.id)
        if row < 0:
            return

        # Update name+progress widget
        if item.id in self._name_progress_widgets:
            widget = self._name_progress_widgets[item.id]
            widget.set_title(item.title)
            widget.set_progress(item.progress)

        # Update size
        size_widget = self._table.cellWidget(row, 1)
        if isinstance(size_widget, QLabel):
            size_widget.setText(item.size_str)

        # Update open button
        if item.id in self._open_buttons:
            open_btn = self._open_buttons[item.id]
            open_btn.setVisible(item.state == "finished" and item.file_path is not None)

    def _remove_row(self, id: str) -> None:
        """Remove a row by item id."""
        row = self._find_row_by_id(id)
        if row >= 0:
            self._table.removeRow(row)
            self._name_progress_widgets.pop(id, None)
            self._open_buttons.pop(id, None)
            self._row_for_id.pop(id, None)
            # Update row indices for ids that shifted
            for remaining_id, old_row in list(self._row_for_id.items()):
                if old_row > row:
                    self._row_for_id[remaining_id] = old_row - 1

    def _open_file(self, file_path: str | None) -> None:
        """Open the downloaded file."""
        if file_path and os.path.exists(file_path):
            file_path = os.path.normpath(file_path)
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # macOS / Linux
                subprocess.run(
                    ["open", file_path] if sys.platform == "darwin" else ["xdg-open", file_path]
                )

    def setFixedHeight(self, height: int) -> None:
        """Override to set table height."""
        super().setFixedHeight(height)
        self._table.setFixedHeight(height)
