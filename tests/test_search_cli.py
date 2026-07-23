"""End-to-end tests for the search command-line interface."""

from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.interfaces.search_cli import main


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


def test_main_prints_matching_results(tmp_path: Path, capsys) -> None:
    """A successful search prints the matching title and excerpt."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    exit_code = main(["jurisprudence", "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Book of Fiqh" in captured.out


def test_main_reports_no_matches(tmp_path: Path, capsys) -> None:
    """A query with no matches exits successfully with a clear message."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    exit_code = main(["nonexistentterm", "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No matches found." in captured.out


def test_main_fails_cleanly_when_database_is_missing(tmp_path: Path) -> None:
    """A missing master database returns a non-zero exit code instead of raising."""
    exit_code = main(["query", "--database", str(tmp_path / "missing.db")])

    assert exit_code == 1


def test_main_shows_library_and_respects_library_filter(tmp_path: Path, capsys) -> None:
    """Results show their library, and --library restricts the search to one."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    other_book = Book(
        information={"Name": "Other Fiqh Book"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "More rules of jurisprudence here", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path,
        (other_book,),
        (database_path.parent / "other.mjbz",),
        library_name="Second Library",
    )

    exit_code = main(["jurisprudence", "--database", str(database_path)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "[Maktaba Jibreel (Mobile)]" in captured.out
    assert "[Second Library]" in captured.out

    exit_code = main(
        ["jurisprudence", "--database", str(database_path), "--library", "Second Library"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Other Fiqh Book" in captured.out
    assert "Book of Fiqh" not in captured.out
