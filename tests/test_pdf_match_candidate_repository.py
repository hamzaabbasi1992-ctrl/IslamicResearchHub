"""Tests for fuzzy-matching heading-only books to PDF archive titles."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.pdf_match_candidate_repository import (
    PdfMatchCandidateRepository,
)

STUB_PAGE_COUNT = 25


def _set_source_pdf_hint(database_path: Path, book_id: int, hint: str) -> None:
    """Set Books.SourcePdfHint directly, as the real backfill CLI does."""
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)").fetchall()}
        if "SourcePdfHint" not in columns:
            connection.execute("ALTER TABLE Books ADD COLUMN SourcePdfHint TEXT")
        connection.execute(
            "UPDATE Books SET SourcePdfHint = ? WHERE BookID = ?", (hint, book_id)
        )


def _stub_book(name: str) -> Book:
    """Build a book with many pages of near-empty (heading-only) content."""
    pages = tuple(Page(i, i, "hd", None) for i in range(1, STUB_PAGE_COUNT + 1))
    return Book(information={"Name": name}, categories=(), table_of_contents=(), pages=pages)


def _full_book(name: str) -> Book:
    """Build a book with real, substantial page content."""
    pages = tuple(
        Page(i, i, "Real substantial page content " * 10, None)
        for i in range(1, STUB_PAGE_COUNT + 1)
    )
    return Book(information={"Name": name}, categories=(), table_of_contents=(), pages=pages)


def _pdf_book(name: str) -> Book:
    """Build a metadata-only PDF archive entry (no page content, as in production)."""
    return Book(information={"Name": name}, categories=(), table_of_contents=(), pages=())


def test_matches_a_stub_book_to_its_similarly_titled_pdf(tmp_path: Path) -> None:
    """A heading-only book fuzzy-matches a near-identical PDF archive title."""
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
        (_pdf_book("Ilm Ul Aasar Ke Dars O Muzakraat Fi Al Hadith Al Nabawi"),),
        (tmp_path / "unrelated_source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )
    # Fuzzy matching relies on shared Arabic-script words, so give the PDF
    # entry an Arabic-titled sibling too (a real archive has a mix).
    repository.import_books(
        database_path,
        (_pdf_book("علم الآثار کے درس و مذاکرات فی الحدیث"),),
        (tmp_path / "real_source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    match_repository = PdfMatchCandidateRepository(database_path)
    count = match_repository.detect_and_store()

    assert count == 1
    candidates = match_repository.list_candidates()
    assert len(candidates) == 1
    assert candidates[0].confidence >= 0.82


def test_does_not_match_unrelated_titles(tmp_path: Path) -> None:
    """A stub book with no similar PDF title gets no match."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("فتاوی قاضی خان"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("12 Masail By SHEIKH MUNEER AHMAD MUNAWWAR"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_does_not_match_books_with_real_substantial_content(tmp_path: Path) -> None:
    """A book with real page content is never treated as a stub, even with a matching title."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_full_book("کشف الباری اردو شرح صحیح البخاری"),),
        (tmp_path / "full.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("کشف الباری اردو شرح صحیح البخاری"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_ignores_pdf_archive_books_as_match_targets_for_each_other(tmp_path: Path) -> None:
    """A PDF Archive book itself is never treated as a stub needing a match."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("کتاب"),),
        (tmp_path / "stub.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("کتاب"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_does_not_match_a_different_volume_of_the_same_series(tmp_path: Path) -> None:
    """A wrong-volume PDF is rejected even when it scores high on plain string similarity.

    Real production data showed "Fatawa Mahmoodiah Vol 07" fuzzy-matching
    "Fatawa Mahmoodiah Vol 25" at 0.92 confidence - the titles are nearly
    identical text apart from the volume number, so a right-book-wrong-volume
    match is exactly the failure mode plain SequenceMatcher.ratio() misses.
    """
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("Fatawa Mahmoodiah Vol 07"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("Fatawa Mahmoodiah Vol 25"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_does_not_match_a_different_sub_part_of_the_same_volume(tmp_path: Path) -> None:
    """A wrong-sub-part PDF is rejected even when the volume number itself matches.

    Real production data showed "Jadeed Fiqhi Mabahis Vol 22 B" matching
    "... Vol 22 A" at 0.966 confidence - same volume number, different
    lettered part, so the plain volume-number check alone was not enough.
    """
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("Jadeed Fiqhi Mabahis Vol 22 B"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("Jadeed Fiqhi Mabahis Vol 22 A"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_matches_same_volume_of_a_series_despite_shared_boilerplate(tmp_path: Path) -> None:
    """A same-volume match within a series is still found, not blocked by the volume check."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("Fatawa Mahmoodiah Vol 07"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("Fatawa Mahmoodiah Vol 07"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 1


def test_detect_and_store_is_idempotent_on_rerun(tmp_path: Path) -> None:
    """Re-running detection recomputes rather than accumulating stale rows."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("علم الآثار کے درس و مذاکرات"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("علم الآثار کے درس و مذاکرات"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )

    match_repository = PdfMatchCandidateRepository(database_path)
    match_repository.detect_and_store()
    count = match_repository.detect_and_store()

    assert count == 1
    assert len(match_repository.list_candidates()) == 1


def test_get_match_returns_none_when_no_match_stored(tmp_path: Path) -> None:
    """Looking up a book with no stored match returns None, not an error."""
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_stub_book("کتاب"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )

    match_repository = PdfMatchCandidateRepository(database_path)
    match_repository.detect_and_store()

    assert match_repository.get_match(book_id=999) is None


def test_is_stub_true_for_heading_only_book(tmp_path: Path) -> None:
    """A book whose pages average near-empty content is reported as a stub."""
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_stub_book("کتاب"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )

    assert PdfMatchCandidateRepository(database_path).is_stub(book_id=1) is True


def test_is_stub_false_for_a_book_with_real_content(tmp_path: Path) -> None:
    """A book with real, substantial page content is never reported as a stub."""
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_full_book("کتاب"),),
        (tmp_path / "full.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )

    assert PdfMatchCandidateRepository(database_path).is_stub(book_id=1) is False


def test_is_stub_false_for_an_unknown_book(tmp_path: Path) -> None:
    """A book id with no pages at all is never reported as a stub."""
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (_stub_book("کتاب"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )

    assert PdfMatchCandidateRepository(database_path).is_stub(book_id=999) is False


def test_matches_via_source_pdf_hint_across_scripts_where_title_matching_cannot(
    tmp_path: Path,
) -> None:
    """A native-script title has zero shared words with a romanized PDF filename,
    so only the SourcePdfHint (also romanized) can bridge them - real production
    evidence: a random sample of 30 unmatched stub books found real PDFs for 24
    via the hint (17 of them an exact match after normalization, like this one -
    plain SequenceMatcher.ratio() is deliberately not relaxed for near-misses
    with extra trailing text, e.g. an appended author name: manually verified
    that doing so would also let real false positives from the title-matching
    path back in at similar scores, with no clean threshold separating them)."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("کشف الباری کتاب الایمان"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("Kashf Ul Bari Kitab Ul Eeman"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )
    _set_source_pdf_hint(database_path, book_id=1, hint="KASHF_UL_BARI_KITAB_UL_EEMAN.pdf")

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 1
    candidates = PdfMatchCandidateRepository(database_path).list_candidates()
    assert candidates[0].pdf_book_id == 2
    assert candidates[0].confidence == 1.0


def test_hint_match_still_rejects_a_different_volume(tmp_path: Path) -> None:
    """The volume-conflict guard applies to hint-based matching too."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("کشف الباری کتاب الایمان جلد 1"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("Kashf Ul Bari Kitab Ul Eeman Vol 02"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )
    _set_source_pdf_hint(database_path, book_id=1, hint="KASHF_UL_BARI_KITAB_UL_EEMAN_VOL_01.pdf")

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 0


def test_falls_back_to_title_when_hint_finds_no_match(tmp_path: Path) -> None:
    """A hint present but matching nothing still lets the title-based match through."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("کشف الباری اردو شرح صحیح البخاری"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository.import_books(
        database_path,
        (_pdf_book("کشف الباری اردو شرح صحیح البخاری"),),
        (tmp_path / "source.pdf",),
        library_name="Maktaba Jibreel (PDF Archive)",
    )
    _set_source_pdf_hint(database_path, book_id=1, hint="SOME_UNRELATED_FILENAME.pdf")

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 1
    candidates = PdfMatchCandidateRepository(database_path).list_candidates()
    assert candidates[0].pdf_book_id == 2


def test_missing_source_pdf_hint_column_does_not_break_detection(tmp_path: Path) -> None:
    """A database that predates migration 11 (no SourcePdfHint column) still works."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (_stub_book("کتاب"),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)").fetchall()}
    assert "SourcePdfHint" not in columns

    count = PdfMatchCandidateRepository(database_path).detect_and_store()

    assert count == 0
