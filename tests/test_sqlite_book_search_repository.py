"""Tests for the read-only full-text search adapter over the master database."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
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


def test_search_matches_letter_form_variants_after_migration(tmp_path: Path) -> None:
    """Once migrated, a query using one spelling variant matches another."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book About Ali"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "كتاب علی الفقه", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    results = SqliteBookSearchRepository(database_path).search("علي", limit=10)

    assert len(results) == 1
    assert results[0].title == "Book About Ali"


def test_exact_true_does_not_match_a_letter_form_variant_after_migration(
    tmp_path: Path,
) -> None:
    """With exact=True, a spelling-variant query does NOT match, even though it
    would under the default tolerant search - proving exact mode is real,
    literal matching, not just tolerant matching that happens to work."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book About Ali"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "كتاب علی الفقه", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    tolerant_results = SqliteBookSearchRepository(database_path).search("علي", limit=10)
    exact_results = SqliteBookSearchRepository(database_path).search(
        "علي", limit=10, exact=True
    )

    assert len(tolerant_results) == 1
    assert exact_results == ()


def test_exact_true_matches_the_real_literal_spelling(tmp_path: Path) -> None:
    """With exact=True, the literal spelling actually present still matches."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book About Ali"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "كتاب علی الفقه", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    results = SqliteBookSearchRepository(database_path).search("علی", limit=10, exact=True)

    assert len(results) == 1


def test_search_falls_back_to_plain_index_before_migration(tmp_path: Path) -> None:
    """Before migration 5 runs, search still works via the plain PagesFTS index."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    results = SqliteBookSearchRepository(database_path).search("jurisprudence", limit=10)

    assert len(results) == 1
    assert results[0].title == "Book of Fiqh"


def test_search_filters_by_author(tmp_path: Path) -> None:
    """An author filter excludes matches by a different author."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    other_book = Book(
        information={"Name": "Other Book", "ANAME": "Author Two"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence explained again", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (other_book,), (database_path.parent / "other.mjbz",)
    )

    results = SqliteBookSearchRepository(database_path).search(
        "jurisprudence", limit=10, author="Author Two"
    )

    assert len(results) == 1
    assert results[0].title == "Other Book"
    assert results[0].author == "Author Two"


def test_search_filters_by_category(tmp_path: Path) -> None:
    """A category filter excludes matches from books outside that category."""
    database_path = tmp_path / "books.db"
    fiqh = Category(mjcn=9, name="Fiqh", parent_mjcn=0, sort_key=1)
    hadith = Category(mjcn=10, name="Hadith", parent_mjcn=0, sort_key=1)
    fiqh_book = Book(
        information={"Name": "Fiqh Book"},
        categories=(fiqh,),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence in fiqh", "Plain"),),
    )
    hadith_book = Book(
        information={"Name": "Hadith Book"},
        categories=(hadith,),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence in hadith too", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path,
        (fiqh_book, hadith_book),
        (database_path.parent / "fiqh.mjbz", database_path.parent / "hadith.mjbz"),
    )

    results = SqliteBookSearchRepository(database_path).search(
        "jurisprudence", limit=10, category="Fiqh"
    )

    assert len(results) == 1
    assert results[0].title == "Fiqh Book"


def test_search_supports_boolean_and_operator(tmp_path: Path) -> None:
    """An explicit AND query matches only pages containing both terms."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    results = SqliteBookSearchRepository(database_path).search(
        "jurisprudence AND fiqh", limit=10
    )

    assert len(results) == 1
    assert results[0].page_number == 1


def test_search_supports_boolean_or_operator(tmp_path: Path) -> None:
    """An OR query matches pages containing either term."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    results = SqliteBookSearchRepository(database_path).search(
        "jurisprudence OR unrelated", limit=10
    )

    assert len(results) == 2


def test_search_supports_boolean_not_operator(tmp_path: Path) -> None:
    """A NOT query excludes pages containing the excluded term."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    results = SqliteBookSearchRepository(database_path).search(
        "jurisprudence NOT extensive", limit=10
    )

    assert results == ()


def test_search_supports_phrase_queries(tmp_path: Path) -> None:
    """A quoted phrase matches only that exact word sequence."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    results = SqliteBookSearchRepository(database_path).search(
        '"rules of jurisprudence"', limit=10
    )

    assert len(results) == 1
    assert results[0].page_number == 1


def test_search_raises_book_search_error_for_malformed_query(tmp_path: Path) -> None:
    """A malformed FTS5 query (unbalanced quote) raises a clear error, not a raw crash."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    with pytest.raises(BookSearchError):
        SqliteBookSearchRepository(database_path).search('"unbalanced quote', limit=10)
