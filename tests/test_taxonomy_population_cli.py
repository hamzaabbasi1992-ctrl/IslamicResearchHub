"""End-to-end tests for the taxonomy population command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.interfaces.taxonomy_population_cli import main


def _make_migrated_database(path: Path) -> None:
    """Create a real, fully-migrated database with real categories and an author."""
    fiqh = Category(mjcn=9, name="الفقه", parent_mjcn=0, sort_key=1)
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Imam Al-Ghazali"},
        categories=(fiqh,),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(path, (book,), (path.parent / "source.mjbz",))
    with sqlite3.connect(path) as connection:
        MigrationRunner().migrate(connection)


def test_main_populates_and_links_real_taxonomy_data(tmp_path: Path, capsys) -> None:
    """Running against a real migrated database populates and links real terms."""
    database_path = tmp_path / "books.db"
    _make_migrated_database(database_path)

    exit_code = main(["--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Subject terms: 1" in captured.out
    assert "Author terms: 1" in captured.out
    assert "Book-subject links: 1" in captured.out
    assert "Book-author links: 1" in captured.out


def test_main_fails_cleanly_when_database_is_missing(tmp_path: Path) -> None:
    """A missing database returns a non-zero exit code instead of raising."""
    exit_code = main(["--database", str(tmp_path / "missing.db")])

    assert exit_code == 1
