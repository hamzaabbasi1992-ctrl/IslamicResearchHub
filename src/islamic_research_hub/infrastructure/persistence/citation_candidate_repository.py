"""SQLite adapter for detecting and persisting real citation candidates
between owned books - one book's text literally naming another book's
title, when both are already in this corpus.

Detection is exact-literal-phrase-based only, real page content against
real book titles: nothing here asserts a citation is real, it only
records a candidate for human review, the same discipline
`DuplicateCandidateRepository` already follows.
"""

import logging
import random
import sqlite3
import time
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

from islamic_research_hub.application.citation_detection import (
    MAX_HITS_PER_ANCHOR,
    TitleAnchor,
    build_title_anchors,
    escape_fts_phrase,
    resolve_citing_paragraph,
)
from islamic_research_hub.domain.models.citation_candidate import CitationCandidate

LOGGER = logging.getLogger(__name__)

_CitationRow = tuple[int, int, int | None, int, str, str]
"""(citing_book_id, citing_page_no, citing_paragraph_id, cited_book_id, matched_title_text, match_type)."""


class SampleTimingResult(NamedTuple):
    """Real, measured timing for a random sample of anchors - lets a CLI
    estimate full-run cost on the target machine before committing to it."""

    sampled: int
    total_anchors: int
    elapsed_seconds: float
    estimated_total_seconds: float


class CitationCandidateRepository:
    """Detect and store real, literal-phrase citation links between owned books."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def detect_and_store(
        self, progress_callback: Callable[[int, int], None] | None = None
    ) -> int:
        """Run the full detection pass, returning the count of candidates stored.

        `progress_callback(done, total)` is called periodically (every 100
        anchors, and once at completion) - optional and Qt-agnostic, so a
        desktop worker can wire it to a real progress bar without this
        layer importing Qt. Existing `Status` is preserved across reruns
        (a human already reviewed a candidate stays reviewed), same
        discipline as `DuplicateCandidateRepository.detect_and_store()`.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            if not self._table_exists(connection, "PagesFTSNormalized"):
                LOGGER.info(
                    "PagesFTSNormalized not found (unmigrated database) - "
                    "skipping citation detection."
                )
                return 0
            connection.row_factory = sqlite3.Row

            existing_status = {
                (row["CitingBookID"], row["CitingPageNo"], row["CitedBookID"]): row["Status"]
                for row in connection.execute(
                    "SELECT CitingBookID, CitingPageNo, CitedBookID, Status FROM CitationCandidates"
                ).fetchall()
            }

            books = self._load_books(connection)
            series_by_book = {book_id: series_id for book_id, _, series_id in books}
            anchors = build_title_anchors(books)

            candidates: list[_CitationRow] = []
            total = len(anchors)
            for done, anchor in enumerate(anchors, start=1):
                candidates.extend(
                    self._find_citations_for_anchor(connection, anchor, series_by_book)
                )
                if progress_callback is not None and (done % 100 == 0 or done == total):
                    progress_callback(done, total)

            connection.execute("DELETE FROM CitationCandidates")
            connection.executemany(
                "INSERT INTO CitationCandidates "
                "(CitingBookID, CitingPageNo, CitingParagraphID, CitedBookID, "
                "MatchedTitleText, MatchType, Status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    (*candidate, existing_status.get(
                        (candidate[0], candidate[1], candidate[3]), "pending"
                    ))
                    for candidate in candidates
                ),
            )
            connection.commit()

        LOGGER.info("Citation candidate detection complete: %d found.", len(candidates))
        return len(candidates)

    def time_sample(self, sample_size: int) -> SampleTimingResult:
        """Time real per-anchor detection work for a random sample of
        anchors, without writing anything - lets a `--sample` CLI run
        measure real per-machine timing (disk speed/cache warmth vary
        widely) before committing to a full run. Real measured range
        against the production database: 15 minutes (warm OS page cache)
        to 2+ hours (cold cache) for the full ~83,763-anchor corpus.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            if not self._table_exists(connection, "PagesFTSNormalized"):
                return SampleTimingResult(0, 0, 0.0, 0.0)
            connection.row_factory = sqlite3.Row
            books = self._load_books(connection)
            series_by_book = {book_id: series_id for book_id, _, series_id in books}
            anchors = build_title_anchors(books)
            sample = random.sample(anchors, min(sample_size, len(anchors)))

            start = time.monotonic()
            for anchor in sample:
                self._find_citations_for_anchor(connection, anchor, series_by_book)
            elapsed = time.monotonic() - start

        per_anchor = elapsed / len(sample) if sample else 0.0
        return SampleTimingResult(
            sampled=len(sample),
            total_anchors=len(anchors),
            elapsed_seconds=elapsed,
            estimated_total_seconds=per_anchor * len(anchors),
        )

    def _load_books(
        self, connection: sqlite3.Connection
    ) -> list[tuple[int, str, int | None]]:
        query = (
            "SELECT BookID, Title, SeriesID FROM Books WHERE Title IS NOT NULL"
            if self._has_series_column(connection)
            else "SELECT BookID, Title, NULL AS SeriesID FROM Books WHERE Title IS NOT NULL"
        )
        return [
            (row["BookID"], row["Title"], row["SeriesID"])
            for row in connection.execute(query).fetchall()
        ]

    def _find_citations_for_anchor(
        self,
        connection: sqlite3.Connection,
        anchor: TitleAnchor,
        series_by_book: dict[int, int | None],
    ) -> list[_CitationRow]:
        phrase = escape_fts_phrase(anchor.normalized_title)
        try:
            hits = connection.execute(
                "SELECT rowid FROM PagesFTSNormalized WHERE PagesFTSNormalized MATCH ?", (phrase,)
            ).fetchall()
        except sqlite3.OperationalError:
            # A title containing real FTS5 syntax characters even after
            # phrase-quoting/escaping (rare) - skip rather than crash the
            # whole detection run over one bad anchor.
            LOGGER.warning("Skipping anchor %r: invalid FTS5 phrase query.", anchor.title)
            return []
        if len(hits) > MAX_HITS_PER_ANCHOR:
            LOGGER.info(
                "Skipping anchor %r: %d hits exceeds MAX_HITS_PER_ANCHOR (%d).",
                anchor.title,
                len(hits),
                MAX_HITS_PER_ANCHOR,
            )
            return []

        anchor_series_id = series_by_book.get(anchor.cited_book_id)
        results: list[_CitationRow] = []
        seen_pages: set[tuple[int, int]] = set()
        for hit in hits:
            page_row = connection.execute(
                "SELECT BookID, PageNo FROM Pages WHERE rowid = ?", (hit["rowid"],)
            ).fetchone()
            if page_row is None:
                continue
            citing_book_id, citing_page_no = page_row
            if citing_page_no is None:
                # Real, if rare, data quality gap: Pages.PageNo has no
                # NOT NULL constraint - a page with no real page number
                # can't be a meaningfully citable location. Confirmed via
                # a real production crash: CitationCandidates.CitingPageNo
                # IS NOT NULL rejected the row at the final write step,
                # after all other anchors had already processed.
                continue
            if citing_book_id == anchor.cited_book_id:
                continue
            if (
                anchor_series_id is not None
                and series_by_book.get(citing_book_id) == anchor_series_id
            ):
                continue
            page_key = (citing_book_id, citing_page_no)
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            paragraph_rows = connection.execute(
                "SELECT ParagraphID, Content FROM Paragraphs WHERE BookID = ? AND PageNo = ?",
                (citing_book_id, citing_page_no),
            ).fetchall()
            citing_paragraph_id = resolve_citing_paragraph(
                ((row["ParagraphID"], row["Content"]) for row in paragraph_rows),
                anchor.normalized_title,
            )
            results.append(
                (
                    citing_book_id,
                    citing_page_no,
                    citing_paragraph_id,
                    anchor.cited_book_id,
                    anchor.title,
                    anchor.match_type,
                )
            )
        return results

    def list_candidates(self, *, include_dismissed: bool = False) -> tuple[CitationCandidate, ...]:
        """Return stored citation candidates, excluding dismissed ones by default."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            query = (
                "SELECT CitingBookID, CitingPageNo, CitingParagraphID, CitedBookID, "
                "MatchedTitleText, MatchType, Status FROM CitationCandidates"
            )
            if not include_dismissed:
                query += " WHERE Status != 'dismissed'"
            rows = connection.execute(query).fetchall()
        return tuple(
            CitationCandidate(
                citing_book_id=row[0],
                citing_page_no=row[1],
                citing_paragraph_id=row[2],
                cited_book_id=row[3],
                matched_title_text=row[4],
                match_type=row[5],
                status=row[6],
            )
            for row in rows
        )

    def dismiss(self, citing_book_id: int, citing_page_no: int, cited_book_id: int) -> None:
        """Mark one candidate as reviewed and confirmed not a real citation.

        Persists across future `detect_and_store()` reruns. Purely a
        status change - no row is deleted.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.execute(
                "UPDATE CitationCandidates SET Status = 'dismissed' "
                "WHERE CitingBookID = ? AND CitingPageNo = ? AND CitedBookID = ?",
                (citing_book_id, citing_page_no, cited_book_id),
            )
            connection.commit()

    def dismiss_pair(self, citing_book_id: int, cited_book_id: int) -> int:
        """Dismiss every candidate row for one citing/cited book pair at once.

        A book that heavily cites another (e.g. a commentary citing its
        base text page after page) can produce hundreds of per-page rows
        - a real usability gap `dismiss()` alone doesn't close. Returns
        the number of rows dismissed.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            cursor = connection.execute(
                "UPDATE CitationCandidates SET Status = 'dismissed' "
                "WHERE CitingBookID = ? AND CitedBookID = ?",
                (citing_book_id, cited_book_id),
            )
            connection.commit()
            return cursor.rowcount

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            is not None
        )

    @classmethod
    def _has_series_column(cls, connection: sqlite3.Connection) -> bool:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)").fetchall()}
        return "SeriesID" in columns

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS CitationCandidates (
                CitingBookID      INTEGER NOT NULL REFERENCES Books(BookID),
                CitingPageNo      INTEGER NOT NULL,
                CitingParagraphID INTEGER REFERENCES Paragraphs(ParagraphID),
                CitedBookID       INTEGER NOT NULL REFERENCES Books(BookID),
                MatchedTitleText  TEXT NOT NULL,
                MatchType         TEXT NOT NULL,
                Status            TEXT NOT NULL DEFAULT 'pending',
                PRIMARY KEY (CitingBookID, CitingPageNo, CitedBookID)
            );
            CREATE INDEX IF NOT EXISTS idx_citation_candidates_cited_book
                ON CitationCandidates(CitedBookID);
            """
        )
        connection.commit()
