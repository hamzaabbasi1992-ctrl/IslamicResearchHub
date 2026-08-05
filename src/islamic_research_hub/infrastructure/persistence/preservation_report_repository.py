"""Digital Preservation Report data: real corpus completeness/duplication
gaps, surfaced from already-built detection infrastructure
(`DuplicateCandidateRepository`, `PdfMatchCandidateRepository`) - not new
detection logic from scratch.

Corrupted/damaged source-file tracking is deliberately out of scope for
this milestone: an import-time failure today is only ever a transient
log line (`maknoon_import_cli.py`/`shamela_import_cli.py` both log and
move on), with nothing persisted post-import to query - adding that
would mean new schema across every importer, a real, separate, bigger
undertaking, not a report over existing data.
"""

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

from islamic_research_hub.application.pdf_source_resolver import PDF_SOURCE_LIBRARIES
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.pdf_match_candidate_repository import (
    STUB_MAX_AVG_CONTENT_LENGTH,
    STUB_MIN_PAGE_COUNT,
    PdfMatchCandidateRepository,
)

REASON_NO_TEXT_NO_PDF = "no_text_no_pdf"
REASON_SPARSE_TEXT_NO_PDF_MATCH = "sparse_text_no_pdf_match"


@dataclass(frozen=True, slots=True)
class IncompleteBook:
    """One real book with no substantive readable content in the app
    today: no real page text (and not from a library where that's
    expected, like a PDF Archive), or heading-only/sparse text - and no
    PDF fallback either found (own Source) or fuzzy-matched."""

    book_id: int
    title: str
    author: str | None
    library: str | None
    reason: str


class PreservationReportRepository:
    """Real corpus completeness/duplication gaps, composed from already-
    built detection rather than new detection logic."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._duplicates = DuplicateCandidateRepository(database_path)
        self._pdf_matches = PdfMatchCandidateRepository(database_path)

    def count_pending_duplicates(self) -> int:
        """Real pending duplicate-candidate count - a summary stat only;
        full review already lives in the Duplicate Manager screen."""
        return len(self._duplicates.list_candidates())

    def list_incomplete_books(self) -> tuple[IncompleteBook, ...]:
        """Real books genuinely unreadable in the app today.

        Two real cases, both excluding anything with a resolvable PDF
        fallback (own Source or a fuzzy match already found):
        - zero real page text, from a library where that's *not*
          expected (a `PDF_SOURCE_LIBRARIES` library having zero pages
          is normal - that's the format, not flagged);
        - heading-only/sparse text (same thresholds
          `PdfMatchCandidateRepository` already uses for stub detection,
          reused here rather than redefined) with no PDF match found.
        """
        matched_book_ids = {candidate.book_id for candidate in self._pdf_matches.list_candidates()}
        placeholders = ",".join("?" for _ in PDF_SOURCE_LIBRARIES)
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            # LEFT JOIN + "p.BookID IS NULL", not "BookID NOT IN (SELECT ...)" -
            # a real, measured difference at this corpus's scale (millions of
            # Pages rows): NOT IN against a large subquery is a known SQLite
            # slow path, confirmed directly against production (initial NOT
            # IN version did not complete in a reasonable time).
            zero_page_rows = connection.execute(
                f"""
                SELECT b.BookID, b.Title, b.Author, l.Name AS Library
                FROM Books b
                JOIN Libraries l ON l.LibraryID = b.LibraryID
                LEFT JOIN Pages p ON p.BookID = b.BookID
                WHERE l.Name NOT IN ({placeholders})
                AND b.Title IS NOT NULL
                AND p.BookID IS NULL
                """,
                tuple(PDF_SOURCE_LIBRARIES),
            ).fetchall()

            sparse_rows = connection.execute(
                f"""
                SELECT b.BookID, b.Title, b.Author, l.Name AS Library
                FROM Books b
                JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE l.Name NOT IN ({placeholders})
                AND b.Title IS NOT NULL
                AND b.PageCount > ?
                AND b.BookID IN (
                    SELECT BookID FROM Pages
                    GROUP BY BookID
                    HAVING AVG(LENGTH(Content)) < ?
                )
                """,
                (*PDF_SOURCE_LIBRARIES, STUB_MIN_PAGE_COUNT, STUB_MAX_AVG_CONTENT_LENGTH),
            ).fetchall()

        incomplete = [
            IncompleteBook(row["BookID"], row["Title"], row["Author"], row["Library"], REASON_NO_TEXT_NO_PDF)
            for row in zero_page_rows
            if row["BookID"] not in matched_book_ids
        ]
        incomplete.extend(
            IncompleteBook(
                row["BookID"], row["Title"], row["Author"], row["Library"], REASON_SPARSE_TEXT_NO_PDF_MATCH
            )
            for row in sparse_rows
            if row["BookID"] not in matched_book_ids
        )
        return tuple(sorted(incomplete, key=lambda book: (book.library or "", book.title or "")))
