"""Tests for the desktop app's Quick Open dialog (screens + recent books)."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (  # noqa: E402
    RecentBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.quick_open_dialog import (  # noqa: E402
    QuickOpenDialog,
)

_RAIL_LABELS = ("Home", "Search", "Libraries", "Duplicates", "Taxonomy", "Logs", "Settings")


def _migrated_database_with_a_recent_book(tmp_path: Path) -> Path:
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Fiqh"}, categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    RecentBookRepository(database_path).record_open(1)
    return database_path


def test_lists_every_rail_screen_and_recent_book_by_default(qtbot, tmp_path: Path) -> None:
    """With no filter text, every screen and recent book is listed."""
    database_path = _migrated_database_with_a_recent_book(tmp_path)
    dialog = QuickOpenDialog(_RAIL_LABELS, RecentBookRepository(database_path))
    qtbot.addWidget(dialog)

    assert dialog._list.count() == len(_RAIL_LABELS) + 1


def test_typing_filters_to_matching_entries_only(qtbot, tmp_path: Path) -> None:
    """Typing narrows the list to real, matching screens/books."""
    database_path = _migrated_database_with_a_recent_book(tmp_path)
    dialog = QuickOpenDialog(_RAIL_LABELS, RecentBookRepository(database_path))
    qtbot.addWidget(dialog)

    dialog._filter_edit.setText("Fiqh")

    assert dialog._list.count() == 1
    assert "Book of Fiqh" in dialog._list.item(0).text()


def test_activating_a_screen_entry_emits_screen_requested(qtbot, tmp_path: Path) -> None:
    """Selecting a screen entry emits its real rail index and closes the dialog."""
    database_path = _migrated_database_with_a_recent_book(tmp_path)
    dialog = QuickOpenDialog(_RAIL_LABELS, RecentBookRepository(database_path))
    qtbot.addWidget(dialog)
    dialog._filter_edit.setText("Taxonomy")

    with qtbot.waitSignal(dialog.screen_requested, timeout=1000) as blocker:
        dialog._open_first_match()
    assert blocker.args == [4]


def test_activating_a_book_entry_emits_book_requested(qtbot, tmp_path: Path) -> None:
    """Selecting a recent book entry emits its real book id."""
    database_path = _migrated_database_with_a_recent_book(tmp_path)
    dialog = QuickOpenDialog(_RAIL_LABELS, RecentBookRepository(database_path))
    qtbot.addWidget(dialog)
    dialog._filter_edit.setText("Fiqh")

    with qtbot.waitSignal(dialog.book_requested, timeout=1000) as blocker:
        dialog._open_first_match()
    assert blocker.args == [1, 1]
