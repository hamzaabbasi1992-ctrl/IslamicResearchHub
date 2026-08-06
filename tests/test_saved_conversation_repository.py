"""Tests for the real saved-AI-conversation repository (Phase 14 deferred scope)."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.infrastructure.persistence.saved_conversation_repository import (
    SavedConversationNameTakenError,
    SavedConversationRepository,
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


def test_save_conversation_then_list_returns_the_real_question_and_answer(
    tmp_path: Path,
) -> None:
    repo = SavedConversationRepository(_migrated_database(tmp_path))

    repo.save_conversation(
        "Zakat on gold jewelry",
        "Is zakat due on gold jewelry a woman wears daily?",
        "Yes, according to the majority view...",
    )

    saved = repo.list_conversations()
    assert len(saved) == 1
    assert saved[0].name == "Zakat on gold jewelry"
    assert saved[0].question == "Is zakat due on gold jewelry a woman wears daily?"
    assert saved[0].answer == "Yes, according to the majority view..."


def test_save_conversation_with_a_taken_name_raises(tmp_path: Path) -> None:
    repo = SavedConversationRepository(_migrated_database(tmp_path))
    repo.save_conversation("My conversation", "Question one", "Answer one")

    with pytest.raises(SavedConversationNameTakenError):
        repo.save_conversation("My conversation", "Question two", "Answer two")


def test_save_conversation_rejects_a_blank_name(tmp_path: Path) -> None:
    repo = SavedConversationRepository(_migrated_database(tmp_path))

    with pytest.raises(ValueError):
        repo.save_conversation("   ", "Question", "Answer")


def test_save_conversation_rejects_a_blank_question(tmp_path: Path) -> None:
    repo = SavedConversationRepository(_migrated_database(tmp_path))

    with pytest.raises(ValueError):
        repo.save_conversation("My conversation", "   ", "Answer")


def test_save_conversation_rejects_a_blank_answer(tmp_path: Path) -> None:
    repo = SavedConversationRepository(_migrated_database(tmp_path))

    with pytest.raises(ValueError):
        repo.save_conversation("My conversation", "Question", "   ")


def test_list_conversations_orders_most_recent_first(tmp_path: Path) -> None:
    repo = SavedConversationRepository(_migrated_database(tmp_path))
    repo.save_conversation("First", "Question one", "Answer one")
    repo.save_conversation("Second", "Question two", "Answer two")

    names = [saved.name for saved in repo.list_conversations()]

    assert names == ["Second", "First"]


def test_delete_conversation_removes_it(tmp_path: Path) -> None:
    repo = SavedConversationRepository(_migrated_database(tmp_path))
    saved_id = repo.save_conversation("My conversation", "Question", "Answer")

    repo.delete_conversation(saved_id)

    assert repo.list_conversations() == ()


def test_list_conversations_is_empty_with_none_saved(tmp_path: Path) -> None:
    assert SavedConversationRepository(_migrated_database(tmp_path)).list_conversations() == ()


def test_all_operations_degrade_gracefully_on_a_pre_migration_database(tmp_path: Path) -> None:
    """Before the SavedConversations migration runs, every real operation
    is a safe no-op, not a crash - same discipline as SavedSearchRepository."""
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
    repo = SavedConversationRepository(database_path)

    saved_id = repo.save_conversation("My conversation", "Question", "Answer")
    assert repo.list_conversations() == ()
    repo.delete_conversation(saved_id)
