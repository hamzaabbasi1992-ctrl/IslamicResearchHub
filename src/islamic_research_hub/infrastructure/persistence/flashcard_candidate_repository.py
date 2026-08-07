"""SQLite adapter for storing and reviewing real generated flashcard
candidates, and (Phase 15's deferred scheduling milestone) their real
SM-2 spaced-repetition review state.

Generation itself lives in `flashcard_extraction.py`/`AiAgentService`;
this module only persists results, their human review status, and -
once confirmed - how well a real human has been remembering each one.
Mirrors `event_candidate_repository.py`'s exact shape.
"""

import json
import logging
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from islamic_research_hub.application.flashcard_extraction import ExtractedFlashcard
from islamic_research_hub.application.spaced_repetition import (
    FRESH_REVIEW_STATE,
    ReviewState,
    schedule_next_review,
)
from islamic_research_hub.domain.models.flashcard_candidate import FlashcardCandidate
from islamic_research_hub.domain.models.flashcard_review_state import FlashcardReviewState

LOGGER = logging.getLogger(__name__)

_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
"""Matches SQLite's own `datetime('now')` output format exactly (no
'T', no timezone suffix) so `DueAt <= ?` comparisons against a Python-
computed timestamp sort correctly against real SQLite-generated ones."""


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

    def record_review(self, flashcard_candidate_id: int, grade: str) -> FlashcardReviewState:
        """Grade one real review ("again" / "good" / "easy") and persist
        the resulting real SM-2 schedule, returning it.

        A card with no prior review state starts from `FRESH_REVIEW_STATE`
        - its first-ever review always sets a real, non-empty schedule.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            current = self._read_review_state(connection, flashcard_candidate_id)
            previous = (
                ReviewState(
                    ease_factor=current.ease_factor,
                    interval_days=current.interval_days,
                    repetitions=current.repetitions,
                )
                if current is not None
                else FRESH_REVIEW_STATE
            )
            next_state = schedule_next_review(previous, grade)
            now = datetime.utcnow()
            reviewed_at = now.strftime(_TIMESTAMP_FORMAT)
            due_at = (now + timedelta(days=next_state.interval_days)).strftime(_TIMESTAMP_FORMAT)
            connection.execute(
                """
                INSERT INTO FlashcardReviewState
                    (FlashcardCandidateID, EaseFactor, IntervalDays, Repetitions, DueAt, LastReviewedAt)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(FlashcardCandidateID) DO UPDATE SET
                    EaseFactor = excluded.EaseFactor,
                    IntervalDays = excluded.IntervalDays,
                    Repetitions = excluded.Repetitions,
                    DueAt = excluded.DueAt,
                    LastReviewedAt = excluded.LastReviewedAt
                """,
                (
                    flashcard_candidate_id,
                    next_state.ease_factor,
                    next_state.interval_days,
                    next_state.repetitions,
                    due_at,
                    reviewed_at,
                ),
            )
            connection.commit()
            return FlashcardReviewState(
                flashcard_candidate_id=flashcard_candidate_id,
                ease_factor=next_state.ease_factor,
                interval_days=next_state.interval_days,
                repetitions=next_state.repetitions,
                due_at=due_at,
                last_reviewed_at=reviewed_at,
            )

    def get_review_state(self, flashcard_candidate_id: int) -> FlashcardReviewState | None:
        """Return one card's real review state, or None if it's never been reviewed."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            return self._read_review_state(connection, flashcard_candidate_id)

    def due_candidates(self, *, as_of: str | None = None) -> tuple[FlashcardCandidate, ...]:
        """Return every real *confirmed* candidate due for review right
        now - never reviewed yet (immediately due), or whose real
        `DueAt` has already passed. Never an unreviewed/dismissed
        candidate, same discipline as `list_candidates(status="confirmed")`.
        """
        cutoff = as_of or datetime.utcnow().strftime(_TIMESTAMP_FORMAT)
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            rows = connection.execute(
                """
                SELECT c.FlashcardCandidateID, c.BookID, c.ChunkStartPage, c.ChunkEndPage,
                       c.ExtractedDataJson, c.Status
                FROM FlashcardCandidates c
                LEFT JOIN FlashcardReviewState r ON r.FlashcardCandidateID = c.FlashcardCandidateID
                WHERE c.Status = 'confirmed' AND (r.DueAt IS NULL OR r.DueAt <= ?)
                ORDER BY COALESCE(r.DueAt, c.ExtractedAt)
                """,
                (cutoff,),
            ).fetchall()

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

    @staticmethod
    def _read_review_state(
        connection: sqlite3.Connection, flashcard_candidate_id: int
    ) -> FlashcardReviewState | None:
        row = connection.execute(
            """
            SELECT EaseFactor, IntervalDays, Repetitions, DueAt, LastReviewedAt
            FROM FlashcardReviewState WHERE FlashcardCandidateID = ?
            """,
            (flashcard_candidate_id,),
        ).fetchone()
        if row is None:
            return None
        return FlashcardReviewState(
            flashcard_candidate_id=flashcard_candidate_id,
            ease_factor=row[0],
            interval_days=row[1],
            repetitions=row[2],
            due_at=row[3],
            last_reviewed_at=row[4],
        )

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

            CREATE TABLE IF NOT EXISTS FlashcardReviewState (
                FlashcardCandidateID INTEGER PRIMARY KEY
                    REFERENCES FlashcardCandidates(FlashcardCandidateID),
                EaseFactor     REAL NOT NULL,
                IntervalDays   INTEGER NOT NULL,
                Repetitions    INTEGER NOT NULL,
                DueAt          TEXT NOT NULL,
                LastReviewedAt TEXT NOT NULL
            );
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
