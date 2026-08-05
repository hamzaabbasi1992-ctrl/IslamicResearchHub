"""Tests for the Digital Preservation Report's real data-gathering queries."""

from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.pdf_match_candidate_repository import (
    PdfMatchCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.preservation_report_repository import (
    REASON_NO_TEXT_NO_PDF,
    REASON_SPARSE_TEXT_NO_PDF_MATCH,
    PreservationReportRepository,
)

STUB_PAGE_COUNT = 25


def _stub_book(name: str) -> Book:
    pages = tuple(Page(i, i, "hd", None) for i in range(1, STUB_PAGE_COUNT + 1))
    return Book(information={"Name": name}, categories=(), table_of_contents=(), pages=pages)


def _full_book(name: str) -> Book:
    pages = tuple(
        Page(i, i, "Real substantial page content " * 10, None)
        for i in range(1, STUB_PAGE_COUNT + 1)
    )
    return Book(information={"Name": name}, categories=(), table_of_contents=(), pages=pages)


def _empty_book(name: str) -> Book:
    return Book(information={"Name": name}, categories=(), table_of_contents=(), pages=())


def test_zero_page_book_in_a_pdf_archive_library_is_not_flagged(tmp_path: Path) -> None:
    """A PDF Archive library having zero pages is the expected format, not an anomaly."""
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_empty_book("A Real PDF-Only Book"),),
        (tmp_path / "a.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    incomplete = PreservationReportRepository(database_path).list_incomplete_books()

    assert incomplete == ()


def test_zero_page_book_outside_a_pdf_archive_library_is_flagged(tmp_path: Path) -> None:
    """A zero-page book from a text-source library is a real anomaly worth flagging."""
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_empty_book("A Real Broken Import"),),
        (tmp_path / "a.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )

    incomplete = PreservationReportRepository(database_path).list_incomplete_books()

    assert len(incomplete) == 1
    assert incomplete[0].title == "A Real Broken Import"
    assert incomplete[0].reason == REASON_NO_TEXT_NO_PDF


def test_sparse_heading_only_book_with_no_pdf_match_is_flagged(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_stub_book("فتاوی قاضی خان"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    PdfMatchCandidateRepository(database_path).detect_and_store()  # real, finds nothing

    incomplete = PreservationReportRepository(database_path).list_incomplete_books()

    assert len(incomplete) == 1
    assert incomplete[0].reason == REASON_SPARSE_TEXT_NO_PDF_MATCH


def test_sparse_book_with_a_real_pdf_match_is_not_flagged(tmp_path: Path) -> None:
    """A stub book with a real, already-found PDF fallback isn't a preservation gap."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("علم الآثار کے درس و مذاکرات فی الحدیث النبوی"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (Book(
            information={"Name": "Ilm Ul Aasar Ke Dars O Muzakraat Fi Al Hadith Al Nabawi"},
            categories=(), table_of_contents=(), pages=(),
        ),),
        (tmp_path / "unrelated_source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )
    repository.import_books(
        database_path,
        (Book(
            information={"Name": "علم الآثار کے درس و مذاکرات فی الحدیث"},
            categories=(), table_of_contents=(), pages=(),
        ),),
        (tmp_path / "real_source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )
    PdfMatchCandidateRepository(database_path).detect_and_store()

    incomplete = PreservationReportRepository(database_path).list_incomplete_books()

    assert incomplete == ()


def test_book_with_real_substantial_content_is_not_flagged(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_full_book("A Real, Complete Book"),),
        (tmp_path / "a.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )

    incomplete = PreservationReportRepository(database_path).list_incomplete_books()

    assert incomplete == ()


def test_count_pending_duplicates_reflects_real_candidates(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_full_book("Book of Fiqh"),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (_full_book("Book of Fiqh"),),
        (tmp_path / "b.mjbz",),
        library_name="Library B",
    )
    DuplicateCandidateRepository(database_path).detect_and_store()

    count = PreservationReportRepository(database_path).count_pending_duplicates()

    assert count == 1
