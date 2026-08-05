"""Tests for detecting and storing real citation candidates between owned books."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.citation_candidate_repository import (
    CitationCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner

_DISTINCTIVE_TITLE = "A Real Distinctive Citation Target Title"


def _book(name: str, pages: tuple[Page, ...] = ()) -> Book:
    return Book(information={"Name": name}, categories=(), table_of_contents=(), pages=pages)


def _page(page_number: int, content: str) -> Page:
    return Page(page_number, page_number, content, None)


def _migrate(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)


def _set_series(database_path: Path, book_id: int, series_id: int) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO Series (SeriesID, Title) VALUES (?, ?)",
            (series_id, f"Series {series_id}"),
        )
        connection.execute("UPDATE Books SET SeriesID = ? WHERE BookID = ?", (series_id, book_id))
        connection.commit()


def _insert_paragraph(
    database_path: Path, book_id: int, page_no: int, paragraph_index: int, content: str
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Paragraphs (BookID, PageNo, ParagraphIndex, IsHeading, Content) "
            "VALUES (?, ?, ?, 0, ?)",
            (book_id, page_no, paragraph_index, content),
        )
        connection.commit()


def _seed(database_path: Path, books: tuple[Book, ...]) -> None:
    MasterBookRepository().import_books(
        database_path, books, tuple(database_path.parent / f"src{i}.mjbz" for i in range(len(books)))
    )
    _migrate(database_path)


def test_detects_a_real_literal_phrase_citation(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),
            _book(
                "A Completely Unrelated Citing Book",
                pages=(_page(1, f"as mentioned in {_DISTINCTIVE_TITLE} earlier"),),
            ),
        ),
    )

    count = CitationCandidateRepository(database_path).detect_and_store()

    assert count == 1
    candidates = CitationCandidateRepository(database_path).list_candidates()
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.cited_book_id == 1
    assert candidate.citing_book_id == 2
    assert candidate.citing_page_no == 1
    assert candidate.match_type == "unique_title"
    assert candidate.matched_title_text == _DISTINCTIVE_TITLE


def test_does_not_flag_a_book_citing_itself(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(
                _DISTINCTIVE_TITLE,
                pages=(_page(1, f"the introduction to {_DISTINCTIVE_TITLE}"),),
            ),
        ),
    )

    count = CitationCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_does_not_flag_a_same_series_cross_volume_mention(tmp_path: Path) -> None:
    """Real corpus fact: volumes of the same series often share an
    identical Title (VolumeNumber stored separately) - one volume's text
    naturally mentions the series title, which isn't a real citation of
    a *different* book."""
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "volume one content"),)),
            _book(
                _DISTINCTIVE_TITLE,
                pages=(_page(1, f"continuing {_DISTINCTIVE_TITLE} from volume one"),),
            ),
        ),
    )
    _set_series(database_path, 1, 100)
    _set_series(database_path, 2, 100)

    count = CitationCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_title_shorter_than_minimum_length_is_not_used_as_an_anchor(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book("Al", pages=(_page(1, "short"),)),
            _book("Another Book", pages=(_page(1, "mentions Al in passing"),)),
        ),
    )

    count = CitationCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_ambiguous_title_produces_one_candidate_per_cited_book(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "first copy"),)),
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "second unrelated copy"),)),
            _book(
                "A Third Citing Book",
                pages=(_page(1, f"refers to {_DISTINCTIVE_TITLE} here"),),
            ),
        ),
    )

    count = CitationCandidateRepository(database_path).detect_and_store()

    assert count == 2
    candidates = CitationCandidateRepository(database_path).list_candidates()
    assert {candidate.cited_book_id for candidate in candidates} == {1, 2}
    assert all(candidate.match_type == "ambiguous_title" for candidate in candidates)
    assert all(candidate.citing_book_id == 3 for candidate in candidates)


def test_anchor_exceeding_max_hits_stores_nothing(tmp_path: Path) -> None:
    from islamic_research_hub.application import citation_detection

    citing_pages = tuple(
        _page(page_no, f"mentions {_DISTINCTIVE_TITLE} here")
        for page_no in range(1, citation_detection.MAX_HITS_PER_ANCHOR + 2)
    )
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),
            _book("A Very Heavily Citing Book", pages=citing_pages),
        ),
    )

    count = CitationCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_resolves_citing_paragraph_when_paragraphs_are_backfilled(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),
            _book(
                "A Citing Book",
                pages=(_page(1, f"as mentioned in {_DISTINCTIVE_TITLE} earlier"),),
            ),
        ),
    )
    _insert_paragraph(database_path, 2, 1, 1, "unrelated first paragraph")
    _insert_paragraph(database_path, 2, 1, 2, f"as mentioned in {_DISTINCTIVE_TITLE} earlier")

    CitationCandidateRepository(database_path).detect_and_store()

    candidates = CitationCandidateRepository(database_path).list_candidates()
    assert len(candidates) == 1
    assert candidates[0].citing_paragraph_id is not None


def test_leaves_paragraph_id_null_when_paragraphs_were_never_backfilled(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),
            _book(
                "A Citing Book",
                pages=(_page(1, f"as mentioned in {_DISTINCTIVE_TITLE} earlier"),),
            ),
        ),
    )

    CitationCandidateRepository(database_path).detect_and_store()

    candidates = CitationCandidateRepository(database_path).list_candidates()
    assert len(candidates) == 1
    assert candidates[0].citing_paragraph_id is None
    assert candidates[0].citing_page_no == 1


def test_dismiss_hides_by_default_and_is_visible_with_include_dismissed(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),
            _book(
                "A Citing Book",
                pages=(_page(1, f"as mentioned in {_DISTINCTIVE_TITLE} earlier"),),
            ),
        ),
    )
    repository = CitationCandidateRepository(database_path)
    repository.detect_and_store()

    repository.dismiss(citing_book_id=2, citing_page_no=1, cited_book_id=1)

    assert repository.list_candidates() == ()
    assert len(repository.list_candidates(include_dismissed=True)) == 1


def test_dismissed_status_survives_a_rerun(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),
            _book(
                "A Citing Book",
                pages=(_page(1, f"as mentioned in {_DISTINCTIVE_TITLE} earlier"),),
            ),
        ),
    )
    repository = CitationCandidateRepository(database_path)
    repository.detect_and_store()
    repository.dismiss(citing_book_id=2, citing_page_no=1, cited_book_id=1)

    repository.detect_and_store()

    assert repository.list_candidates() == ()


def test_dismiss_pair_dismisses_every_row_for_one_book_pair(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),
            _book(
                "A Heavily Citing Book",
                pages=(
                    _page(1, f"first mention of {_DISTINCTIVE_TITLE}"),
                    _page(2, f"second mention of {_DISTINCTIVE_TITLE}"),
                ),
            ),
        ),
    )
    repository = CitationCandidateRepository(database_path)
    repository.detect_and_store()
    assert len(repository.list_candidates()) == 2

    dismissed_count = repository.dismiss_pair(citing_book_id=2, cited_book_id=1)

    assert dismissed_count == 2
    assert repository.list_candidates() == ()


def test_detect_and_store_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed(
        database_path,
        (
            _book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),
            _book(
                "A Citing Book",
                pages=(_page(1, f"as mentioned in {_DISTINCTIVE_TITLE} earlier"),),
            ),
        ),
    )
    repository = CitationCandidateRepository(database_path)

    first_count = repository.detect_and_store()
    second_count = repository.detect_and_store()

    assert first_count == second_count == 1


def test_returns_zero_without_crashing_when_unmigrated(tmp_path: Path) -> None:
    """An unmigrated database (no PagesFTSNormalized) degrades gracefully."""
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_book(_DISTINCTIVE_TITLE, pages=(_page(1, "front matter"),)),),
        (database_path.parent / "source.mjbz",),
    )

    count = CitationCandidateRepository(database_path).detect_and_store()

    assert count == 0
