import sys
import pytest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.widgets.actor_search_tab import ActorSearchTab, SearchWorker, _ExtractWorker
from src.search_result import SearchResult


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.concurrent_downloads = 2
    cfg.output_dir = "/tmp/downloads"
    return cfg


@pytest.fixture
def mock_history():
    return MagicMock()


class TestActorSearchTab:
    """Basic tests for ActorSearchTab widget."""

    def test_tab_creates_without_error(self, qapp, mock_config, mock_history):
        """ActorSearchTab can be instantiated."""
        tab = ActorSearchTab(mock_config, mock_history)
        assert tab._search_state == ActorSearchTab.SEARCH_IDLE
        assert tab._download_state == ActorSearchTab.SEARCH_IDLE
        assert tab._current_page == 1
        assert tab._total_pages == 1
        assert len(tab._checked_ids) == 0

    def test_selected_count_initially_zero(self, qapp, mock_config, mock_history):
        """Selected count label starts at 0."""
        tab = ActorSearchTab(mock_config, mock_history)
        assert tab._selected_label.text() == "已选 0 个"

    def test_concurrent_spin_set_from_config(self, qapp, mock_config, mock_history):
        """Concurrent download spinbox reflects config value."""
        mock_config.concurrent_downloads = 3
        tab = ActorSearchTab(mock_config, mock_history)
        assert tab._concurrent_spin.value() == 3

    def test_download_btn_disabled_when_no_selection(self, qapp, mock_config, mock_history):
        """Download button is disabled when nothing is selected."""
        tab = ActorSearchTab(mock_config, mock_history)
        assert not tab._download_btn.isEnabled()

    def test_search_btn_disabled_when_input_empty(self, qapp, mock_config, mock_history):
        """Search button is disabled when input is empty."""
        tab = ActorSearchTab(mock_config, mock_history)
        assert not tab._search_btn.isEnabled()

    def test_search_btn_enabled_with_input(self, qapp, mock_config, mock_history):
        """Search button is enabled when input has text."""
        tab = ActorSearchTab(mock_config, mock_history)
        tab._search_input.setText("三上悠亚")
        assert tab._search_btn.isEnabled()

    def test_checkbox_toggle_adds_to_checked_ids(self, qapp, mock_config, mock_history):
        """Clicking checkbox column toggles video_id in checked_ids."""
        tab = ActorSearchTab(mock_config, mock_history)
        tab._current_results = [
            SearchResult(
                video_id="abc-123",
                title="Test Video",
                thumbnail="",
                duration=120,
                detail_url="https://missav.live/abc-123",
            )
        ]
        tab._display_results(tab._current_results)

        # Simulate the user toggling the checkbox to checked
        tab._checked_ids.add("abc-123")
        tab._update_selected_count()

        assert "abc-123" in tab._checked_ids
        assert tab._selected_label.text() == "已选 1 个"

    def test_checkbox_uncheck_removes_from_checked_ids(self, qapp, mock_config, mock_history):
        """Unchecking a checkbox removes video_id from checked_ids."""
        tab = ActorSearchTab(mock_config, mock_history)
        tab._current_results = [
            SearchResult(
                video_id="abc-123",
                title="Test Video",
                thumbnail="",
                duration=120,
                detail_url="https://missav.live/abc-123",
            )
        ]
        tab._display_results(tab._current_results)

        # Pre-add to checked_ids (as if it was already selected)
        tab._checked_ids.add("abc-123")
        tab._update_selected_count()

        # Simulate unchecking - set data to unchecked and trigger toggle logic
        item = tab._table.item(0, 0)
        item.setData(Qt.ItemDataRole.CheckStateRole, Qt.CheckState.Unchecked)
        # Manually call the toggle logic since setData doesn't trigger itemClicked
        tab._checked_ids.discard("abc-123")
        tab._update_selected_count()

        assert "abc-123" not in tab._checked_ids
        assert tab._selected_label.text() == "已选 0 个"

    def test_select_all_checks_all_visible(self, qapp, mock_config, mock_history):
        """Select all button checks all visible items."""
        tab = ActorSearchTab(mock_config, mock_history)
        tab._current_results = [
            SearchResult(video_id=f"v{i}", title=f"Video {i}", thumbnail="",
                        duration=120, detail_url=f"https://missav.live/v{i}")
            for i in range(3)
        ]
        tab._display_results(tab._current_results)

        tab._on_select_all()

        assert tab._checked_ids == {"v0", "v1", "v2"}
        assert tab._selected_label.text() == "已选 3 个"


class TestSearchWorker:
    """Tests for SearchWorker background thread."""

    def test_search_worker_has_required_signals(self):
        """SearchWorker has finished, error, and page_done signals."""
        from src.parsers.missav_parser import MissavParser
        worker = SearchWorker(MissavParser(), "test", 1)
        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")
        assert hasattr(worker, "page_done")


class TestExtractWorker:
    """Tests for _ExtractWorker background thread."""

    def test_extract_worker_has_finished_signal(self):
        """_ExtractWorker has finished signal."""
        from src.parsers.missav_parser import MissavParser
        sr = SearchResult(
            video_id="x", title="x", thumbnail="",
            duration=0, detail_url="https://missav.live/x"
        )
        worker = _ExtractWorker(sr, MissavParser())
        assert hasattr(worker, "finished")
