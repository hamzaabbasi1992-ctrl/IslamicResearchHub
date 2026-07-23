"""Tests for detecting and storing possible cross-library duplicate books."""

from pathlib import Path

from islamic_research_hub.domain.models.book import Book
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


def _book(name: str, mjbn: str | None = None) -> Book:
    """Build a minimal book with the given title and optional source id."""
    information = {"Name": name}
    if mjbn is not None:
        information["MJBN"] = mjbn
    return Book(information=information, categories=(), table_of_contents=(), pages=())


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
