"""Tests for tagging extracted event candidates with taxonomy terms."""

from pathlib import Path

import sqlite3

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import (
    EventCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.event_candidate_taxonomy_repository import (
    EventCandidateTaxonomyRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository

_EVENT = ExtractedEvent(
    title="A real waqia",
    alternate_names=(),
    subject="sabr",
    date_hijri=None,
    date_gregorian=None,
    location=None,
    background="Background text.",
    summary="Summary text.",
    key_figures=("Hazrat Umar",),
    quoted_excerpt="A real verbatim excerpt.",
    citation="Book X, Page 5",
)


def _migrated_database_with_candidate(tmp_path: Path) -> tuple[Path, int]:
    """A real, fully-migrated database with one book and one event candidate."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Khutbat"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real page content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    candidate_id = EventCandidateRepository(database_path).add_candidate(1, 1, 5, _EVENT)
    return database_path, candidate_id


def test_tag_candidate_then_get_term_ids_round_trips(tmp_path: Path) -> None:
    database_path, candidate_id = _migrated_database_with_candidate(tmp_path)
    taxonomy = TaxonomyRepository(database_path)
    sabr_id = taxonomy.get_or_create_term("subject", "صبر", "ur")
    umar_id = taxonomy.get_or_create_term("personality", "حضرت عمر فاروق رضی اللہ عنہ", "ur")
    repo = EventCandidateTaxonomyRepository(database_path)

    repo.tag_candidate(candidate_id, [sabr_id, umar_id])

    assert set(repo.get_term_ids(candidate_id)) == {sabr_id, umar_id}


def test_tag_candidate_is_idempotent(tmp_path: Path) -> None:
    """Tagging with the same term twice does not create duplicate rows or error."""
    database_path, candidate_id = _migrated_database_with_candidate(tmp_path)
    sabr_id = TaxonomyRepository(database_path).get_or_create_term("subject", "صبر", "ur")
    repo = EventCandidateTaxonomyRepository(database_path)

    repo.tag_candidate(candidate_id, [sabr_id])
    repo.tag_candidate(candidate_id, [sabr_id])

    assert repo.get_term_ids(candidate_id) == (sabr_id,)


def test_untag_candidate_removes_only_the_given_terms(tmp_path: Path) -> None:
    database_path, candidate_id = _migrated_database_with_candidate(tmp_path)
    taxonomy = TaxonomyRepository(database_path)
    sabr_id = taxonomy.get_or_create_term("subject", "صبر", "ur")
    shukr_id = taxonomy.get_or_create_term("subject", "شکر", "ur")
    repo = EventCandidateTaxonomyRepository(database_path)
    repo.tag_candidate(candidate_id, [sabr_id, shukr_id])

    repo.untag_candidate(candidate_id, [sabr_id])

    assert repo.get_term_ids(candidate_id) == (shukr_id,)


def test_find_candidates_sharing_terms_finds_a_real_overlap(tmp_path: Path) -> None:
    database_path, first_id = _migrated_database_with_candidate(tmp_path)
    second_id = EventCandidateRepository(database_path).add_candidate(1, 6, 10, _EVENT)
    sabr_id = TaxonomyRepository(database_path).get_or_create_term("subject", "صبر", "ur")
    repo = EventCandidateTaxonomyRepository(database_path)
    repo.tag_candidate(first_id, [sabr_id])
    repo.tag_candidate(second_id, [sabr_id])

    matches = repo.find_candidates_sharing_terms([sabr_id], exclude_candidate_id=first_id)

    assert matches == (second_id,)


def test_find_candidates_sharing_terms_returns_empty_for_no_terms(tmp_path: Path) -> None:
    database_path, _candidate_id = _migrated_database_with_candidate(tmp_path)
    repo = EventCandidateTaxonomyRepository(database_path)

    assert repo.find_candidates_sharing_terms([]) == ()
