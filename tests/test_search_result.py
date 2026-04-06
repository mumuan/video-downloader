import pytest
from src.search_result import SearchResult


def test_search_result_basic():
    sr = SearchResult(
        video_id="abc123",
        title="Test Video",
        thumbnail="https://example.com/thumb.jpg",
        duration=120,
        detail_url="https://missav.live/abc123",
    )
    assert sr.video_id == "abc123"
    assert sr.title == "Test Video"
    assert sr.thumbnail == "https://example.com/thumb.jpg"
    assert sr.duration == 120
    assert sr.detail_url == "https://missav.live/abc123"


def test_search_result_formatted_duration():
    sr = SearchResult(
        video_id="x", title="x", thumbnail="", duration=90, detail_url="x"
    )
    assert sr.formatted_duration == "1:30"

    sr2 = SearchResult(
        video_id="y", title="y", thumbnail="", duration=3661, detail_url="y"
    )
    assert sr2.formatted_duration == "1:01:01"

    sr3 = SearchResult(
        video_id="z", title="z", thumbnail="", duration=0, detail_url="z"
    )
    assert sr3.formatted_duration == "0:00"


def test_search_result_duration_float_not_cast():
    # SearchResult stores duration as-is; parser is responsible for float->int cast
    sr = SearchResult(
        video_id="x", title="x", thumbnail="", duration=90.5, detail_url="x"
    )
    assert sr.duration == 90.5
    assert sr.formatted_duration == "1:30"
