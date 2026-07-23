"""SQLite adapter for detecting and persisting possible cross-library duplicates.

Detection is title-based only, across libraries, and is intentionally
informational: nothing here deletes or merges data. It exists so duplicate
candidates are durable, queryable records rather than one-off findings that
only lived in a scratch analysis, and can be recomputed as more libraries
are imported.
"""

import logging
import sqlite3
from collections import defaultdict
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.duplicate_candidate import DuplicateCandidate

LOGGER = logging.getLogger(__name__)


class DuplicateCandidateRepository:
    """Detect and store possible cross-library duplicate book pairings."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def detect_and_store(self) -> int:
        """Find cross-library title matches and store them, returning the count stored."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT BookID, Title, SourceBookID, LibraryID FROM Books "
                "WHERE Title IS NOT NULL"
            ).fetchall()

            by_title: dict[str, list[sqlite3.Row]] = defaultdict(list)
            for row in rows:
                normalized = " ".join(row["Title"].split()).strip().casefold()
                if normalized:
                    by_title[normalized].append(row)

            candidates: list[tuple[int, int, str]] = []
            for entries in by_title.values():
                libraries = {entry["LibraryID"] for entry in entries}
                if len(libraries) < 2:
                    continue
                canonical = min(entries, key=lambda entry: entry["BookID"])
                for entry in entries:
                    if entry["BookID"] == canonical["BookID"]:
                        continue
                    same_source_id = (
                        entry["SourceBookID"] is not None
                        and entry["SourceBookID"] == canonical["SourceBookID"]
                    )
                    match_type = (
                        "exact_title_and_source_id" if same_source_id else "exact_title"
                    )
                    candidates.append((entry["BookID"], canonical["BookID"], match_type))

            connection.execute("DELETE FROM DuplicateCandidates")
            connection.executemany(
                "INSERT INTO DuplicateCandidates (BookID, DuplicateOfBookID, MatchType) "
                "VALUES (?, ?, ?)",
                candidates,
            )
            connection.commit()

        LOGGER.info(
            "Duplicate candidate detection complete: %d pair(s) found.", len(candidates)
        )
        return len(candidates)

    def list_candidates(self) -> tuple[DuplicateCandidate, ...]:
        """Return every stored duplicate candidate."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            rows = connection.execute(
                "SELECT BookID, DuplicateOfBookID, MatchType FROM DuplicateCandidates"
            ).fetchall()
        return tuple(
            DuplicateCandidate(book_id=row[0], duplicate_of_book_id=row[1], match_type=row[2])
            for row in rows
        )

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        """Create the duplicate candidates table when it does not yet exist."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS DuplicateCandidates (
                BookID INTEGER NOT NULL REFERENCES Books(BookID),
                DuplicateOfBookID INTEGER NOT NULL REFERENCES Books(BookID),
                MatchType TEXT NOT NULL,
                PRIMARY KEY (BookID, DuplicateOfBookID)
            );
            """
        )
        connection.commit()
