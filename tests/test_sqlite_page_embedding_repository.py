"""Tests for the pilot-scale SQLite page embedding store and search."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.sqlite_page_embedding_repository import (
    SqlitePageEmbeddingRepository,
)


def _seed_database(database_path: Path) -> None:
    """Import two books with content into a fresh master database."""
    first_book = Book(
        information={"Name": "Book One", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "About mercy and compassion", "Plain"),),
    )
    second_book = Book(
        information={"Name": "Book Two", "ANAME": "Author Two"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "About trade and commerce", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path,
        (first_book, second_book),
        (database_path.parent / "first.mjbz", database_path.parent / "second.mjbz"),
    )


def _seed_database_with_languages(database_path: Path) -> None:
    """Two books, real per-book `Language` values - for testing the
    query-language same-language boost."""
    arabic_book = Book(
        information={"Name": "Arabic Book", "ANAME": "Author One", "Language": "Arabic"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Arabic content", "Plain"),),
    )
    urdu_book = Book(
        information={"Name": "Urdu Book", "ANAME": "Author Two", "Language": "Urdu"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Urdu content", "Plain"),),
    )
    unlabeled_book = Book(
        information={"Name": "Unlabeled Book", "ANAME": "Author Three"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Unlabeled content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path,
        (arabic_book, urdu_book, unlabeled_book),
        (
            database_path.parent / "arabic.mjbz",
            database_path.parent / "urdu.mjbz",
            database_path.parent / "unlabeled.mjbz",
        ),
    )


def test_search_ranks_by_cosine_similarity_to_the_query(tmp_path: Path) -> None:
    """The stored embedding closest to the query embedding ranks first."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    repository = SqlitePageEmbeddingRepository(database_path)

    repository.store(
        (
            (1, 1, (1.0, 0.0)),
            (2, 1, (0.0, 1.0)),
        )
    )

    results = repository.search(embedding=(1.0, 0.0), limit=10)

    assert len(results) == 2
    assert results[0].book_id == 1
    assert results[0].title == "Book One"
    assert results[0].similarity > results[1].similarity


def test_search_respects_limit(tmp_path: Path) -> None:
    """No more than `limit` results are returned."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    repository = SqlitePageEmbeddingRepository(database_path)
    repository.store(((1, 1, (1.0, 0.0)), (2, 1, (0.9, 0.1))))

    results = repository.search(embedding=(1.0, 0.0), limit=1)

    assert len(results) == 1


def test_ensure_schema_creates_the_table_without_writing_any_rows(tmp_path: Path) -> None:
    """ensure_schema() makes PageEmbeddings queryable before any real store() call."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    repository = SqlitePageEmbeddingRepository(database_path)

    repository.ensure_schema()

    with sqlite3.connect(database_path) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'PageEmbeddings'"
        ).fetchone()
        assert exists is not None
        count = connection.execute("SELECT COUNT(*) FROM PageEmbeddings").fetchone()[0]
        assert count == 0


def test_store_upserts_existing_book_and_page(tmp_path: Path) -> None:
    """Storing the same (book_id, page_number) twice replaces the embedding."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    repository = SqlitePageEmbeddingRepository(database_path)

    repository.store(((1, 1, (1.0, 0.0)),))
    repository.store(((1, 1, (0.0, 1.0)),))

    results = repository.search(embedding=(0.0, 1.0), limit=10)
    matching = next(result for result in results if result.book_id == 1)
    assert matching.similarity > 0.99


def test_query_language_boost_lets_a_same_language_match_outrank_a_closer_other_language_one(
    tmp_path: Path,
) -> None:
    """Real, confirmed fix: without the boost, a numerically closer
    other-language page always wins even when a same-language page is
    a genuinely reasonable match - see SAME_LANGUAGE_BOOST's docstring
    for the real evidence this value came from."""
    database_path = tmp_path / "books.db"
    _seed_database_with_languages(database_path)
    repository = SqlitePageEmbeddingRepository(database_path)
    # Arabic book (id 1) is a slightly worse raw match than the Urdu
    # book (id 2) for this query vector.
    repository.store(((1, 1, (0.85, 0.1)), (2, 1, (0.9, 0.0)), (3, 1, (0.1, 0.85))))

    without_boost = repository.search(embedding=(1.0, 0.0), limit=1)
    with_boost = repository.search(embedding=(1.0, 0.0), limit=1, query_language="Arabic")

    assert without_boost[0].book_id == 2  # Urdu book wins on raw similarity alone
    assert with_boost[0].book_id == 1  # Arabic book wins once the query is detected as Arabic


def test_query_language_boost_does_not_change_the_displayed_similarity_score(
    tmp_path: Path,
) -> None:
    """The boost only affects ranking order - the real, unboosted cosine
    similarity is still what's shown to the user."""
    database_path = tmp_path / "books.db"
    _seed_database_with_languages(database_path)
    repository = SqlitePageEmbeddingRepository(database_path)
    repository.store(((1, 1, (0.85, 0.1)),))

    without_boost = repository.search(embedding=(1.0, 0.0), limit=1)
    with_boost = repository.search(embedding=(1.0, 0.0), limit=1, query_language="Arabic")

    assert with_boost[0].similarity == without_boost[0].similarity


def test_a_book_with_no_recorded_language_is_never_boosted(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_languages(database_path)
    repository = SqlitePageEmbeddingRepository(database_path)
    repository.store(((3, 1, (1.0, 0.0)),))  # unlabeled book

    results = repository.search(embedding=(1.0, 0.0), limit=1, query_language="Arabic")

    assert results[0].similarity < 1.01  # no boost applied, still the real raw score


def test_no_query_language_given_applies_no_boost(tmp_path: Path) -> None:
    """Existing callers that don't pass query_language keep today's
    exact behavior - a real backward-compatibility guarantee."""
    database_path = tmp_path / "books.db"
    _seed_database_with_languages(database_path)
    repository = SqlitePageEmbeddingRepository(database_path)
    repository.store(((1, 1, (0.85, 0.1)), (2, 1, (0.9, 0.0))))

    results = repository.search(embedding=(1.0, 0.0), limit=1)

    assert results[0].book_id == 2  # raw closest match wins, no language involved at all
