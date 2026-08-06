"""Tests for the real saved-search repository (Phase 14 deferred scope)."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.infrastructure.persistence.saved_search_repository import (
    SavedSearchNameTakenError,
    SavedSearchRepository,
)


def _migrated_database(tmp_path: Path) -> Path:
    """Create a real, fully-migrated database with one real book."""
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


def test_save_search_then_list_returns_every_real_filter(tmp_path: Path) -> None:
    repo = SavedSearchRepository(_migrated_database(tmp_path))

    repo.save_search(
        "Zakat, Maktaba Jibreel only",
        query="zakat",
        library="Maktaba Jibreel (Mobile)",
        author="Imam Ghazali",
        category="Fiqh",
        exact=True,
        scope="both",
        search_target="content",
    )

    searches = repo.list_searches()
    assert len(searches) == 1
    saved = searches[0]
    assert saved.name == "Zakat, Maktaba Jibreel only"
    assert saved.query == "zakat"
    assert saved.library == "Maktaba Jibreel (Mobile)"
    assert saved.author == "Imam Ghazali"
    assert saved.category == "Fiqh"
    assert saved.exact is True
    assert saved.scope == "both"
    assert saved.search_target == "content"


def test_save_search_with_no_filters_stores_real_nones(tmp_path: Path) -> None:
    repo = SavedSearchRepository(_migrated_database(tmp_path))

    repo.save_search(
        "Just a query",
        query="patience",
        library=None,
        author=None,
        category=None,
        exact=False,
        scope="content",
        search_target="both",
    )

    saved = repo.list_searches()[0]
    assert saved.library is None
    assert saved.author is None
    assert saved.category is None
    assert saved.exact is False


def test_save_search_with_a_taken_name_raises(tmp_path: Path) -> None:
    repo = SavedSearchRepository(_migrated_database(tmp_path))
    repo.save_search("My search", "zakat", None, None, None, False, "content", "both")

    with pytest.raises(SavedSearchNameTakenError):
        repo.save_search("My search", "fasting", None, None, None, False, "content", "both")


def test_save_search_rejects_a_blank_name(tmp_path: Path) -> None:
    repo = SavedSearchRepository(_migrated_database(tmp_path))

    with pytest.raises(ValueError):
        repo.save_search("   ", "zakat", None, None, None, False, "content", "both")


def test_save_search_rejects_a_blank_query(tmp_path: Path) -> None:
    repo = SavedSearchRepository(_migrated_database(tmp_path))

    with pytest.raises(ValueError):
        repo.save_search("My search", "   ", None, None, None, False, "content", "both")


def test_list_searches_orders_most_recent_first(tmp_path: Path) -> None:
    repo = SavedSearchRepository(_migrated_database(tmp_path))
    repo.save_search("First", "zakat", None, None, None, False, "content", "both")
    repo.save_search("Second", "fasting", None, None, None, False, "content", "both")

    names = [saved.name for saved in repo.list_searches()]

    assert names == ["Second", "First"]


def test_delete_search_removes_it(tmp_path: Path) -> None:
    repo = SavedSearchRepository(_migrated_database(tmp_path))
    saved_id = repo.save_search(
        "My search", "zakat", None, None, None, False, "content", "both"
    )

    repo.delete_search(saved_id)

    assert repo.list_searches() == ()


def test_list_searches_is_empty_with_none_saved(tmp_path: Path) -> None:
    assert SavedSearchRepository(_migrated_database(tmp_path)).list_searches() == ()


def test_all_operations_degrade_gracefully_on_a_pre_migration_database(tmp_path: Path) -> None:
    """Before the SavedSearches migration runs, every real operation is a
    safe no-op, not a crash - same discipline as CollectionRepository."""
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
    repo = SavedSearchRepository(database_path)

    saved_id = repo.save_search(
        "My search", "zakat", None, None, None, False, "content", "both"
    )
    assert repo.list_searches() == ()
    repo.delete_search(saved_id)
