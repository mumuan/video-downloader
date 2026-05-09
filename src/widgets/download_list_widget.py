import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


@dataclass
class DownloadItem:
    id: str
    title: str
    output_filename: str
    source_site: str  # "bilibili", "youtube", "missav"
    state: str = "pending"  # "pending", "downloading", "paused", "finished", "error", "playing"
    progress: float = 0.0  # 0.0 - 100.0
    speed: str = ""  # e.g. "1.2MB/s"
    size_str: str = ""  # e.g. "10.5MB / 50.0MB"
    file_path: str | None = None
    direct_url: str | None = None
    is_playing: bool = False
    added_at: datetime = field(default_factory=datetime.now)
    error_message: str | None = None


class _NameProgressWidget(QWidget):
    def __init__(self, title: str, progress: float = 0.0, parent=None):
        super().__init__(parent)
        self._title = title
        self._progress = progress
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self._name_label = QLabel(self._title)
        self._name_label.setObjectName("download_item_name")
        self._name_label.setToolTip(self._title)
        self._name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_layout.addWidget(self._name_label, stretch=1)

        self._percent_label = QLabel("0%")
        self._percent_label.setObjectName("download_item_percent")
        self._percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._percent_label.setFixedWidth(42)
        top_layout.addWidget(self._percent_label)

        layout.addLayout(top_layout)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName("download_progress_bar")
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(int(self._progress))
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(8)
        layout.addWidget(self._progress_bar)

    def set_progress(self, progress: float):
        self._progress = progress
        self._percent_label.setText(f"{int(progress)}%")
        self._progress_bar.setValue(max(0, min(100, int(progress))))

    def set_title(self, title: str):
        self._title = title
        self._name_label.setText(title)
        self._name_label.setToolTip(title)

    def sizeHint(self) -> QSize:
        return QSize(220, 48)


class _StatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._status_label = QLabel()
        self._status_label.setObjectName("download_status_badge")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_label)

        self._meta_label = QLabel()
        self._meta_label.setObjectName("download_status_meta")
        self._meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._meta_label)

    def update_from_item(self, item: DownloadItem):
        self._status_label.setText(self._status_text(item))
        self._status_label.setProperty("status", item.state)
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)
        self._meta_label.setText(self._meta_text(item))

    @staticmethod
    def _status_text(item: DownloadItem) -> str:
        mapping = {
            "pending": "Pending",
            "downloading": "Downloading",
            "paused": "Paused",
            "finished": "Finished",
            "error": "Error",
        }
        base = mapping.get(item.state, item.state.title())
        if item.is_playing:
            return f"{base} · Preview"
        return base

    @staticmethod
    def _meta_text(item: DownloadItem) -> str:
        if item.state == "error" and item.error_message:
            return item.error_message
        if item.speed:
            return item.speed
        if item.state == "finished":
            return "Ready"
        if item.state == "paused":
            return "Can resume"
        return "Waiting"


class _ActionWidget(QWidget):
    def __init__(self, item_id: str, callback, parent=None):
        super().__init__(parent)
        self._item_id = item_id
        self._callback = callback

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._main_btn = QPushButton()
        self._main_btn.setObjectName("download_action_btn")
        self._main_btn.setFixedHeight(28)
        self._main_btn.clicked.connect(self._on_main_clicked)
        layout.addWidget(self._main_btn)

        self._preview_btn = QPushButton()
        self._preview_btn.setObjectName("download_preview_btn")
        self._preview_btn.setFixedHeight(28)
        self._preview_btn.clicked.connect(self._on_preview_clicked)
        layout.addWidget(self._preview_btn)

        self._item: DownloadItem | None = None

    def bind_item(self, item: DownloadItem):
        self._item = item

        main_text = ""
        preview_text = "Preview"

        if item.state == "downloading":
            main_text = "Pause"
        elif item.state == "paused":
            main_text = "Resume"
        elif item.state == "finished":
            main_text = "Open"

        can_preview = (
            item.state in {"downloading", "paused", "finished"}
            or bool(item.file_path)
        )
        if item.is_playing:
            preview_text = "Stop"

        self._main_btn.setText(main_text)
        self._main_btn.setVisible(bool(main_text))
        self._preview_btn.setText(preview_text)
        self._preview_btn.setVisible(can_preview)

    def _on_main_clicked(self):
        if self._item is None or self._callback is None:
            return

        if self._item.state == "downloading":
            self._callback(self._item_id, "pause")
        elif self._item.state == "paused":
            self._callback(self._item_id, "resume")
        elif self._item.state == "finished":
            self._open_file(self._item.file_path)

    def _on_preview_clicked(self):
        if self._item is None or self._callback is None:
            return
        if self._item.is_playing:
            self._callback(self._item_id, "stop_play")
        else:
            self._callback(self._item_id, "play")

    @staticmethod
    def _open_file(file_path: str | None):
        if file_path is None or not os.path.exists(file_path):
            return

        file_path = os.path.normpath(file_path)
        if os.name == "nt":
            os.startfile(file_path)
        elif os.name == "posix":
            subprocess.run(
                ["open", file_path] if sys.platform == "darwin" else ["xdg-open", file_path]
            )


class DownloadListWidget(QWidget):
    def __init__(self, parent=None, action_callback=None):
        super().__init__(parent)
        self._items: dict[str, DownloadItem] = {}
        self._name_progress_widgets: dict[str, _NameProgressWidget] = {}
        self._status_widgets: dict[str, _StatusWidget] = {}
        self._action_widgets: dict[str, _ActionWidget] = {}
        self._row_for_id: dict[str, int] = {}
        self._action_callback = action_callback
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._table = QTableWidget()
        self._table.setObjectName("download_list")
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Video", "Status", "Size", "Actions"])
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setShowGrid(False)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 160)
        self._table.setColumnWidth(2, 170)
        self._table.setColumnWidth(3, 210)

        layout.addWidget(self._table)

    def add_item(self, item: DownloadItem):
        self._items[item.id] = item
        self._insert_row(item)

    def update_item(self, item_id: str, **kwargs):
        item = self._items.get(item_id)
        if item is None:
            return
        for key, value in kwargs.items():
            if hasattr(item, key):
                setattr(item, key, value)
        self._update_row(item)

    def get_item(self, item_id: str) -> DownloadItem | None:
        return self._items.get(item_id)

    def _find_row_by_id(self, item_id: str) -> int:
        return self._row_for_id.get(item_id, -1)

    def _insert_row(self, item: DownloadItem):
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._row_for_id[item.id] = row

        name_widget = _NameProgressWidget(item.title, item.progress)
        self._table.setCellWidget(row, 0, name_widget)
        self._name_progress_widgets[item.id] = name_widget

        status_widget = _StatusWidget()
        status_widget.update_from_item(item)
        self._table.setCellWidget(row, 1, status_widget)
        self._status_widgets[item.id] = status_widget

        size_label = QLabel(item.size_str)
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        size_label.setObjectName("download_size_label")
        self._table.setCellWidget(row, 2, size_label)

        action_widget = _ActionWidget(item.id, self._action_callback)
        action_widget.bind_item(item)
        self._table.setCellWidget(row, 3, action_widget)
        self._action_widgets[item.id] = action_widget

        self._table.setRowHeight(row, 56)

    def _update_row(self, item: DownloadItem):
        row = self._find_row_by_id(item.id)
        if row < 0:
            return

        name_widget = self._name_progress_widgets.get(item.id)
        if name_widget is not None:
            name_widget.set_title(item.title)
            name_widget.set_progress(item.progress)

        status_widget = self._status_widgets.get(item.id)
        if status_widget is not None:
            status_widget.update_from_item(item)

        size_widget = self._table.cellWidget(row, 2)
        if isinstance(size_widget, QLabel):
            size_widget.setText(item.size_str)

        # Update open button
        if item.id in self._open_buttons:
            open_btn = self._open_buttons[item.id]
            open_btn.setText(self._button_text_for_state(item.state))
            open_btn.setVisible(item.state != "pending")

    def _button_text_for_state(self, state: str) -> str:
        """Return button text based on item state."""
        if state == "downloading":
            return _("暂停")
        elif state == "paused":
            return _("继续")
        elif state == "finished":
            return _("打开")
        elif state == "playing":
            return _("停止")
        return ""

    def _on_action_clicked(self, item_id: str) -> None:
        """Route button click to appropriate action."""
        item = self._items.get(item_id)
        if not item:
            return
        if item.state == "downloading":
            self._action_callback(item_id, "pause")
        elif item.state == "paused":
            self._action_callback(item_id, "resume")
        elif item.state == "finished":
            self._open_file(item.file_path)
        elif item.state == "playing":
            self._action_callback(item_id, "stop_play")

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
