"""SQLite adapter for storing and reviewing real generated flashcard
candidates.

Generation itself lives in `flashcard_extraction.py`/`AiAgentService`;
this module only persists results and their human review status -
mirrors `event_candidate_repository.py`'s exact shape.
"""

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.application.flashcard_extraction import ExtractedFlashcard
from islamic_research_hub.domain.models.flashcard_candidate import FlashcardCandidate

LOGGER = logging.getLogger(__name__)


class FlashcardCandidateRepository:
    """Store and review real generated flashcard candidates, pending human confirmation."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def add_candidate(
        self, book_id: int, start_page: int, end_page: int, flashcard: ExtractedFlashcard
    ) -> int:
        """Store one real flashcard candidate, returning its new `FlashcardCandidateID`."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            cursor = connection.execute(
                "INSERT INTO FlashcardCandidates "
                "(BookID, ChunkStartPage, ChunkEndPage, Front, ExtractedDataJson, Status) "
                "VALUES (?, ?, ?, ?, ?, 'pending')",
                (book_id, start_page, end_page, flashcard.front, _serialize_flashcard(flashcard)),
            )
            connection.commit()
            return cursor.lastrowid

    def list_candidates(
        self, *, book_id: int | None = None, status: str | None = None, include_dismissed: bool = False
    ) -> tuple[FlashcardCandidate, ...]:
        """Return stored flashcard candidates, excluding dismissed ones by
        default. `status`, if given, filters to exactly that status
        (e.g. "confirmed" for Study mode) - takes priority over
        `include_dismissed`."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            query = (
                "SELECT FlashcardCandidateID, BookID, ChunkStartPage, ChunkEndPage, "
                "ExtractedDataJson, Status FROM FlashcardCandidates"
            )
            conditions: list[str] = []
            params: list[object] = []
            if book_id is not None:
                conditions.append("BookID = ?")
                params.append(book_id)
            if status is not None:
                conditions.append("Status = ?")
                params.append(status)
            elif not include_dismissed:
                conditions.append("Status != 'dismissed'")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            rows = connection.execute(query, params).fetchall()

        candidates: list[FlashcardCandidate] = []
        for row in rows:
            flashcard = _deserialize_flashcard(row[4])
            if flashcard is None:
                continue
            candidates.append(
                FlashcardCandidate(
                    id=row[0],
                    book_id=row[1],
                    chunk_start_page=row[2],
                    chunk_end_page=row[3],
                    flashcard=flashcard,
                    status=row[5],
                )
            )
        return tuple(candidates)

    def confirm(self, flashcard_candidate_id: int) -> None:
        """Mark a candidate as reviewed and verified accurate/study-worthy."""
        self._set_status(flashcard_candidate_id, "confirmed")

    def dismiss(self, flashcard_candidate_id: int) -> None:
        """Mark a candidate as reviewed and rejected (hallucinated, wrong, or not worth studying)."""
        self._set_status(flashcard_candidate_id, "dismissed")

    def _set_status(self, flashcard_candidate_id: int, status: str) -> None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.execute(
                "UPDATE FlashcardCandidates SET Status = ? WHERE FlashcardCandidateID = ?",
                (status, flashcard_candidate_id),
            )
            connection.commit()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS FlashcardCandidates (
                FlashcardCandidateID INTEGER PRIMARY KEY,
                BookID            INTEGER NOT NULL REFERENCES Books(BookID),
                ChunkStartPage    INTEGER NOT NULL,
                ChunkEndPage      INTEGER NOT NULL,
                Front             TEXT NOT NULL,
                ExtractedDataJson TEXT NOT NULL,
                Status            TEXT NOT NULL DEFAULT 'pending',
                ExtractedAt       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_flashcard_candidates_book ON FlashcardCandidates(BookID);
            """
        )
        connection.commit()


def _serialize_flashcard(flashcard: ExtractedFlashcard) -> str:
    return json.dumps(
        {
            "front": flashcard.front,
            "back": flashcard.back,
            "quoted_excerpt": flashcard.quoted_excerpt,
            "citation": flashcard.citation,
        }
    )


def _deserialize_flashcard(raw_json: str) -> ExtractedFlashcard | None:
    try:
        data = json.loads(raw_json)
        return ExtractedFlashcard(
            front=data["front"],
            back=data["back"],
            quoted_excerpt=data["quoted_excerpt"],
            citation=data["citation"],
        )
    except (json.JSONDecodeError, KeyError):
        LOGGER.warning("Could not deserialize a stored FlashcardCandidate row - skipping.")
        return None
