"""Tests for detecting and storing possible cross-library duplicate books."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


def _book(name: str, mjbn: str | None = None, with_content: bool = False) -> Book:
    """Build a minimal book with the given title, optional source id and content."""
    information = {"Name": name}
    if mjbn is not None:
        information["MJBN"] = mjbn
    pages = (Page(1, 1, "Some real page content", None),) if with_content else ()
    return Book(information=information, categories=(), table_of_contents=(), pages=pages)


def test_detects_same_title_and_source_id_across_libraries(tmp_path: Path) -> None:
    """An exact title and source id match across libraries is flagged."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Shared Title", mjbn="42"),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (_book("Shared Title", mjbn="42"),),
        (tmp_path / "b.mjbz",),
        library_name="Library B",
    )

    count = DuplicateCandidateRepository(database_path).detect_and_store()

    assert count == 1
    candidates = DuplicateCandidateRepository(database_path).list_candidates()
    assert len(candidates) == 1
    assert candidates[0].match_type == "exact_title_and_source_id"


def test_detects_same_title_with_different_source_id(tmp_path: Path) -> None:
    """A title match with no matching source id is flagged with a weaker match type."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Shared Title", mjbn="1"),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (_book("Shared Title"),),
        (tmp_path / "b.mjbz",),
        library_name="Library B",
    )

    DuplicateCandidateRepository(database_path).detect_and_store()

    candidates = DuplicateCandidateRepository(database_path).list_candidates()
    assert len(candidates) == 1
    assert candidates[0].match_type == "exact_title"


def test_does_not_flag_same_title_within_one_library(tmp_path: Path) -> None:
    """A repeated title within the same library is not a cross-library candidate."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Same Title"),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (_book("Same Title"),),
        (tmp_path / "b.mjbz",),
        library_name="Library A",
    )

    count = DuplicateCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_detect_and_store_is_idempotent_on_rerun(tmp_path: Path) -> None:
    """Re-running detection recomputes rather than accumulating stale rows."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Shared Title"),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (_book("Shared Title"),),
        (tmp_path / "b.mjbz",),
        library_name="Library B",
    )

    duplicate_repository = DuplicateCandidateRepository(database_path)
    duplicate_repository.detect_and_store()
    count = duplicate_repository.detect_and_store()

    assert count == 1
    assert len(duplicate_repository.list_candidates()) == 1


def test_resolve_empty_stub_duplicates_removes_the_contentless_side(tmp_path: Path) -> None:
    """When one side has no content, only the empty side is removed."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Shared Title", with_content=False),),
        (tmp_path / "empty.mjbz",),
        library_name="Metadata Only",
    )
    repository.import_books(
        database_path,
        (_book("Shared Title", with_content=True),),
        (tmp_path / "real.mjbz",),
        library_name="Real Content",
    )
    duplicate_repository = DuplicateCandidateRepository(database_path)
    duplicate_repository.detect_and_store()

    removed_count = duplicate_repository.resolve_empty_stub_duplicates()

    assert removed_count == 1
    assert duplicate_repository.list_candidates() == ()
    with sqlite3.connect(database_path) as connection:
        remaining_titles = [
            row[0] for row in connection.execute("SELECT Title FROM Books").fetchall()
        ]
    assert remaining_titles == ["Shared Title"]
    with sqlite3.connect(database_path) as connection:
        remaining_source = connection.execute("SELECT Source FROM Books").fetchone()[0]
    assert "real.mjbz" in remaining_source


def test_resolve_empty_stub_duplicates_leaves_pairs_with_content_on_both_sides(
    tmp_path: Path,
) -> None:
    """When both sides have real content, neither is removed."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Shared Title", with_content=True),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (_book("Shared Title", with_content=True),),
        (tmp_path / "b.mjbz",),
        library_name="Library B",
    )
    duplicate_repository = DuplicateCandidateRepository(database_path)
    duplicate_repository.detect_and_store()

    removed_count = duplicate_repository.resolve_empty_stub_duplicates()

    assert removed_count == 0
    assert len(duplicate_repository.list_candidates()) == 1
    with sqlite3.connect(database_path) as connection:
        book_count = connection.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
    assert book_count == 2
