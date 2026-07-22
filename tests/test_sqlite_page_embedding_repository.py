"""Tests for the pilot-scale SQLite page embedding store and search."""

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
