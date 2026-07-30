"""Tests for the real per-book personal rating repository."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.book_rating_repository import (
    BookRatingRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner


def _migrated_database(tmp_path: Path) -> Path:
    """Create a real, fully-migrated database with one real book (BookID 1)."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    return database_path


def test_set_rating_then_get_returns_the_real_rating(tmp_path: Path) -> None:
    repo = BookRatingRepository(_migrated_database(tmp_path))

    repo.set_rating(1, 4)

    assert repo.get_rating(1) == 4


def test_set_rating_again_replaces_the_previous_one(tmp_path: Path) -> None:
    """Re-rating a book updates it in place - one real rating per book, not a history."""
    repo = BookRatingRepository(_migrated_database(tmp_path))
    repo.set_rating(1, 2)

    repo.set_rating(1, 5)

    assert repo.get_rating(1) == 5


def test_clear_rating_removes_it(tmp_path: Path) -> None:
    repo = BookRatingRepository(_migrated_database(tmp_path))
    repo.set_rating(1, 3)

    repo.clear_rating(1)

    assert repo.get_rating(1) is None


def test_get_rating_returns_none_for_an_unrated_book(tmp_path: Path) -> None:
    repo = BookRatingRepository(_migrated_database(tmp_path))

    assert repo.get_rating(1) is None


@pytest.mark.parametrize("rating", [0, -1, 6, 100])
def test_set_rating_rejects_out_of_range_values(tmp_path: Path, rating: int) -> None:
    repo = BookRatingRepository(_migrated_database(tmp_path))

    with pytest.raises(ValueError):
        repo.set_rating(1, rating)


@pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
def test_set_rating_accepts_every_value_in_range(tmp_path: Path, rating: int) -> None:
    repo = BookRatingRepository(_migrated_database(tmp_path))

    repo.set_rating(1, rating)

    assert repo.get_rating(1) == rating


def test_all_operations_degrade_gracefully_on_a_pre_migration_database(tmp_path: Path) -> None:
    """Before migration 12 runs, every real operation is a safe no-op, not a crash."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    repo = BookRatingRepository(database_path)

    repo.set_rating(1, 5)
    assert repo.get_rating(1) is None
    repo.clear_rating(1)
