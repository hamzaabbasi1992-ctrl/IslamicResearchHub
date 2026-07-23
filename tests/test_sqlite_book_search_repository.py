"""Tests for the read-only full-text search adapter over the master database."""

from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
    BookSearchError,
    SqliteBookSearchRepository,
)


def _seed_database(database_path: Path) -> None:
    """Import one book with searchable content into a fresh master database."""
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(
            Page(1, 1, "The rules of jurisprudence in fiqh are extensive", "Plain"),
            Page(2, 2, "Unrelated page about something else entirely", "Plain"),
        ),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_search_returns_ranked_matches_with_snippets(tmp_path: Path) -> None:
    """A matching term returns the book, page, author, library, and a highlighted excerpt."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    results = SqliteBookSearchRepository(database_path).search("jurisprudence", limit=10)

    assert len(results) == 1
    assert results[0].title == "Book of Fiqh"
    assert results[0].author == "Author One"
    assert results[0].page_number == 1
    assert results[0].library == "Maktaba Jibreel (Mobile)"
    assert "jurisprudence" in results[0].excerpt.lower()


def test_search_filters_by_library(tmp_path: Path) -> None:
    """A library filter excludes matches from other libraries."""
    database_path = tmp_path / "books.db"
    other_book = Book(
        information={"Name": "Other Book"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence explained again", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path,
        (other_book,),
        (database_path.parent / "other.mjbz",),
        library_name="Other Library",
    )
    _seed_database(database_path)

    results = SqliteBookSearchRepository(database_path).search(
        "jurisprudence", limit=10, library="Other Library"
    )

    assert len(results) == 1
    assert results[0].title == "Other Book"
    assert results[0].library == "Other Library"


def test_search_returns_no_results_for_unmatched_term(tmp_path: Path) -> None:
    """A term absent from every page returns an empty result tuple."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    results = SqliteBookSearchRepository(database_path).search("nonexistentterm", limit=10)

    assert results == ()


def test_search_raises_when_database_is_missing(tmp_path: Path) -> None:
    """Searching a database that was never built raises a clear error."""
    with pytest.raises(BookSearchError):
        SqliteBookSearchRepository(tmp_path / "missing.db").search("query", limit=10)
