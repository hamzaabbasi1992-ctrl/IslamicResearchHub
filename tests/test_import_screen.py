"""Tests for the desktop app's Import screen, wired to a real master database."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (  # noqa: E402
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.import_screen import ImportScreen  # noqa: E402


def _seed_database(database_path: Path) -> None:
    """Import two real books into two different libraries."""
    book_one = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",), library_name="Library A"
    )
    book_two = Book(
        information={"Name": "Book of Hadith"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "More content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",), library_name="Library B"
    )


def test_shows_real_library_sources_with_counts(qtbot, tmp_path: Path) -> None:
    """The library table reflects the real database, not hardcoded data."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)

    rows = {
        screen._library_table.item(row, 0).text(): screen._library_table.item(row, 1).text()
        for row in range(screen._library_table.rowCount())
    }
    assert rows["Library A"] == "1"
    assert rows["Library B"] == "1"


def test_scan_button_detects_real_cross_library_duplicates(qtbot, tmp_path: Path) -> None:
    """Scanning finds a real title match across two libraries."""
    database_path = tmp_path / "books.db"
    duplicate_book = Book(
        information={"Name": "Book of Fiqh"},  # same title as book_one, different library
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Duplicate content", "Plain"),),
    )
    _seed_database(database_path)
    MasterBookRepository().import_books(
        database_path,
        (duplicate_book,),
        (database_path.parent / "dup.mjbz",),
        library_name="Library C",
    )
    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)
    assert screen._duplicate_table.rowCount() == 0  # nothing scanned yet

    screen._run_scan()

    assert screen._duplicate_table.rowCount() == 1
    assert "1 candidate" in screen._duplicate_status_label.text()
    titles = {
        screen._duplicate_table.item(0, 0).text(),
        screen._duplicate_table.item(0, 2).text(),
    }
    assert titles == {"Book of Fiqh"}


def test_cleanup_button_removes_a_real_empty_stub_duplicate(qtbot, tmp_path: Path) -> None:
    """Removing empty-stub duplicates deletes the zero-page side and refreshes both tables."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    stub_book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(),  # metadata-only stub, matches book_one's title
    )
    MasterBookRepository().import_books(
        database_path, (stub_book,), (database_path.parent / "stub.mjbz",), library_name="Library C"
    )
    DuplicateCandidateRepository(database_path).detect_and_store()

    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)
    assert screen._duplicate_table.rowCount() == 1

    screen._run_cleanup()

    assert "Removed 1" in screen._duplicate_status_label.text()
    assert screen._duplicate_table.rowCount() == 0
    with sqlite3.connect(database_path) as connection:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM Books WHERE Source LIKE '%stub.mjbz'"
        ).fetchone()[0]
    assert remaining == 0


def test_refresh_reloads_after_an_external_change(qtbot, tmp_path: Path) -> None:
    """Calling refresh() picks up a change made after the screen was built."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)
    rows_before = screen._library_table.rowCount()

    third_book = Book(
        information={"Name": "Book of Tafsir"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (third_book,), (database_path.parent / "three.mjbz",), library_name="Library C"
    )

    screen.refresh()

    assert screen._library_table.rowCount() == rows_before + 1
