"""SQLite adapter for storing and reviewing real extracted event candidates.

Detection itself lives in `event_extraction.py`/`AiAgentService`; this
module only persists results and their human review status - the same
"detected candidate, never trusted until reviewed" discipline as
`CitationCandidateRepository`/`DuplicateCandidateRepository`.
"""

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.application.event_extraction import ExtractedEvent
from islamic_research_hub.domain.models.event_candidate import EventCandidate

LOGGER = logging.getLogger(__name__)


class EventCandidateRepository:
    """Store and review real extracted event candidates, pending human confirmation."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def add_candidate(
        self, book_id: int, start_page: int, end_page: int, event: ExtractedEvent
    ) -> int:
        """Store one real extracted event candidate, returning its new `EventCandidateID`."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            cursor = connection.execute(
                "INSERT INTO EventCandidates "
                "(BookID, ChunkStartPage, ChunkEndPage, Title, ExtractedDataJson, Status) "
                "VALUES (?, ?, ?, ?, ?, 'pending')",
                (book_id, start_page, end_page, event.title, _serialize_event(event)),
            )
            connection.commit()
            return cursor.lastrowid

    def list_candidates(
        self, *, book_id: int | None = None, include_dismissed: bool = False
    ) -> tuple[EventCandidate, ...]:
        """Return stored event candidates, excluding dismissed ones by default."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            query = (
                "SELECT EventCandidateID, BookID, ChunkStartPage, ChunkEndPage, "
                "ExtractedDataJson, Status FROM EventCandidates"
            )
            conditions: list[str] = []
            params: list[object] = []
            if book_id is not None:
                conditions.append("BookID = ?")
                params.append(book_id)
            if not include_dismissed:
                conditions.append("Status != 'dismissed'")
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            rows = connection.execute(query, params).fetchall()

        candidates: list[EventCandidate] = []
        for row in rows:
            event = _deserialize_event(row[4])
            if event is None:
                continue
            candidates.append(
                EventCandidate(
                    id=row[0],
                    book_id=row[1],
                    chunk_start_page=row[2],
                    chunk_end_page=row[3],
                    event=event,
                    status=row[5],
                )
            )
        return tuple(candidates)

    def confirm(self, event_candidate_id: int) -> None:
        """Mark a candidate as reviewed and verified accurate."""
        self._set_status(event_candidate_id, "confirmed")

    def dismiss(self, event_candidate_id: int) -> None:
        """Mark a candidate as reviewed and rejected (hallucinated or wrong)."""
        self._set_status(event_candidate_id, "dismissed")

    def _set_status(self, event_candidate_id: int, status: str) -> None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.execute(
                "UPDATE EventCandidates SET Status = ? WHERE EventCandidateID = ?",
                (status, event_candidate_id),
            )
            connection.commit()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS EventCandidates (
                EventCandidateID INTEGER PRIMARY KEY,
                BookID            INTEGER NOT NULL REFERENCES Books(BookID),
                ChunkStartPage    INTEGER NOT NULL,
                ChunkEndPage      INTEGER NOT NULL,
                Title             TEXT NOT NULL,
                ExtractedDataJson TEXT NOT NULL,
                Status            TEXT NOT NULL DEFAULT 'pending',
                ExtractedAt       TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_event_candidates_book ON EventCandidates(BookID);
            """
        )
        connection.commit()


def _serialize_event(event: ExtractedEvent) -> str:
    return json.dumps(
        {
            "title": event.title,
            "alternate_names": list(event.alternate_names),
            "subject": event.subject,
            "date_hijri": event.date_hijri,
            "date_gregorian": event.date_gregorian,
            "location": event.location,
            "background": event.background,
            "summary": event.summary,
            "key_figures": list(event.key_figures),
            "quoted_excerpt": event.quoted_excerpt,
            "citation": event.citation,
        }
    )


def _deserialize_event(raw_json: str) -> ExtractedEvent | None:
    try:
        data = json.loads(raw_json)
        return ExtractedEvent(
            title=data["title"],
            alternate_names=tuple(data.get("alternate_names", [])),
            subject=data["subject"],
            date_hijri=data.get("date_hijri"),
            date_gregorian=data.get("date_gregorian"),
            location=data.get("location"),
            background=data["background"],
            summary=data["summary"],
            key_figures=tuple(data.get("key_figures", [])),
            quoted_excerpt=data["quoted_excerpt"],
            citation=data["citation"],
        )
    except (json.JSONDecodeError, KeyError):
        LOGGER.warning("Could not deserialize a stored EventCandidate row - skipping.")
        return None
