"""Tests for storing and reviewing real extracted narrator candidates."""

import sqlite3
from pathlib import Path

from islamic_research_hub.application.narrator_extraction import ExtractedNarrator
from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.narrator_candidate_repository import (
    NarratorCandidateRepository,
)

_NARRATOR = ExtractedNarrator(
    name="Abu Hurayrah",
    alternate_names=("Abd al-Rahman ibn Sakhr",),
    kunya_nasab="Abu Hurayrah al-Dawsi",
    generation="Companion",
    hadith_reference="Hadith 12, Chapter of Faith",
    quoted_excerpt="A real verbatim excerpt naming this narrator.",
    citation="Book of Hadith, Page 5, Paragraph 1",
)


def _seed_book(database_path: Path) -> int:
    book = Book(
        information={"Name": "Book of Hadith"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    return 1


def test_add_and_list_a_real_candidate(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = NarratorCandidateRepository(database_path)

    candidate_id = repository.add_candidate(book_id, 10, 20, _NARRATOR)

    assert candidate_id > 0
    candidates = repository.list_candidates()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.book_id == book_id
    assert candidate.chunk_start_page == 10
    assert candidate.chunk_end_page == 20
    assert candidate.status == "pending"
    assert candidate.narrator == _NARRATOR  # full JSON round-trip fidelity


def test_json_round_trip_preserves_all_fields_including_nulls_and_lists(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    narrator_with_nulls = ExtractedNarrator(
        name="Unnamed Narrator",
        alternate_names=(),
        kunya_nasab=None,
        generation=None,
        hadith_reference="Hadith 1",
        quoted_excerpt="Excerpt.",
        citation="Book X, Page 1, Paragraph 1",
    )
    repository = NarratorCandidateRepository(database_path)

    repository.add_candidate(book_id, 1, 5, narrator_with_nulls)

    stored = repository.list_candidates()[0].narrator
    assert stored.kunya_nasab is None
    assert stored.generation is None
    assert stored.alternate_names == ()


def test_filters_by_book_id(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = NarratorCandidateRepository(database_path)
    repository.add_candidate(book_id, 1, 5, _NARRATOR)

    assert len(repository.list_candidates(book_id=book_id)) == 1
    assert len(repository.list_candidates(book_id=999)) == 0


def test_confirm_persists_status(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = NarratorCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _NARRATOR)

    repository.confirm(candidate_id)

    candidates = repository.list_candidates()
    assert candidates[0].status == "confirmed"


def test_dismiss_hides_by_default_and_visible_with_include_dismissed(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = NarratorCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _NARRATOR)

    repository.dismiss(candidate_id)

    assert repository.list_candidates() == ()
    assert len(repository.list_candidates(include_dismissed=True)) == 1


def test_remove_book_clears_its_narrator_candidates(tmp_path: Path) -> None:
    """NarratorCandidates has a single BookID column, so it joins
    DuplicateCandidateRepository's generic _BOOK_REFERENCING_TABLES
    cleanup loop directly (same shape as EventCandidates)."""
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    narrator_repository = NarratorCandidateRepository(database_path)
    narrator_repository.add_candidate(book_id, 1, 5, _NARRATOR)

    DuplicateCandidateRepository(database_path).remove_book(book_id)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM NarratorCandidates").fetchone()[0]
    assert count == 0
