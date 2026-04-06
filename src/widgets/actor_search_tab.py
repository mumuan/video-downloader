# src/widgets/actor_search_tab.py
import os
from typing import Literal

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QSpinBox,
    QProgressBar, QMessageBox, QAbstractItemView, QStyledItemDelegate,
    QStyleOptionButton, QStyle, QApplication
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize
from typing import Union, Optional
from PyQt6.QtGui import QIcon

from src.search_result import SearchResult
from src.parsers.missav_parser import MissavParser
from src.parsers.session_manager import VideoParseError
from src.download_queue import DownloadQueue
from src.video_info import VideoInfo
from src.config import Config


class _CheckBoxDelegate(QStyledItemDelegate):
    """Delegate that renders a real QCheckBox in the first column."""

    def paint(self, painter, option, index):
        opt = QStyleOptionButton()
        opt.rect = option.rect
        opt.state |= QStyle.StateFlag.State_Enabled
        widget = option.widget
        if widget is not None:
            style = widget.style()
        else:
            style = QApplication.style()
        opt.text = ""
        opt.state |= QStyle.StateFlag.State_On if index.model().data(index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked else QStyle.StateFlag.State_Off
        style.drawControl(QStyle.ControlElement.CE_CheckBox, opt, painter, widget)

    def editorEvent(self, event, model, option, index):
        if event.type() in (event.Type.MouseButtonPress, event.Type.MouseButtonRelease, event.Type.KeyPress):
            current = model.data(index, Qt.ItemDataRole.CheckStateRole)
            new_state = Qt.CheckState.Unchecked if current == Qt.CheckState.Checked else Qt.CheckState.Checked
            model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
            return True
        return super().editorEvent(event, model, option, index)


class SearchWorker(QThread):
    """Background thread for search requests."""
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    page_done = pyqtSignal(int, int)  # current_page, total_pages

    def __init__(self, parser: MissavParser, actor_name: str, page: int):
        super().__init__()
        self._parser = parser
        self._actor_name = actor_name
        self._page = page

    def run(self):
        try:
            results, total_pages = self._parser.search_parse(self._actor_name, self._page)
            self.page_done.emit(self._page, total_pages)
            self.finished.emit(results)
        except VideoParseError as e:
            self.error.emit(str(e))
        except Exception as e:
            self.error.emit(f"搜索失败：{str(e)}")


class ActorSearchTab(QWidget):
    """
    Actor search and batch download Tab.

    Signals:
        download_started(): emitted when batch download begins
        download_entry_finished(title, bv_id, source_site): for history logging
    """

    download_entry_finished = pyqtSignal(str, str, str)  # title, bv_id, source_site

    # State machine values
    SEARCH_IDLE = "idle"
    SEARCH_SEARCHING = "searching"
    DOWNLOAD_EXTRACTING = "extracting"
    DOWNLOAD_DOWNLOADING = "downloading"
    DOWNLOAD_FINISHED = "finished"

    def __init__(self, config: Config, history_widget, parent=None):
        super().__init__(parent)
        self._config = config
        self._history_widget = history_widget
        self._parser = MissavParser()
        self._search_worker: SearchWorker | None = None
        self._download_queue: DownloadQueue | None = None

        # State
        self._search_state = self.SEARCH_IDLE
        self._download_state = self.SEARCH_IDLE
        self._current_page = 1
        self._total_pages = 1
        self._current_actor = ""
        self._checked_ids: set[str] = set()  # cross-page selection persistence
        self._page_results: dict[int, list[SearchResult]] = {}  # page -> results cache
        self._current_results: list[SearchResult] = []  # displayed results
        self._downloaded_ids: set[str] = set()  # pre-populated from history

        self._init_ui()
        self._load_downloaded_ids()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # --- Search row ---
        search_layout = QHBoxLayout()
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("输入演员名字...")
        self._search_input.returnPressed.connect(self._on_search_clicked)
        self._search_input.textChanged.connect(lambda _: self._update_ui_state())
        self._search_btn = QPushButton("搜索")
        self._search_btn.clicked.connect(self._on_search_clicked)
        search_layout.addWidget(self._search_input)
        search_layout.addWidget(self._search_btn)
        layout.addLayout(search_layout)

        # --- Results info label ---
        self._results_label = QLabel("")
        self._results_label.setObjectName("results_label")
        layout.addWidget(self._results_label)

        # --- Results table ---
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["", "封面", "标题", "时长"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(1, 90)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(3, 70)

        # Checkbox delegate for first column
        self._table.setItemDelegateForColumn(0, _CheckBoxDelegate(self._table))
        self._table.itemClicked.connect(self._on_table_item_clicked)

        layout.addWidget(self._table)

        # --- Pagination ---
        page_layout = QHBoxLayout()
        self._prev_btn = QPushButton("上一页")
        self._prev_btn.clicked.connect(self._on_prev_page)
        self._page_label = QLabel("1 / 1")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._next_btn = QPushButton("下一页")
        self._next_btn.clicked.connect(self._on_next_page)
        page_layout.addWidget(self._prev_btn)
        page_layout.addWidget(self._page_label)
        page_layout.addWidget(self._next_btn)
        layout.addLayout(page_layout)

        # --- Download controls ---
        controls_layout = QHBoxLayout()
        self._concurrent_spin = QSpinBox()
        self._concurrent_spin.setRange(1, 5)
        self._concurrent_spin.setValue(self._config.concurrent_downloads)
        self._concurrent_spin.setPrefix("并发 ")
        self._concurrent_spin.valueChanged.connect(self._on_concurrent_changed)
        self._selected_label = QLabel("已选 0 个")
        self._selected_label.setObjectName("selected_label")
        self._download_btn = QPushButton("下载选中")
        self._download_btn.setObjectName("download_btn")
        self._download_btn.clicked.connect(self._on_download_clicked)
        self._select_all_btn = QPushButton("全选")
        self._select_all_btn.clicked.connect(self._on_select_all)
        controls_layout.addWidget(self._concurrent_spin)
        controls_layout.addWidget(self._selected_label)
        controls_layout.addWidget(self._select_all_btn)
        controls_layout.addWidget(self._download_btn)
        layout.addLayout(controls_layout)

        # --- Progress ---
        self._batch_progress = QProgressBar()
        self._batch_progress.setRange(0, 100)
        self._batch_progress.setValue(0)
        self._batch_progress.setVisible(False)
        layout.addWidget(self._batch_progress)

        self._item_progress_label = QLabel("")
        self._item_progress_label.setObjectName("item_progress_label")
        self._item_progress_label.setVisible(False)
        layout.addWidget(self._item_progress_label)

        self._update_ui_state()

    def _load_downloaded_ids(self):
        """Load already-downloaded video IDs from history for skip detection."""
        # Will be populated from history widget if available
        pass

    def _set_search_state(self, state: str):
        self._search_state = state
        self._update_ui_state()

    def _set_download_state(self, state: str):
        self._download_state = state
        self._update_ui_state()

    def _update_ui_state(self):
        """Update widget enabled/disabled states based on current state."""
        # Search controls
        searching = self._search_state == self.SEARCH_SEARCHING
        self._search_input.setEnabled(not searching)
        self._search_btn.setEnabled(not searching and bool(self._search_input.text().strip()))

        # Download controls
        is_downloading = self._download_state in (self.DOWNLOAD_EXTRACTING, self.DOWNLOAD_DOWNLOADING)
        self._download_btn.setEnabled(
            not is_downloading
            and len(self._checked_ids) > 0
            and self._search_state == self.SEARCH_IDLE
        )
        self._concurrent_spin.setEnabled(not is_downloading)
        self._select_all_btn.setEnabled(self._search_state == self.SEARCH_IDLE and bool(self._current_results))

        # Pagination
        self._prev_btn.setEnabled(
            not searching and not is_downloading and self._current_page > 1
        )
        self._next_btn.setEnabled(
            not searching and not is_downloading and self._current_page < self._total_pages
        )

        # Download button text
        if self._download_state == self.DOWNLOAD_EXTRACTING:
            self._download_btn.setText("正在提取直链...")
        elif self._download_state == self.DOWNLOAD_DOWNLOADING:
            self._download_btn.setText("下载中...")
        elif self._download_state == self.DOWNLOAD_FINISHED:
            self._download_btn.setText("下载完成")
        else:
            self._download_btn.setText("下载选中")

    def _on_search_clicked(self):
        actor = self._search_input.text().strip()
        if not actor:
            return
        self._current_actor = actor
        self._current_page = 1
        self._page_results = {}
        self._checked_ids = set()
        self._do_search(actor, 1)

    def _do_search(self, actor: str, page: int):
        self._set_search_state(self.SEARCH_SEARCHING)
        self._results_label.setText("搜索中...")
        self._table.setRowCount(0)

        self._search_worker = SearchWorker(self._parser, actor, page)
        self._search_worker.page_done.connect(self._on_page_done)
        self._search_worker.finished.connect(self._on_search_finished)
        self._search_worker.error.connect(self._on_search_error)
        self._search_worker.start()

    @pyqtSlot(int, int)
    def _on_page_done(self, page: int, total: int):
        self._current_page = page
        self._total_pages = total
        self._page_label.setText(f"{page} / {max(1, total)}")
        self._prev_btn.setEnabled(page > 1)
        self._next_btn.setEnabled(page < total)

    @pyqtSlot(list)
    def _on_search_finished(self, results: list[SearchResult]):
        self._set_search_state(self.SEARCH_IDLE)
        self._page_results[self._current_page] = results
        self._current_results = results
        self._display_results(results)

    @pyqtSlot(str)
    def _on_search_error(self, error_msg: str):
        self._set_search_state(self.SEARCH_IDLE)
        self._results_label.setText(f"搜索失败：{error_msg}")
        QMessageBox.warning(self, "搜索失败", error_msg)
        self._update_ui_state()

    def _display_results(self, results: list[SearchResult]):
        self._table.setRowCount(0)
        self._table.setRowCount(len(results))

        for row, sr in enumerate(results):
            # Checkbox column (column 0)
            item = QTableWidgetItem()
            item.setData(Qt.ItemDataRole.CheckStateRole, Qt.CheckState.Checked if sr.video_id in self._checked_ids else Qt.CheckState.Unchecked)
            self._table.setItem(row, 0, item)

            # Thumbnail (column 1)
            thumb_label = QLabel()
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if sr.thumbnail:
                from urllib.request import urlopen
                from PyQt6.QtGui import QPixmap
                try:
                    data = urlopen(sr.thumbnail, timeout=5).read()
                    pixmap = QPixmap()
                    pixmap.loadFromData(data)
                    scaled = pixmap.scaled(80, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    thumb_label.setPixmap(scaled)
                except Exception:
                    thumb_label.setText("[无封面]")
            else:
                thumb_label.setText("[无封面]")
            self._table.setCellWidget(row, 1, thumb_label)

            # Title (column 2)
            title_item = QTableWidgetItem(sr.title)
            title_item.setToolTip(sr.title)
            self._table.setItem(row, 2, title_item)

            # Duration (column 3)
            duration_item = QTableWidgetItem(sr.formatted_duration)
            self._table.setItem(row, 3, duration_item)

            # Gray out already-downloaded
            if sr.video_id in self._downloaded_ids:
                for col in range(4):
                    item = self._table.item(row, col)
                    if item:
                        item.setBackground(Qt.GlobalColor.lightGray)

        self._results_label.setText(
            f"找到 {len(results)} 个视频" if results else "未找到该演员的相关视频"
        )
        self._update_selected_count()
        self._update_ui_state()

    def _on_table_item_clicked(self, item: QTableWidgetItem):
        """Handle checkbox column click."""
        if item.column() != 0:
            return
        row = item.row()
        if 0 <= row < len(self._current_results):
            sr = self._current_results[row]
            current_state = self._table.item(row, 0).data(Qt.ItemDataRole.CheckStateRole)
            new_state = Qt.CheckState.Unchecked if current_state == Qt.CheckState.Checked else Qt.CheckState.Checked
            self._table.item(row, 0).setData(Qt.ItemDataRole.CheckStateRole, new_state)
            if new_state == Qt.CheckState.Checked:
                self._checked_ids.add(sr.video_id)
            else:
                self._checked_ids.discard(sr.video_id)
            self._update_selected_count()
            self._update_ui_state()

    def _update_selected_count(self):
        self._selected_label.setText(f"已选 {len(self._checked_ids)} 个")

    def _on_prev_page(self):
        if self._current_page > 1:
            page = self._current_page - 1
            self._current_page = page
            if page in self._page_results:
                self._current_results = self._page_results[page]
                self._display_results(self._current_results)
                self._page_label.setText(f"{page} / {max(1, self._total_pages)}")
            else:
                self._do_search(self._current_actor, page)

    def _on_next_page(self):
        if self._current_page < self._total_pages:
            page = self._current_page + 1
            self._current_page = page
            if page in self._page_results:
                self._current_results = self._page_results[page]
                self._display_results(self._current_results)
                self._page_label.setText(f"{page} / {max(1, self._total_pages)}")
            else:
                self._do_search(self._current_actor, page)

    def _on_select_all(self):
        """Select all visible results."""
        for row, sr in enumerate(self._current_results):
            self._table.item(row, 0).setData(Qt.ItemDataRole.CheckStateRole, Qt.CheckState.Checked)
            self._checked_ids.add(sr.video_id)
        self._update_selected_count()
        self._update_ui_state()

    def _on_concurrent_changed(self, value: int):
        self._config.concurrent_downloads = value

    def _on_download_clicked(self):
        """Start the two-phase download process."""
        if not self._checked_ids:
            return

        # Collect selected SearchResults
        selected = []
        for page_results in self._page_results.values():
            for sr in page_results:
                if sr.video_id in self._checked_ids:
                    selected.append(sr)

        if not selected:
            return

        self._set_download_state(self.DOWNLOAD_EXTRACTING)
        self._batch_progress.setVisible(True)
        self._batch_progress.setValue(0)
        self._item_progress_label.setVisible(True)
        self._item_progress_label.setText("正在提取直链...")
        self._update_ui_state()

        # Phase 1: Extract direct URLs for all selected videos
        self._extract_queue: list[tuple[SearchResult, VideoInfo | None]] = []
        self._extract_done_count = 0
        self._extract_total = len(selected)
        self._extract_errors: list[tuple[str, str]] = []  # (video_id, error)

        # Limit concurrent extraction to 3
        self._extraction_workers: list[QThread] = []
        self._extraction_batch = list(selected)
        self._launch_next_extraction()

    def _launch_next_extraction(self):
        """Launch extraction workers up to concurrent limit."""
        while len(self._extraction_workers) < 3 and self._extraction_batch:
            sr = self._extraction_batch.pop(0)
            worker = _ExtractWorker(sr, self._parser)
            worker.finished.connect(self._on_extract_done)
            worker.start()
            self._extraction_workers.append(worker)

    @pyqtSlot(SearchResult, object, str)
    def _on_extract_done(self, sr: SearchResult, video_info: VideoInfo | None, error: str):
        self._extraction_workers.remove(self.sender())
        self._extract_done_count += 1
        self._batch_progress.setValue(int(self._extract_done_count / self._extract_total * 50))  # Phase 1 = 50%

        if video_info is not None:
            self._extract_queue.append((sr, video_info))
        elif error:
            self._extract_errors.append((sr.video_id, error))

        if self._extract_done_count == self._extract_total:
            self._start_download_phase()
        else:
            self._launch_next_extraction()

    def _start_download_phase(self):
        """Phase 2: Start DownloadQueue with extracted VideoInfos."""
        self._set_download_state(self.DOWNLOAD_DOWNLOADING)
        self._item_progress_label.setText(f"正在下载 {len(self._extract_queue)} 个视频...")
        self._batch_progress.setValue(50)
        self._update_ui_state()

        video_infos = [vi for _, vi in self._extract_queue]
        self._download_queue = DownloadQueue(
            self._config.output_dir,
            self._config.concurrent_downloads
        )
        self._download_queue.batch_progress.connect(self._on_batch_progress)
        self._download_queue.item_progress.connect(self._on_item_progress)
        self._download_queue.item_finished.connect(self._on_item_finished)
        self._download_queue.item_failed.connect(self._on_item_failed)
        self._download_queue.batch_finished.connect(self._on_batch_finished)
        self._download_queue.start(video_infos)

    @pyqtSlot(int, int)
    def _on_batch_progress(self, done: int, total: int):
        # Phase 2 is 50-100%, Phase 1 was 0-50%
        pct = 50 + int(done / total * 50)
        self._batch_progress.setValue(pct)

    @pyqtSlot(str, float)
    def _on_item_progress(self, video_id: str, percent: float):
        # Find the title for this video_id
        title = video_id
        for sr, vi in self._extract_queue:
            if sr.video_id == video_id:
                title = sr.title
                break
        self._item_progress_label.setText(f"正在下载: {title} ({percent:.0f}%)")

    @pyqtSlot(str)
    def _on_item_finished(self, video_id: str):
        # Find title and add to history
        title = video_id
        for sr, vi in self._extract_queue:
            if sr.video_id == video_id:
                title = sr.title
                break
        self.download_entry_finished.emit(title, video_id, "missav")
        if self._history_widget:
            self._history_widget.add_entry(title, video_id, "finished", source_site="missav")

    @pyqtSlot(str, str)
    def _on_item_failed(self, video_id: str, error: str):
        title = video_id
        for sr, vi in self._extract_queue:
            if sr.video_id == video_id:
                title = sr.title
                break
        if self._history_widget:
            self._history_widget.add_entry(title, video_id, "error", source_site="missav")

    @pyqtSlot(list, list)
    def _on_batch_finished(self, success_ids: list, failed_ids: list):
        self._batch_progress.setValue(100)
        self._set_download_state(self.DOWNLOAD_FINISHED)
        self._item_progress_label.setText("下载完成")

        msg = QMessageBox(self)
        msg.setWindowTitle("批量下载完成")
        if not failed_ids:
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setText(f"成功下载 {len(success_ids)} 个视频")
        else:
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText(f"成功 {len(success_ids)} 个，失败 {len(failed_ids)} 个")
            msg.setDetailedText("\n".join(f"  - {vid}" for vid in failed_ids))
        msg.exec()

        # Reset after a short delay
        self._batch_progress.setVisible(False)
        self._item_progress_label.setVisible(False)
        self._set_download_state(self.SEARCH_IDLE)
        self._update_ui_state()


class _ExtractWorker(QThread):
    """Background thread to extract direct URL from a single SearchResult detail page."""
    finished = pyqtSignal(SearchResult, object, str)  # sr, video_info, error

    def __init__(self, sr: SearchResult, parser: MissavParser):
        super().__init__()
        self._sr = sr
        self._parser = parser

    def run(self):
        try:
            video_info = self._parser.parse(self._sr.detail_url)
            self.finished.emit(self._sr, video_info, "")
        except VideoParseError as e:
            self.finished.emit(self._sr, None, str(e))
        except Exception as e:
            self.finished.emit(self._sr, None, str(e))
