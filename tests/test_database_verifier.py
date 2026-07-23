"""Tests for the read-only master database integrity verifier."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Category, Chapter, Page
from islamic_research_hub.infrastructure.persistence.database_verifier import DatabaseVerifier
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


def _seed_valid_database(database_path: Path) -> None:
    """Import one well-formed book into a fresh master database."""
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(Category(1, "Root", None, 1),),
        table_of_contents=(Chapter(1, "Chapter", 1, None, 1),),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_healthy_database_reports_no_issues(tmp_path: Path) -> None:
    """A freshly-imported, untouched database reports as healthy."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy
    assert report.error_count == 0
    assert report.issues == ()


def test_detects_orphaned_pages(tmp_path: Path) -> None:
    """A Pages row referencing a nonexistent BookID is flagged as an error."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Pages (BookID, PageNo, Content) VALUES (9999, 1, 'orphaned')"
        )

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(issue.category == "orphaned_rows" for issue in report.issues)


def test_detects_stale_page_count(tmp_path: Path) -> None:
    """A Books.PageCount that disagrees with the real Pages rows is a warning."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Books SET PageCount = 999 WHERE BookID = 1")

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy  # stale counts are a warning, not an error
    assert any(issue.category == "stale_counts" for issue in report.issues)


def test_detects_duplicate_page_numbers(tmp_path: Path) -> None:
    """A repeated (BookID, PageNo) pair is flagged as a warning."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Pages (BookID, PageNo, Content) VALUES (1, 1, 'duplicate page')"
        )

    report = DatabaseVerifier(database_path).verify()

    assert any(issue.category == "duplicate_pages" for issue in report.issues)


def test_detects_orphaned_library_reference(tmp_path: Path) -> None:
    """A Books row referencing a nonexistent LibraryID is flagged as an error."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Books SET LibraryID = 9999 WHERE BookID = 1")

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(
        issue.category == "orphaned_rows" and "Books" in issue.message
        for issue in report.issues
    )
