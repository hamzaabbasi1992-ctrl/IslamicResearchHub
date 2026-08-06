"""SQLite adapter for storing and reviewing real generated MCQ candidates.

Generation itself lives in `mcq_extraction.py`/`AiAgentService`; this
module only persists results and their human review status - mirrors
`flashcard_candidate_repository.py`'s exact shape.
"""

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.application.mcq_extraction import ExtractedMcq
from islamic_research_hub.domain.models.mcq_candidate import McqCandidate

LOGGER = logging.getLogger(__name__)


class McqCandidateRepository:
    """Store and review real generated MCQ candidates, pending human confirmation."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def add_candidate(
        self, book_id: int, start_page: int, end_page: int, mcq: ExtractedMcq
    ) -> int:
        """Store one real MCQ candidate, returning its new `McqCandidateID`."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            cursor = connection.execute(
                "INSERT INTO McqCandidates "
                "(BookID, ChunkStartPage, ChunkEndPage, Question, ExtractedDataJson, Status) "
                "VALUES (?, ?, ?, ?, ?, 'pending')",
                (book_id, start_page, end_page, mcq.question, _serialize_mcq(mcq)),
            )
            connection.commit()
            return cursor.lastrowid

    def list_candidates(
        self, *, book_id: int | None = None, status: str | None = None, include_dismissed: bool = False
    ) -> tuple[McqCandidate, ...]:
        """Return stored MCQ candidates, excluding dismissed ones by
        default. `status`, if given, filters to exactly that status
        (e.g. "confirmed" for Quiz mode) - takes priority over
        `include_dismissed`."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            query = (
                "SELECT McqCandidateID, BookID, ChunkStartPage, ChunkEndPage, "
                "ExtractedDataJson, Status FROM McqCandidates"
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

        candidates: list[McqCandidate] = []
        for row in rows:
            mcq = _deserialize_mcq(row[4])
            if mcq is None:
                continue
            candidates.append(
                McqCandidate(
                    id=row[0],
                    book_id=row[1],
                    chunk_start_page=row[2],
                    chunk_end_page=row[3],
                    mcq=mcq,
                    status=row[5],
                )
            )
        return tuple(candidates)

    def confirm(self, mcq_candidate_id: int) -> None:
        """Mark a candidate as reviewed and verified accurate/study-worthy."""
        self._set_status(mcq_candidate_id, "confirmed")

    def dismiss(self, mcq_candidate_id: int) -> None:
        """Mark a candidate as reviewed and rejected (hallucinated, wrong, or not worth studying)."""
        self._set_status(mcq_candidate_id, "dismissed")

    def _set_status(self, mcq_candidate_id: int, status: str) -> None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.execute(
                "UPDATE McqCandidates SET Status = ? WHERE McqCandidateID = ?",
                (status, mcq_candidate_id),
            )
            connection.commit()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS McqCandidates (
                McqCandidateID    INTEGER PRIMARY KEY,
                BookID            INTEGER NOT NULL REFERENCES Books(BookID),
                ChunkStartPage    INTEGER NOT NULL,
                ChunkEndPage      INTEGER NOT NULL,
                Question          TEXT NOT NULL,
                ExtractedDataJson TEXT NOT NULL,
                Status            TEXT NOT NULL DEFAULT 'pending',
                ExtractedAt       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_mcq_candidates_book ON McqCandidates(BookID);
            """
        )
        connection.commit()


def _serialize_mcq(mcq: ExtractedMcq) -> str:
    return json.dumps(
        {
            "question": mcq.question,
            "options": list(mcq.options),
            "correct_index": mcq.correct_index,
            "quoted_excerpt": mcq.quoted_excerpt,
            "citation": mcq.citation,
        }
    )


def _deserialize_mcq(raw_json: str) -> ExtractedMcq | None:
    try:
        data = json.loads(raw_json)
        options = tuple(data["options"])
        if len(options) != 4:
            raise ValueError("Stored MCQ candidate does not have exactly 4 options.")
        return ExtractedMcq(
            question=data["question"],
            options=options,
            correct_index=data["correct_index"],
            quoted_excerpt=data["quoted_excerpt"],
            citation=data["citation"],
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        LOGGER.warning("Could not deserialize a stored McqCandidate row - skipping.")
        return None
