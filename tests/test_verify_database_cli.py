"""End-to-end tests for the database verification command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.interfaces.verify_database_cli import main


def _seed_valid_database(database_path: Path) -> None:
    """Import one well-formed book into a fresh master database."""
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_main_reports_healthy_database(tmp_path: Path, capsys) -> None:
    """A healthy database exits 0 and prints a clean report."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)

    exit_code = main(["--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Errors: 0" in captured.out
    assert "Database is healthy." in captured.out


def test_main_exits_nonzero_when_errors_found(tmp_path: Path, capsys) -> None:
    """A database with a real integrity error exits non-zero."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Pages (BookID, PageNo, Content) VALUES (9999, 1, 'orphaned')"
        )

    exit_code = main(["--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ERROR" in captured.out


def test_main_fails_cleanly_when_database_is_missing(tmp_path: Path) -> None:
    """A missing database returns a non-zero exit code instead of raising."""
    exit_code = main(["--database", str(tmp_path / "missing.db")])

    assert exit_code == 1
