"""Tests for the desktop app's recent-search-queries store."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.search_history import (  # noqa: E402
    MAX_RECENT_SEARCHES,
    RecentSearchStore,
)


def _isolated_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_list_recent_is_empty_when_nothing_is_stored(tmp_path: Path) -> None:
    """A fresh store has no recent searches."""
    store = RecentSearchStore(_isolated_settings(tmp_path))

    assert store.list_recent() == []


def test_record_adds_a_query_to_the_front(tmp_path: Path) -> None:
    """A single recorded query is recalled, including the single-string
    QSettings edge case (a 1-item list can collapse to a bare string)."""
    store = RecentSearchStore(_isolated_settings(tmp_path))

    store.record("hadith of intentions")

    assert store.list_recent() == ["hadith of intentions"]


def test_record_puts_the_newest_query_first(tmp_path: Path) -> None:
    """Multiple queries are recalled newest-first."""
    store = RecentSearchStore(_isolated_settings(tmp_path))

    store.record("first query")
    store.record("second query")

    assert store.list_recent() == ["second query", "first query"]


def test_record_deduplicates_and_moves_a_repeated_query_to_the_front(tmp_path: Path) -> None:
    """Searching the same thing again bumps it to the top instead of duplicating it."""
    store = RecentSearchStore(_isolated_settings(tmp_path))
    store.record("first query")
    store.record("second query")

    store.record("first query")

    assert store.list_recent() == ["first query", "second query"]


def test_record_trims_to_the_maximum(tmp_path: Path) -> None:
    """Older queries fall off once the limit is exceeded."""
    store = RecentSearchStore(_isolated_settings(tmp_path))
    for i in range(MAX_RECENT_SEARCHES + 5):
        store.record(f"query {i}")

    recent = store.list_recent()

    assert len(recent) == MAX_RECENT_SEARCHES
    assert recent[0] == f"query {MAX_RECENT_SEARCHES + 4}"


def test_record_ignores_blank_queries(tmp_path: Path) -> None:
    """Whitespace-only input is never recorded."""
    store = RecentSearchStore(_isolated_settings(tmp_path))

    store.record("   ")

    assert store.list_recent() == []


def test_recent_searches_persist_across_store_instances(tmp_path: Path) -> None:
    """A fresh store instance (e.g. next app launch) picks up prior history."""
    settings = _isolated_settings(tmp_path)
    RecentSearchStore(settings).record("persisted query")

    reloaded = RecentSearchStore(settings)

    assert reloaded.list_recent() == ["persisted query"]
