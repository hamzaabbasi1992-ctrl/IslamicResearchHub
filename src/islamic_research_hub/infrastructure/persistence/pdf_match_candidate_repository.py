"""SQLite adapter for fuzzy-matching heading-only books to real PDF archive files.

Some source libraries (Maktaba Jibreel Desktop, Al-Maknoon, Maktaba Islam)
contain books whose page content is only a heading - a few words per page,
not the real body text (confirmed by decrypting the original Jibreel source
directly: the raw ContentF/ContentP fields themselves are that sparse, so
this is a source-data limitation, not an import bug). Separate PDF Archive
libraries often hold the real scanned book for the same title, but under a
raw, uncleaned filename (e.g. "12 Masail By SHEIKH MUNEER AHMAD MUNAWWAR"),
so exact-title matching (see `DuplicateCandidateRepository`) mostly misses
them.

This does fuzzy, blocked title matching instead: it only compares a stub
book against PDF titles that share at least one uncommon normalized word
with it (an inverted-index "blocking" step - full O(n*m) SequenceMatcher
comparison across ~2,400 stub books x ~9,000 PDF titles is not practical),
then keeps the single best match per stub book, and only if it clears a
high similarity threshold. Detection is intentionally conservative and
informational only: nothing here deletes or replaces content, and every
match should be treated as a *possible* PDF, not a verified one.
"""

import logging
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from difflib import SequenceMatcher
from pathlib import Path

from islamic_research_hub.application.pdf_source_resolver import PDF_SOURCE_LIBRARIES
from islamic_research_hub.domain.models.pdf_match_candidate import PdfMatchCandidate
from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text

LOGGER = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.90
MIN_WORD_LENGTH = 3
MAX_BLOCKING_DOC_FREQUENCY = 50
STUB_MIN_PAGE_COUNT = 20
STUB_MAX_AVG_CONTENT_LENGTH = 60

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
# Multi-volume series (e.g. "Fatawa Mahmoodiah Vol 07" vs "... Vol 25") share
# almost all of their text and score very high on plain string similarity -
# real production data showed this producing confident, wrong-volume
# matches. Both "vol"/"jild" (English transliteration) and "جلد" (the
# Arabic/Urdu word itself) appear in the corpus. A trailing sub-part letter
# ("Vol 22 A" vs "Vol 22 B") is the same failure mode one level down - also
# seen in production, also rejected.
_VOLUME_PATTERN = re.compile(r"(?:vol|jild|جلد)\.?\s*0*(\d+)\s*([a-z])?\b")


class PdfMatchCandidateRepository:
    """Find and store possible PDF matches for heading-only books, by fuzzy title."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def detect_and_store(self) -> int:
        """Fuzzy-match stub-content books against PDF archive titles, returning the count stored."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.row_factory = sqlite3.Row
            pdf_books = self._fetch_pdf_books(connection)
            stub_books = self._fetch_stub_books(connection)

            candidates = _match(stub_books, pdf_books)

            connection.execute("DELETE FROM PdfMatchCandidates")
            connection.executemany(
                "INSERT INTO PdfMatchCandidates (BookID, PdfBookID, Confidence) "
                "VALUES (?, ?, ?)",
                candidates,
            )
            connection.commit()

        LOGGER.info("PDF match candidate detection complete: %d match(es) found.", len(candidates))
        return len(candidates)

    def list_candidates(self) -> tuple[PdfMatchCandidate, ...]:
        """Return every stored PDF match candidate."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            rows = connection.execute(
                "SELECT BookID, PdfBookID, Confidence FROM PdfMatchCandidates"
            ).fetchall()
        return tuple(
            PdfMatchCandidate(book_id=row[0], pdf_book_id=row[1], confidence=row[2])
            for row in rows
        )

    def get_match(self, book_id: int) -> PdfMatchCandidate | None:
        """Return the stored PDF match for one book, if any."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            row = connection.execute(
                "SELECT BookID, PdfBookID, Confidence FROM PdfMatchCandidates WHERE BookID = ?",
                (book_id,),
            ).fetchone()
        if row is None:
            return None
        return PdfMatchCandidate(book_id=row[0], pdf_book_id=row[1], confidence=row[2])

    def is_stub(self, book_id: int) -> bool:
        """Return whether one book matches the same stub definition used for PDF matching.

        Reuses the same thresholds as `_fetch_stub_books()` so the two
        can't drift apart - this is the check callers use to decide
        whether a *directly* resolvable PDF (the book's own Source, not
        a fuzzy match) is still worth offering as a fallback.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            row = connection.execute(
                "SELECT COUNT(*), AVG(LENGTH(Content)) FROM Pages WHERE BookID = ?",
                (book_id,),
            ).fetchone()
        page_count, avg_length = row if row is not None else (0, None)
        return (
            page_count > STUB_MIN_PAGE_COUNT
            and avg_length is not None
            and avg_length < STUB_MAX_AVG_CONTENT_LENGTH
        )

    @staticmethod
    def _fetch_pdf_books(connection: sqlite3.Connection) -> tuple[sqlite3.Row, ...]:
        """Return every book from a PDF Archive library that has a title."""
        placeholders = ",".join("?" for _ in PDF_SOURCE_LIBRARIES)
        return tuple(
            connection.execute(
                f"""
                SELECT b.BookID, b.Title FROM Books b
                JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE l.Name IN ({placeholders}) AND b.Title IS NOT NULL
                """,
                tuple(PDF_SOURCE_LIBRARIES),
            ).fetchall()
        )

    @staticmethod
    def _fetch_stub_books(connection: sqlite3.Connection) -> tuple[sqlite3.Row, ...]:
        """Return every non-PDF-library book whose pages average near-empty content."""
        placeholders = ",".join("?" for _ in PDF_SOURCE_LIBRARIES)
        return tuple(
            connection.execute(
                f"""
                SELECT b.BookID, b.Title FROM Books b
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
        )

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        """Create the PDF match candidates table when it does not yet exist."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS PdfMatchCandidates (
                BookID INTEGER PRIMARY KEY REFERENCES Books(BookID),
                PdfBookID INTEGER NOT NULL REFERENCES Books(BookID),
                Confidence REAL NOT NULL
            );
            """
        )
        connection.commit()


def _normalize_title(title: str) -> str:
    """Return a lowercased, diacritic-stripped title for fuzzy comparison."""
    return (normalize_search_text(title) or "").casefold()


def _tokens(normalized_title: str) -> set[str]:
    """Return the normalized title's words, excluding very short ones."""
    return {word for word in _TOKEN_PATTERN.findall(normalized_title) if len(word) >= MIN_WORD_LENGTH}


def _volume_key(normalized_title: str) -> tuple[int, str | None] | None:
    """Return the (number, sub-part letter) a title's volume names, if any."""
    match = _VOLUME_PATTERN.search(normalized_title)
    return (int(match.group(1)), match.group(2)) if match else None


def _volumes_conflict(
    stub_volume: tuple[int, str | None] | None, pdf_volume: tuple[int, str | None] | None
) -> bool:
    """Return True only when both titles name a volume and it's unambiguously different."""
    if stub_volume is None or pdf_volume is None:
        return False
    stub_number, stub_letter = stub_volume
    pdf_number, pdf_letter = pdf_volume
    if stub_number != pdf_number:
        return True
    return stub_letter is not None and pdf_letter is not None and stub_letter != pdf_letter


def _match(
    stub_books: tuple[sqlite3.Row, ...], pdf_books: tuple[sqlite3.Row, ...]
) -> list[tuple[int, int, float]]:
    """Return (BookID, PdfBookID, Confidence) triples for high-confidence fuzzy title matches."""
    pdf_normalized: dict[int, str] = {}
    token_index: dict[str, list[int]] = defaultdict(list)
    for row in pdf_books:
        normalized = _normalize_title(row["Title"])
        pdf_normalized[row["BookID"]] = normalized
        for token in _tokens(normalized):
            token_index[token].append(row["BookID"])

    blocking_tokens = {
        token: ids for token, ids in token_index.items() if len(ids) <= MAX_BLOCKING_DOC_FREQUENCY
    }

    candidates: list[tuple[int, int, float]] = []
    for row in stub_books:
        normalized = _normalize_title(row["Title"])
        stub_volume = _volume_key(normalized)
        candidate_pdf_ids: set[int] = set()
        for token in _tokens(normalized):
            candidate_pdf_ids.update(blocking_tokens.get(token, ()))

        best_pdf_id: int | None = None
        best_ratio = 0.0
        for pdf_id in candidate_pdf_ids:
            pdf_title = pdf_normalized[pdf_id]
            if _volumes_conflict(stub_volume, _volume_key(pdf_title)):
                continue
            ratio = SequenceMatcher(None, normalized, pdf_title).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_pdf_id = pdf_id

        if best_pdf_id is not None and best_ratio >= MIN_CONFIDENCE:
            candidates.append((row["BookID"], best_pdf_id, best_ratio))

    return candidates
