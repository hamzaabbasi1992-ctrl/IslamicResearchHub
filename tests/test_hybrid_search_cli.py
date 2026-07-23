"""End-to-end tests for the hybrid search command-line interface."""

from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.interfaces.hybrid_search_cli import main


def _seed_database(database_path: Path) -> None:
    """Import one book with searchable content into a fresh master database."""
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence in fiqh are extensive", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_main_keyword_only_prints_matched_by_and_score(tmp_path: Path, capsys) -> None:
    """--keyword-only skips semantic search and still returns ranked results."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    exit_code = main(
        ["jurisprudence", "--database", str(database_path), "--keyword-only"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Book of Fiqh" in captured.out
    assert "matched by: keyword" in captured.out


def test_main_reports_no_matches(tmp_path: Path, capsys) -> None:
    """A query with no matches exits successfully with a clear message."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    exit_code = main(
        ["nonexistentterm", "--database", str(database_path), "--keyword-only"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No matches found." in captured.out
