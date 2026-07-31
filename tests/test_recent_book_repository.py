"""Tests for the real "recently opened" book repository."""

import sqlite3
import time
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (
    RecentBookRepository,
)


def _migrated_database(tmp_path: Path) -> Path:
    """Create a real, fully-migrated database with two real books."""
    database_path = tmp_path / "books.db"
    book_one = Book(
        information={"Name": "Book One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    book_two = Book(
        information={"Name": "Book Two"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    return database_path


def test_record_open_then_list_recent_shows_the_real_book(tmp_path: Path) -> None:
    """A real recorded open shows up in the recent-books list."""
    repo = RecentBookRepository(_migrated_database(tmp_path))

    repo.record_open(1, page_number=5)

    recent = repo.list_recent()
    assert len(recent) == 1
    assert recent[0].book_id == 1
    assert recent[0].title == "Book One"


def test_list_recent_orders_most_recently_opened_first(tmp_path: Path) -> None:
    """Opening book two after book one puts book two first in the real list."""
    repo = RecentBookRepository(_migrated_database(tmp_path))

    repo.record_open(1)
    time.sleep(1.1)  # SQLite datetime('now') has 1-second resolution
    repo.record_open(2)

    recent = repo.list_recent()
    assert [summary.book_id for summary in recent] == [2, 1]


def test_reopening_a_book_updates_its_existing_row_not_a_new_one(tmp_path: Path) -> None:
    """Re-opening the same real book doesn't create a duplicate recent-books row."""
    repo = RecentBookRepository(_migrated_database(tmp_path))

    repo.record_open(1, page_number=1)
    repo.record_open(1, page_number=10)

    recent = repo.list_recent()
    assert len(recent) == 1
    assert repo.last_page_number(1) == 10


def test_last_page_number_returns_none_for_a_book_never_opened(tmp_path: Path) -> None:
    """A book with no real recent-open record returns None, not an error."""
    repo = RecentBookRepository(_migrated_database(tmp_path))

    assert repo.last_page_number(1) is None


def test_list_recent_respects_the_limit(tmp_path: Path) -> None:
    """A real limit caps how many recent books are returned."""
    repo = RecentBookRepository(_migrated_database(tmp_path))
    repo.record_open(1)
    repo.record_open(2)

    assert len(repo.list_recent(limit=1)) == 1


def test_list_recent_categories_returns_real_categories_newest_book_first(
    tmp_path: Path,
) -> None:
    """Home Dashboard: real category names from recently-opened books' real
    Categories rows, most-recently-opened book first."""
    database_path = tmp_path / "books.db"
    fiqh = Category(mjcn=9, name="الفقه", parent_mjcn=0, sort_key=1)
    hadith = Category(mjcn=10, name="الحديث", parent_mjcn=0, sort_key=1)
    book_one = Book(
        information={"Name": "Book One"}, categories=(fiqh,), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    book_two = Book(
        information={"Name": "Book Two"}, categories=(hadith,), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    repo = RecentBookRepository(database_path)

    repo.record_open(1)
    time.sleep(1.1)  # SQLite datetime('now') has 1-second resolution
    repo.record_open(2)

    assert repo.list_recent_categories() == ("الحديث", "الفقه")


def test_list_recent_categories_is_empty_with_nothing_opened(tmp_path: Path) -> None:
    """Honest empty result, not a crash, when nothing has been opened yet."""
    assert RecentBookRepository(_migrated_database(tmp_path)).list_recent_categories() == ()


def test_all_operations_degrade_gracefully_on_a_pre_migration_database(tmp_path: Path) -> None:
    """Before migration 8 runs, every real operation is a safe no-op, not a crash."""
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
    repo = RecentBookRepository(database_path)

    repo.record_open(1, page_number=1)

    assert repo.list_recent() == ()
    assert repo.last_page_number(1) is None
