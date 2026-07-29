"""Read-only SQLite adapter for real, page-level comparison between two candidate-duplicate books.

A title match alone (`DuplicateCandidateRepository`) only says two books
are *probably* the same work - it never shows what actually differs
between editions/printings. This is the real comparison: for every page
number present in both books, how similar is the real text, and where
does it genuinely differ. Purely read-only - never modifies `Books` or
`Pages`.
"""

import difflib
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book_comparison import (
    BookComparisonResult,
    PageComparisonEntry,
)

MAX_DIFFERING_PAGES = 50
"""Cap on how many differing pages are returned, so two genuinely
different books mistakenly paired as candidates don't produce an
unusably huge result."""

SIMILARITY_THRESHOLD = 0.98
"""A common page below this similarity ratio counts as "differing" -
just under 1.0 so trivial whitespace/OCR noise doesn't flood results."""


class BookComparisonRepository:
    """Compare two real books' page content, page number by page number."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def compare(self, book_id_a: int, book_id_b: int) -> BookComparisonResult:
        """Return a real page-level comparison between two books."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            title_a = self._get_title(connection, book_id_a)
            title_b = self._get_title(connection, book_id_b)
            pages_a = self._get_pages(connection, book_id_a)
            pages_b = self._get_pages(connection, book_id_b)

        common_page_numbers = sorted(set(pages_a) & set(pages_b))

        differing_pages: list[PageComparisonEntry] = []
        similarities: list[float] = []
        for page_number in common_page_numbers:
            content_a = pages_a[page_number]
            content_b = pages_b[page_number]
            similarity = difflib.SequenceMatcher(None, content_a, content_b).ratio()
            similarities.append(similarity)
            if similarity < SIMILARITY_THRESHOLD:
                differing_pages.append(
                    PageComparisonEntry(
                        page_number=page_number,
                        similarity=similarity,
                        content_a=content_a,
                        content_b=content_b,
                    )
                )

        overall_similarity = (
            sum(similarities) / len(similarities) if similarities else None
        )

        return BookComparisonResult(
            book_id_a=book_id_a,
            book_id_b=book_id_b,
            title_a=title_a,
            title_b=title_b,
            page_count_a=len(pages_a),
            page_count_b=len(pages_b),
            common_page_count=len(common_page_numbers),
            overall_similarity=overall_similarity,
            differing_pages=tuple(differing_pages[:MAX_DIFFERING_PAGES]),
        )

    @staticmethod
    def _get_title(connection: sqlite3.Connection, book_id: int) -> str | None:
        row = connection.execute(
            "SELECT Title FROM Books WHERE BookID = ?", (book_id,)
        ).fetchone()
        return row["Title"] if row else None

    @staticmethod
    def _get_pages(connection: sqlite3.Connection, book_id: int) -> dict[int, str]:
        rows = connection.execute(
            "SELECT PageNo, Content FROM Pages WHERE BookID = ? AND PageNo IS NOT NULL",
            (book_id,),
        ).fetchall()
        return {row["PageNo"]: row["Content"] or "" for row in rows}
