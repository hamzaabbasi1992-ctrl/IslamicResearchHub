"""Tests for storing and reviewing real extracted event candidates."""

import sqlite3
from pathlib import Path

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import (
    EventCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)

_EVENT = ExtractedEvent(
    title="Battle of Badr",
    alternate_names=("Ghazwa Badr",),
    subject="battle",
    date_hijri="17 Ramadan, 2 AH",
    date_gregorian="624 CE",
    location="Badr",
    background="Tensions between Mecca and Medina.",
    summary="The first major battle.",
    key_figures=("Prophet Muhammad",),
    quoted_excerpt="A real verbatim excerpt from the source text.",
    citation="Book of Seerah, Page 12, Paragraph 1",
)


def _seed_book(database_path: Path) -> int:
    book = Book(
        information={"Name": "Book of Seerah"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    return 1


def test_add_and_list_a_real_candidate(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = EventCandidateRepository(database_path)

    candidate_id = repository.add_candidate(book_id, 10, 20, _EVENT)

    assert candidate_id > 0
    candidates = repository.list_candidates()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.book_id == book_id
    assert candidate.chunk_start_page == 10
    assert candidate.chunk_end_page == 20
    assert candidate.status == "pending"
    assert candidate.event == _EVENT  # full JSON round-trip fidelity


def test_json_round_trip_preserves_all_fields_including_nulls_and_lists(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    event_with_nulls = ExtractedEvent(
        title="Undated Event",
        alternate_names=(),
        subject="topic",
        date_hijri=None,
        date_gregorian=None,
        location=None,
        background="Background text.",
        summary="Summary text.",
        key_figures=(),
        quoted_excerpt="Excerpt.",
        citation="Book X, Page 1, Paragraph 1",
    )
    repository = EventCandidateRepository(database_path)

    repository.add_candidate(book_id, 1, 5, event_with_nulls)

    stored = repository.list_candidates()[0].event
    assert stored.date_hijri is None
    assert stored.alternate_names == ()
    assert stored.key_figures == ()


def test_filters_by_book_id(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = EventCandidateRepository(database_path)
    repository.add_candidate(book_id, 1, 5, _EVENT)

    assert len(repository.list_candidates(book_id=book_id)) == 1
    assert len(repository.list_candidates(book_id=999)) == 0


def test_confirm_persists_status(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = EventCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _EVENT)

    repository.confirm(candidate_id)

    candidates = repository.list_candidates()
    assert candidates[0].status == "confirmed"


def test_dismiss_hides_by_default_and_visible_with_include_dismissed(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = EventCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _EVENT)

    repository.dismiss(candidate_id)

    assert repository.list_candidates() == ()
    assert len(repository.list_candidates(include_dismissed=True)) == 1


def test_remove_book_clears_its_event_candidates(tmp_path: Path) -> None:
    """EventCandidates has a single BookID column, so it joins
    DuplicateCandidateRepository's generic _BOOK_REFERENCING_TABLES
    cleanup loop directly (unlike CitationCandidates' two-sided case)."""
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    event_repository = EventCandidateRepository(database_path)
    event_repository.add_candidate(book_id, 1, 5, _EVENT)

    DuplicateCandidateRepository(database_path).remove_book(book_id)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM EventCandidates").fetchone()[0]
    assert count == 0
