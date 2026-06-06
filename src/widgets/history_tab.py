import os
import subprocess
import sys
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.config import Config
from src.download_history import DownloadHistory
from src.i18n import _


class HistoryTab(QWidget):
    """Tab for viewing and managing download history."""

    def __init__(self, config: Config, history: DownloadHistory, download_list, parent=None):
        super().__init__(parent)
        self._config = config
        self._history = history
        self._download_list = download_list
        self._current_filter = "all"
        self._init_ui()
        self._load_records()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Top controls
        controls_layout = QHBoxLayout()

        # Filter dropdown
        filter_label = QLabel(_("Filter") + ":")
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            _("All"),
            _("Finished"),
            _("Paused"),
            _("Error")
        ])
        self._filter_combo.currentTextChanged.connect(self._on_filter_changed)

        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(_("Search") + "...")
        self._search_input.textChanged.connect(self._on_search_changed)

        # Refresh button
        self._refresh_btn = QPushButton(_("Refresh"))
        self._refresh_btn.clicked.connect(self._load_records)

        # Cleanup button
        self._cleanup_btn = QPushButton(_("Cleanup Orphaned"))
        self._cleanup_btn.clicked.connect(self._on_cleanup_clicked)

        controls_layout.addWidget(filter_label)
        controls_layout.addWidget(self._filter_combo)
        controls_layout.addWidget(self._search_input)
        controls_layout.addStretch()
        controls_layout.addWidget(self._refresh_btn)
        controls_layout.addWidget(self._cleanup_btn)

        layout.addLayout(controls_layout)

        # Results label
        self._results_label = QLabel("")
        layout.addWidget(self._results_label)

        # History table
        self._table = QTableWidget()
        self._table.setObjectName("history_table")
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels([
            _("Title"),
            _("Site"),
            _("State"),
            _("Progress"),
            _("Added"),
            _("Actions")
        ])
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)

        header = self._table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(1, 80)
        self._table.setColumnWidth(2, 80)
        self._table.setColumnWidth(3, 80)
        self._table.setColumnWidth(4, 150)
        self._table.setColumnWidth(5, 200)

        layout.addWidget(self._table)

    def _on_filter_changed(self, text: str):
        """Handle filter dropdown change."""
        filter_map = {
            _("All"): "all",
            _("Finished"): "finished",
            _("Paused"): "paused",
            _("Error"): "error"
        }
        self._current_filter = filter_map.get(text, "all")
        self._load_records()

    def _on_search_changed(self, text: str):
        """Handle search input change."""
        self._load_records()

    def _load_records(self):
        """Load and display records based on current filter and search."""
        self._table.setRowCount(0)

        # Get records based on filter
        if self._current_filter == "all":
            records = self._history.get_all_records(limit=1000)
        elif self._current_filter == "finished":
            records = self._history.get_finished_downloads()
        elif self._current_filter == "paused":
            records = self._history.get_by_state("paused")
        elif self._current_filter == "error":
            records = self._history.get_failed_downloads()
        else:
            records = self._history.get_all_records(limit=1000)

        # Apply search filter
        search_text = self._search_input.text().strip().lower()
        if search_text:
            records = [r for r in records if search_text in r['title'].lower()]

        # Display records
        for record in records:
            self._add_record_row(record)

        # Update results label
        self._results_label.setText(f"{len(records)} {_('records')}")

    def _add_record_row(self, record: dict):
        """Add a record to the table."""
        row = self._table.rowCount()
        self._table.insertRow(row)

        # Title
        title_item = QTableWidgetItem(record['title'])
        title_item.setToolTip(record['title'])
        self._table.setItem(row, 0, title_item)

        # Site
        site_item = QTableWidgetItem(record['source_site'])
        site_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 1, site_item)

        # State
        state_map = {
            "finished": _("Finished"),
            "paused": _("Paused"),
            "error": _("Error"),
            "downloading": _("Downloading"),
            "pending": "Pending"
        }
        state_text = state_map.get(record['state'], record['state'])
        state_item = QTableWidgetItem(state_text)
        state_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 2, state_item)

        # Progress
        progress_text = f"{int(record['progress'])}%"
        progress_item = QTableWidgetItem(progress_text)
        progress_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 3, progress_item)

        # Added time
        added_dt = datetime.fromtimestamp(record['added_at'])
        time_text = self._format_time(added_dt)
        time_item = QTableWidgetItem(time_text)
        time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 4, time_item)

        # Actions
        actions_widget = self._create_actions_widget(record)
        self._table.setCellWidget(row, 5, actions_widget)

        self._table.setRowHeight(row, 40)

    def _create_actions_widget(self, record: dict) -> QWidget:
        """Create action buttons for a record."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        state = record['state']
        item_id = record['id']

        # Open button (for finished downloads)
        if state == "finished":
            open_btn = QPushButton(_("Open"))
            open_btn.setFixedHeight(28)
            open_btn.clicked.connect(lambda: self._on_open_clicked(record))
            layout.addWidget(open_btn)

        # Resume button (for paused downloads)
        if state == "paused":
            resume_btn = QPushButton(_("Resume"))
            resume_btn.setFixedHeight(28)
            resume_btn.clicked.connect(lambda: self._on_resume_clicked(record))
            layout.addWidget(resume_btn)

        # Retry button (for failed downloads)
        if state == "error":
            retry_btn = QPushButton(_("Retry"))
            retry_btn.setFixedHeight(28)
            retry_btn.clicked.connect(lambda: self._on_retry_clicked(record))
            layout.addWidget(retry_btn)

        # Delete button (always available)
        delete_btn = QPushButton(_("Delete Record"))
        delete_btn.setFixedHeight(28)
        delete_btn.clicked.connect(lambda: self._on_delete_clicked(record))
        layout.addWidget(delete_btn)

        layout.addStretch()
        return widget

    def _format_time(self, dt: datetime) -> str:
        """Format datetime for display."""
        now = datetime.now()
        diff = now - dt

        if diff.days == 0:
            if diff.seconds < 60:
                return _("Just now")
            elif diff.seconds < 3600:
                return f"{diff.seconds // 60}m ago"
            else:
                return f"{diff.seconds // 3600}h ago"
        elif diff.days == 1:
            return _("Yesterday")
        elif diff.days < 7:
            return f"{diff.days}d ago"
        else:
            return dt.strftime("%Y-%m-%d")

    def _on_open_clicked(self, record: dict):
        """Open the downloaded file."""
        file_path = record.get('file_path')
        if not file_path or not os.path.exists(file_path):
            # Try constructing path from output_dir
            file_path = os.path.join(self._config.output_dir, record['output_filename'])
            if not os.path.exists(file_path):
                QMessageBox.warning(
                    self,
                    _("Error"),
                    _("File not found, cannot resume")
                )
                return

        file_path = os.path.normpath(file_path)
        if os.name == "nt":
            os.startfile(file_path)
        elif os.name == "posix":
            subprocess.run(
                ["open", file_path] if sys.platform == "darwin" else ["xdg-open", file_path]
            )

    def _on_resume_clicked(self, record: dict):
        """Resume a paused download."""
        # Add to download list if not already there
        if self._download_list:
            from src.widgets.download_list_widget import DownloadItem
            from datetime import datetime

            item = DownloadItem(
                id=record['id'],
                title=record['title'],
                output_filename=record['output_filename'],
                source_site=record['source_site'],
                state="paused",
                progress=record['progress'],
                speed="",
                size_str=record['size_str'],
                file_path=record.get('file_path'),
                direct_url=record.get('direct_url'),
                is_playing=False,
                added_at=datetime.fromtimestamp(record['added_at']),
                error_message=None
            )

            # Check if item already exists in download list
            existing = self._download_list.get_item(record['id'])
            if not existing:
                self._download_list.add_item(item)

            QMessageBox.information(
                self,
                _("Resume"),
                _("Download added to queue. Click Resume in the download list to continue.")
            )

    def _on_retry_clicked(self, record: dict):
        """Retry a failed download."""
        QMessageBox.information(
            self,
            _("Retry"),
            _("Please search and download again from the main tab.")
        )

    def _on_delete_clicked(self, record: dict):
        """Delete a record from history."""
        reply = QMessageBox.question(
            self,
            _("Confirm Delete"),
            _("Are you sure you want to delete this record?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._history.delete_record(record['id'])
            self._load_records()
            QMessageBox.information(self, _("Success"), _("Record deleted"))

    def _on_cleanup_clicked(self):
        """Clean up orphaned records (files deleted but records remain)."""
        cleaned = self._history.cleanup_orphaned_records(self._config.output_dir)

        if cleaned > 0:
            QMessageBox.information(
                self,
                _("Cleanup complete"),
                f"{cleaned} {_('records cleaned')}"
            )
            self._load_records()
        else:
            QMessageBox.information(
                self,
                _("Cleanup complete"),
                _("No orphaned records found")
            )
