"""Tests for the real named-collections repository (Phase 14 Milestone 1)."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.collection_repository import (
    CollectionNameTakenError,
    CollectionRepository,
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


def test_create_collection_then_list_returns_it_with_a_zero_item_count(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))

    repo.create_collection("Zakat research")

    collections = repo.list_collections()
    assert len(collections) == 1
    assert collections[0].name == "Zakat research"
    assert collections[0].item_count == 0


def test_create_collection_with_a_taken_name_raises(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))
    repo.create_collection("Zakat research")

    with pytest.raises(CollectionNameTakenError):
        repo.create_collection("Zakat research")


def test_create_collection_rejects_a_blank_name(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))

    with pytest.raises(ValueError):
        repo.create_collection("   ")


def test_rename_collection_changes_the_real_name(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))
    collection_id = repo.create_collection("Old name")

    repo.rename_collection(collection_id, "New name")

    assert repo.list_collections()[0].name == "New name"


def test_rename_collection_to_a_taken_name_raises(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))
    repo.create_collection("Existing")
    collection_id = repo.create_collection("Renaming this one")

    with pytest.raises(CollectionNameTakenError):
        repo.rename_collection(collection_id, "Existing")


def test_add_item_then_list_returns_the_real_book_and_page(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))
    collection_id = repo.create_collection("Zakat research")

    repo.add_item(collection_id, book_id=1, page_number=2)

    items = repo.list_items(collection_id)
    assert len(items) == 1
    assert items[0].book_id == 1
    assert items[0].page_number == 2
    assert items[0].book_title == "Book of Fiqh"


def test_add_item_twice_does_not_duplicate(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))
    collection_id = repo.create_collection("Zakat research")

    repo.add_item(collection_id, 1, 1)
    repo.add_item(collection_id, 1, 1)

    assert len(repo.list_items(collection_id)) == 1


def test_add_item_updates_the_collections_real_item_count(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))
    collection_id = repo.create_collection("Zakat research")

    repo.add_item(collection_id, 1, 1)
    repo.add_item(collection_id, 1, 2)

    assert repo.list_collections()[0].item_count == 2


def test_remove_item_removes_only_that_page(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))
    collection_id = repo.create_collection("Zakat research")
    repo.add_item(collection_id, 1, 1)
    repo.add_item(collection_id, 1, 2)

    repo.remove_item(collection_id, 1, 1)

    items = repo.list_items(collection_id)
    assert len(items) == 1
    assert items[0].page_number == 2


def test_delete_collection_removes_it_and_its_items(tmp_path: Path) -> None:
    repo = CollectionRepository(_migrated_database(tmp_path))
    collection_id = repo.create_collection("Zakat research")
    repo.add_item(collection_id, 1, 1)

    repo.delete_collection(collection_id)

    assert repo.list_collections() == ()


def test_list_collections_is_empty_before_migration_or_with_none_created(
    tmp_path: Path,
) -> None:
    assert CollectionRepository(_migrated_database(tmp_path)).list_collections() == ()


def test_all_operations_degrade_gracefully_on_a_pre_migration_database(tmp_path: Path) -> None:
    """Before the Collections migration runs, every real operation is a
    safe no-op, not a crash - same discipline as BookmarkRepository."""
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
    repo = CollectionRepository(database_path)

    collection_id = repo.create_collection("Zakat research")
    repo.rename_collection(collection_id, "Renamed")
    repo.add_item(collection_id, 1, 1)
    assert repo.list_collections() == ()
    assert repo.list_items(collection_id) == ()
    repo.remove_item(collection_id, 1, 1)
    repo.delete_collection(collection_id)
