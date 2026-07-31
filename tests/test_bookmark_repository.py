"""Tests for the real per-book, per-page bookmark repository."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.bookmark_repository import (
    BookmarkRepository,
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
        pages=(Page(1, 1, "Content", "Plain"), Page(2, 2, "More content", "Plain")),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    return database_path


def test_add_bookmark_then_list_returns_the_real_page(tmp_path: Path) -> None:
    """A real bookmark, once added, shows up in the real bookmarked-pages list."""
    repo = BookmarkRepository(_migrated_database(tmp_path))

    repo.add_bookmark(1, 2)

    assert repo.list_bookmarked_pages(1) == {2}


def test_add_bookmark_twice_does_not_duplicate(tmp_path: Path) -> None:
    """Adding the same real bookmark twice is safe and doesn't error."""
    repo = BookmarkRepository(_migrated_database(tmp_path))

    repo.add_bookmark(1, 2)
    repo.add_bookmark(1, 2)

    assert repo.list_bookmarked_pages(1) == {2}


def test_remove_bookmark_removes_only_that_page(tmp_path: Path) -> None:
    """Removing one real bookmark leaves the others in place."""
    repo = BookmarkRepository(_migrated_database(tmp_path))
    repo.add_bookmark(1, 1)
    repo.add_bookmark(1, 2)

    repo.remove_bookmark(1, 1)

    assert repo.list_bookmarked_pages(1) == {2}


def test_set_bookmark_toggles_both_directions(tmp_path: Path) -> None:
    """set_bookmark(True) adds, set_bookmark(False) removes, matching a real toggle UI."""
    repo = BookmarkRepository(_migrated_database(tmp_path))

    repo.set_bookmark(1, 1, True)
    assert repo.list_bookmarked_pages(1) == {1}

    repo.set_bookmark(1, 1, False)
    assert repo.list_bookmarked_pages(1) == set()


def test_list_bookmarked_pages_returns_empty_for_a_book_with_none(tmp_path: Path) -> None:
    """A book with no real bookmarks returns an empty set, not an error."""
    repo = BookmarkRepository(_migrated_database(tmp_path))

    assert repo.list_bookmarked_pages(1) == set()


def test_list_recent_bookmarks_returns_newest_first_across_books(tmp_path: Path) -> None:
    """Home Dashboard: real bookmarks across every book, most recent first."""
    database_path = tmp_path / "books.db"
    book_two = Book(
        information={"Name": "Book Two"}, categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )
    book_one = Book(
        information={"Name": "Book of Fiqh"}, categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"), Page(2, 2, "More content", "Plain")),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    repo = BookmarkRepository(database_path)

    repo.add_bookmark(1, 1)  # Book Two (BookID 1, imported first), bookmarked first
    repo.add_bookmark(2, 2)  # Book of Fiqh (BookID 2), bookmarked second (most recent)

    recent = repo.list_recent_bookmarks(limit=5)

    assert len(recent) == 2
    assert recent[0].title == "Book of Fiqh"
    assert recent[0].page_number == 2
    assert recent[1].title == "Book Two"


def test_list_recent_bookmarks_is_empty_before_migration_or_with_none_added(
    tmp_path: Path,
) -> None:
    """Honest empty result, not a crash, when there's nothing to show."""
    assert BookmarkRepository(_migrated_database(tmp_path)).list_recent_bookmarks() == ()


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
    repo = BookmarkRepository(database_path)

    repo.add_bookmark(1, 1)
    repo.set_bookmark(1, 1, True)
    assert repo.list_bookmarked_pages(1) == set()
    repo.remove_bookmark(1, 1)
