"""Tests for storing and reviewing real generated flashcard candidates."""

import sqlite3
from pathlib import Path

from islamic_research_hub.application.flashcard_extraction import ExtractedFlashcard
from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.flashcard_candidate_repository import (
    FlashcardCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)

_FLASHCARD = ExtractedFlashcard(
    front="What is the ruling on zakat for gold below the nisab threshold?",
    back="No zakat is due until the nisab threshold is reached.",
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
    repository = FlashcardCandidateRepository(database_path)

    candidate_id = repository.add_candidate(book_id, 10, 20, _FLASHCARD)

    assert candidate_id > 0
    candidates = repository.list_candidates()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.book_id == book_id
    assert candidate.chunk_start_page == 10
    assert candidate.chunk_end_page == 20
    assert candidate.status == "pending"
    assert candidate.flashcard == _FLASHCARD  # full JSON round-trip fidelity


def test_filters_by_book_id(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    repository.add_candidate(book_id, 1, 5, _FLASHCARD)

    assert len(repository.list_candidates(book_id=book_id)) == 1
    assert len(repository.list_candidates(book_id=999)) == 0


def test_confirm_persists_status(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)

    repository.confirm(candidate_id)

    assert repository.list_candidates()[0].status == "confirmed"


def test_dismiss_hides_by_default_and_visible_with_include_dismissed(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)

    repository.dismiss(candidate_id)

    assert repository.list_candidates() == ()
    assert len(repository.list_candidates(include_dismissed=True)) == 1


def test_filter_by_status_returns_only_that_status(tmp_path: Path) -> None:
    """Study mode's real use case: only ever show confirmed flashcards."""
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    pending_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)
    confirmed_id = repository.add_candidate(book_id, 6, 10, _FLASHCARD)
    repository.confirm(confirmed_id)

    confirmed_only = repository.list_candidates(status="confirmed")

    assert len(confirmed_only) == 1
    assert confirmed_only[0].id == confirmed_id
    assert confirmed_only[0].id != pending_id


def test_record_review_creates_a_real_schedule_on_first_review(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)
    repository.confirm(candidate_id)

    state = repository.record_review(candidate_id, "good")

    assert state.flashcard_candidate_id == candidate_id
    assert state.repetitions == 1
    assert state.interval_days == 1
    assert state.due_at > state.last_reviewed_at


def test_get_review_state_is_none_before_any_real_review(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)

    assert repository.get_review_state(candidate_id) is None


def test_get_review_state_returns_the_persisted_schedule(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)
    repository.confirm(candidate_id)
    repository.record_review(candidate_id, "good")

    state = repository.get_review_state(candidate_id)

    assert state is not None
    assert state.repetitions == 1


def test_second_review_updates_the_same_real_row_not_a_new_one(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)
    repository.confirm(candidate_id)
    repository.record_review(candidate_id, "good")

    state = repository.record_review(candidate_id, "good")

    assert state.repetitions == 2
    assert state.interval_days == 6
    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM FlashcardReviewState").fetchone()[0]
    assert count == 1


def test_due_candidates_includes_a_confirmed_card_never_reviewed_yet(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)
    repository.confirm(candidate_id)

    due = repository.due_candidates()

    assert len(due) == 1
    assert due[0].id == candidate_id


def test_due_candidates_excludes_a_card_reviewed_and_not_yet_due(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)
    repository.confirm(candidate_id)
    repository.record_review(candidate_id, "easy")  # real interval > 0 days

    assert repository.due_candidates() == ()


def test_due_candidates_excludes_pending_and_dismissed_candidates(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    pending_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)
    dismissed_id = repository.add_candidate(book_id, 6, 10, _FLASHCARD)
    repository.dismiss(dismissed_id)

    due = repository.due_candidates()

    assert due == ()
    assert pending_id != dismissed_id  # both real candidates exist, neither is due


def test_due_candidates_includes_a_card_whose_real_due_date_has_passed(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    repository = FlashcardCandidateRepository(database_path)
    candidate_id = repository.add_candidate(book_id, 1, 5, _FLASHCARD)
    repository.confirm(candidate_id)
    repository.record_review(candidate_id, "good")  # due in 1 real day

    due = repository.due_candidates(as_of="2999-01-01 00:00:00")

    assert len(due) == 1
    assert due[0].id == candidate_id


def test_remove_book_clears_its_flashcard_candidates(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    book_id = _seed_book(database_path)
    flashcard_repository = FlashcardCandidateRepository(database_path)
    flashcard_repository.add_candidate(book_id, 1, 5, _FLASHCARD)

    DuplicateCandidateRepository(database_path).remove_book(book_id)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM FlashcardCandidates").fetchone()[0]
    assert count == 0
