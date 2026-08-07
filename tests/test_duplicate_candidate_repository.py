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


def _book(
    name: str, mjbn: str | None = None, with_content: bool = False, author: str | None = None
) -> Book:
    """Build a minimal book with the given title, optional source id/author/content."""
    information = {"Name": name}
    if mjbn is not None:
        information["MJBN"] = mjbn
    if author is not None:
        information["ANAME"] = author
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


def test_does_not_flag_same_title_within_one_library_with_no_author(tmp_path: Path) -> None:
    """A repeated title within one library, with no author recorded on either
    side, isn't flagged - title alone is too weak a signal within a single
    library (real Shamela data has many distinct books sharing a generic
    title with no author set)."""
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


def test_flags_same_title_and_author_within_one_library(tmp_path: Path) -> None:
    """Real gap found investigating the full Shamela import: within-library
    duplicates (same title AND author) were entirely invisible to the old
    cross-library-only scan. Now detected, with a distinct match_type."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Same Title", author="Author One"),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (_book("Same Title", author="Author One"),),
        (tmp_path / "b.mjbz",),
        library_name="Library A",
    )

    count = DuplicateCandidateRepository(database_path).detect_and_store()

    assert count == 1
    candidates = DuplicateCandidateRepository(database_path).list_candidates()
    assert candidates[0].match_type == "exact_title_and_author_same_library"


def test_does_not_flag_same_title_within_one_library_with_different_authors(
    tmp_path: Path,
) -> None:
    """A shared title within one library, but a different real author on
    each side, is not flagged - they're evidently different books."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Same Title", author="Author One"),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (_book("Same Title", author="Author Two"),),
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


def test_dismiss_marks_a_pair_dismissed_and_hides_it_by_default(tmp_path: Path) -> None:
    """dismiss() is a pure status change - list_candidates() hides it by
    default, but it's still there (and still tellable apart) on request."""
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
    candidate = duplicate_repository.list_candidates()[0]

    duplicate_repository.dismiss(candidate.book_id, candidate.duplicate_of_book_id)

    assert duplicate_repository.list_candidates() == ()
    remaining = duplicate_repository.list_candidates(include_dismissed=True)
    assert len(remaining) == 1
    assert remaining[0].status == "dismissed"


def test_dismissed_status_survives_a_detect_and_store_rerun(tmp_path: Path) -> None:
    """Real gap this fixes: detect_and_store() used to wipe and fully
    recompute DuplicateCandidates on every run, which would have silently
    un-dismissed a pair a human already reviewed on the very next rescan."""
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
    candidate = duplicate_repository.list_candidates()[0]
    duplicate_repository.dismiss(candidate.book_id, candidate.duplicate_of_book_id)

    duplicate_repository.detect_and_store()

    assert duplicate_repository.list_candidates() == ()
    remaining = duplicate_repository.list_candidates(include_dismissed=True)
    assert remaining[0].status == "dismissed"


def test_resolve_empty_stub_duplicates_ignores_dismissed_pairs(tmp_path: Path) -> None:
    """A dismissed pair (confirmed different books) is left alone even if
    one side has zero pages - dismissal means that side is a real, separate
    book with no content yet, not a stub duplicate."""
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
    candidate = duplicate_repository.list_candidates()[0]
    duplicate_repository.dismiss(candidate.book_id, candidate.duplicate_of_book_id)

    removed_count = duplicate_repository.resolve_empty_stub_duplicates()

    assert removed_count == 0
    with sqlite3.connect(database_path) as connection:
        book_count = connection.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
    assert book_count == 2


def test_export_book_returns_the_real_row_content(tmp_path: Path) -> None:
    """export_book() dumps the Books row plus every referencing table's
    rows, as plain dicts - the backup step before remove_book() deletes."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Shared Title", with_content=True),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    book_id = 1

    export = DuplicateCandidateRepository(database_path).export_book(book_id)

    assert len(export["Books"]) == 1
    assert export["Books"][0]["Title"] == "Shared Title"
    assert len(export["Pages"]) == 1
    assert export["Pages"][0]["Content"] == "Some real page content"
    assert "PageEmbeddings" not in export


def test_remove_book_deletes_the_book_and_its_pages(tmp_path: Path) -> None:
    """remove_book() permanently deletes a real book, not just a stub."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_book("Shared Title", with_content=True),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    book_id = 1

    DuplicateCandidateRepository(database_path).remove_book(book_id)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM Books").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM Pages").fetchone()[0] == 0


def test_remove_book_also_clears_any_duplicate_candidate_rows_referencing_it(
    tmp_path: Path,
) -> None:
    """A removed book shouldn't leave a dangling DuplicateCandidates row on
    either side of the pair."""
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
    candidate = duplicate_repository.list_candidates()[0]

    duplicate_repository.remove_book(candidate.book_id)

    assert duplicate_repository.list_candidates(include_dismissed=True) == ()


def test_remove_book_also_clears_any_citation_candidate_rows_referencing_it(
    tmp_path: Path,
) -> None:
    """A removed book shouldn't leave a dangling CitationCandidates row on
    either the citing or the cited side - that table has two book-reference
    columns, unlike DuplicateCandidates' single BookID, so it needs its own
    explicit check in _delete_book()."""
    from islamic_research_hub.infrastructure.persistence.citation_candidate_repository import (
        CitationCandidateRepository,
    )
    from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner

    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    title = "A Real Distinctive Citation Target Title"
    repository.import_books(
        database_path,
        (
            Book(information={"Name": title}, categories=(), table_of_contents=(), pages=(Page(1, 1, "front matter", None),)),
            Book(
                information={"Name": "A Citing Book"},
                categories=(),
                table_of_contents=(),
                pages=(Page(1, 1, f"as mentioned in {title} earlier", None),),
            ),
        ),
        (tmp_path / "a.mjbz", tmp_path / "b.mjbz"),
        library_name="Library A",
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    citation_repository = CitationCandidateRepository(database_path)
    assert citation_repository.detect_and_store() == 1

    DuplicateCandidateRepository(database_path).remove_book(1)  # the cited book

    assert citation_repository.list_candidates(include_dismissed=True) == ()


def test_remove_book_also_clears_flashcard_review_state_referencing_it(tmp_path: Path) -> None:
    """FlashcardReviewState has no BookID column of its own (it keys off
    FlashcardCandidateID) - a removed book's real spaced-repetition
    schedule shouldn't survive as orphaned dead data."""
    from islamic_research_hub.application.flashcard_extraction import ExtractedFlashcard
    from islamic_research_hub.infrastructure.persistence.flashcard_candidate_repository import (
        FlashcardCandidateRepository,
    )

    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path, (_book("Book of Fiqh"),), (tmp_path / "a.mjbz",), library_name="Library A"
    )
    flashcards = FlashcardCandidateRepository(database_path)
    candidate_id = flashcards.add_candidate(
        1,
        1,
        5,
        ExtractedFlashcard(front="Front", back="Back", quoted_excerpt="x", citation="y"),
    )
    flashcards.confirm(candidate_id)
    flashcards.record_review(candidate_id, "good")

    DuplicateCandidateRepository(database_path).remove_book(1)

    with sqlite3.connect(database_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM FlashcardReviewState").fetchone()[0]
    assert count == 0


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
