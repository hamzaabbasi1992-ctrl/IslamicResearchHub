"""SQLite adapter for storing and reviewing real extracted narrator candidates.

Detection itself lives in `narrator_extraction.py`/`AiAgentService`; this
module only persists results and their human review status - the same
"detected candidate, never trusted until reviewed" discipline as
`EventCandidateRepository`/`CitationCandidateRepository`.
"""

import json
import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.application.narrator_extraction import ExtractedNarrator
from islamic_research_hub.domain.models.narrator_candidate import NarratorCandidate

LOGGER = logging.getLogger(__name__)


class NarratorCandidateRepository:
    """Store and review real extracted narrator candidates, pending human confirmation."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def add_candidate(
        self, book_id: int, start_page: int, end_page: int, narrator: ExtractedNarrator
    ) -> int:
        """Store one real extracted narrator candidate, returning its new `NarratorCandidateID`."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            cursor = connection.execute(
                "INSERT INTO NarratorCandidates "
                "(BookID, ChunkStartPage, ChunkEndPage, Name, ExtractedDataJson, Status) "
                "VALUES (?, ?, ?, ?, ?, 'pending')",
                (book_id, start_page, end_page, narrator.name, _serialize_narrator(narrator)),
            )
            connection.commit()
            return cursor.lastrowid

    def list_candidates(
        self, *, book_id: int | None = None, include_dismissed: bool = False
    ) -> tuple[NarratorCandidate, ...]:
        """Return stored narrator candidates, excluding dismissed ones by default."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            query = (
                "SELECT NarratorCandidateID, BookID, ChunkStartPage, ChunkEndPage, "
                "ExtractedDataJson, Status FROM NarratorCandidates"
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

        candidates: list[NarratorCandidate] = []
        for row in rows:
            narrator = _deserialize_narrator(row[4])
            if narrator is None:
                continue
            candidates.append(
                NarratorCandidate(
                    id=row[0],
                    book_id=row[1],
                    chunk_start_page=row[2],
                    chunk_end_page=row[3],
                    narrator=narrator,
                    status=row[5],
                )
            )
        return tuple(candidates)

    def confirm(self, narrator_candidate_id: int) -> None:
        """Mark a candidate as reviewed and verified accurate."""
        self._set_status(narrator_candidate_id, "confirmed")

    def dismiss(self, narrator_candidate_id: int) -> None:
        """Mark a candidate as reviewed and rejected (hallucinated or wrong)."""
        self._set_status(narrator_candidate_id, "dismissed")

    def _set_status(self, narrator_candidate_id: int, status: str) -> None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.execute(
                "UPDATE NarratorCandidates SET Status = ? WHERE NarratorCandidateID = ?",
                (status, narrator_candidate_id),
            )
            connection.commit()

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS NarratorCandidates (
                NarratorCandidateID INTEGER PRIMARY KEY,
                BookID               INTEGER NOT NULL REFERENCES Books(BookID),
                ChunkStartPage       INTEGER NOT NULL,
                ChunkEndPage         INTEGER NOT NULL,
                Name                 TEXT NOT NULL,
                ExtractedDataJson    TEXT NOT NULL,
                Status               TEXT NOT NULL DEFAULT 'pending',
                ExtractedAt          TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_narrator_candidates_book ON NarratorCandidates(BookID);
            """
        )
        connection.commit()


def _serialize_narrator(narrator: ExtractedNarrator) -> str:
    return json.dumps(
        {
            "name": narrator.name,
            "alternate_names": list(narrator.alternate_names),
            "kunya_nasab": narrator.kunya_nasab,
            "generation": narrator.generation,
            "hadith_reference": narrator.hadith_reference,
            "quoted_excerpt": narrator.quoted_excerpt,
            "citation": narrator.citation,
        }
    )


def _deserialize_narrator(raw_json: str) -> ExtractedNarrator | None:
    try:
        data = json.loads(raw_json)
        return ExtractedNarrator(
            name=data["name"],
            alternate_names=tuple(data.get("alternate_names", [])),
            kunya_nasab=data.get("kunya_nasab"),
            generation=data.get("generation"),
            hadith_reference=data["hadith_reference"],
            quoted_excerpt=data["quoted_excerpt"],
            citation=data["citation"],
        )
    except (json.JSONDecodeError, KeyError):
        LOGGER.warning("Could not deserialize a stored NarratorCandidate row - skipping.")
        return None
