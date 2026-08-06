"""Tests for storing and reviewing real generated MCQ candidates."""

import sqlite3
from pathlib import Path

from islamic_research_hub.application.mcq_extraction import ExtractedMcq
from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.mcq_candidate_repository import (
    McqCandidateRepository,
)

_MCQ = ExtractedMcq(
    question="What is the ruling on zakat for gold below the nisab threshold?",
    options=("It is obligatory", "No zakat is due", "It is recommended", "It is forbidden"),
    correct_index=1,
    quoted_excerpt="A real verbatim excerpt from the source text.",
    citation="Book of Fiqh, Page 12, Paragraph 1",
)


def _seed_book(database_path: Path) -> int:
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    return 1


def test_add_and_list_a_real_candidate(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = McqCandidateRepository(database_path)

    candidate_id = repository.add_candidate(book_id, 10, 20, _MCQ)

    assert candidate_id > 0
    candidates = repository.list_candidates()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.book_id == book_id
    assert candidate.chunk_start_page == 10
    assert candidate.chunk_end_page == 20
    assert candidate.status == "pending"
    assert candidate.mcq == _MCQ  # full JSON round-trip fidelity


def test_filters_by_book_id(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = McqCandidateRepository(database_path)
    repository.add_candidate(book_id, 1, 5, _MCQ)

    assert len(repository.list_candidates(book_id=book_id)) == 1
    assert len(repository.list_candidates(book_id=999)) == 0


def test_confirm_persists_status(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = McqCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _MCQ)

    repository.confirm(candidate_id)

    assert repository.list_candidates()[0].status == "confirmed"


def test_dismiss_hides_by_default_and_visible_with_include_dismissed(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = McqCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _MCQ)

    repository.dismiss(candidate_id)

    assert repository.list_candidates() == ()
    assert len(repository.list_candidates(include_dismissed=True)) == 1


def test_filter_by_status_returns_only_that_status(tmp_path: Path) -> None:
    """Quiz mode's real use case: only ever show confirmed MCQs."""
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = McqCandidateRepository(database_path)
    pending_id = repository.add_candidate(book_id, 1, 5, _MCQ)
    confirmed_id = repository.add_candidate(book_id, 6, 10, _MCQ)
    repository.confirm(confirmed_id)

    confirmed_only = repository.list_candidates(status="confirmed")

    assert len(confirmed_only) == 1
    assert confirmed_only[0].id == confirmed_id
    assert confirmed_only[0].id != pending_id


def test_remove_book_clears_its_mcq_candidates(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    mcq_repository = McqCandidateRepository(database_path)
    mcq_repository.add_candidate(book_id, 1, 5, _MCQ)

    DuplicateCandidateRepository(database_path).remove_book(book_id)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM McqCandidates").fetchone()[0]
    assert count == 0
