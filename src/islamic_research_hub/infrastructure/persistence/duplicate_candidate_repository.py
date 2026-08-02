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
        """Find title matches (cross-library and within the same library) and
        store them, returning the count stored.

        Originally cross-library only. Real gap found investigating this
        corpus at scale: within-library exact Title+Author duplicates
        (5,396 groups in the current Shamela import alone) were entirely
        invisible to this scan, since the cross-library-only rule skipped
        any title whose matches all shared one `LibraryID`. Same detection
        logic now runs for both cases, distinguished by `match_type` so
        the two are still tellable apart later - same-library matches
        additionally require the same `Author` (title alone is too weak a
        signal within one library, where many entries share no author at
        all), while the cross-library case is unchanged (title alone,
        matching the original behavior).
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT BookID, Title, Author, SourceBookID, LibraryID FROM Books "
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
                if len(libraries) >= 2:
                    candidates.extend(self._pair_up(entries, "exact_title", "exact_title_and_source_id"))
                    continue
                by_author: dict[str, list[sqlite3.Row]] = defaultdict(list)
                for entry in entries:
                    author_key = (entry["Author"] or "").strip().casefold()
                    if author_key:
                        by_author[author_key].append(entry)
                for author_entries in by_author.values():
                    if len(author_entries) < 2:
                        continue
                    candidates.extend(
                        self._pair_up(
                            author_entries,
                            "exact_title_and_author_same_library",
                            "exact_title_and_author_and_source_id_same_library",
                        )
                    )

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

    @staticmethod
    def _pair_up(
        entries: list[sqlite3.Row], match_type: str, same_source_match_type: str
    ) -> list[tuple[int, int, str]]:
        """Pair every non-canonical entry with the lowest-BookID entry in the group."""
        canonical = min(entries, key=lambda entry: entry["BookID"])
        pairs: list[tuple[int, int, str]] = []
        for entry in entries:
            if entry["BookID"] == canonical["BookID"]:
                continue
            same_source_id = (
                entry["SourceBookID"] is not None
                and entry["SourceBookID"] == canonical["SourceBookID"]
            )
            pairs.append(
                (
                    entry["BookID"],
                    canonical["BookID"],
                    same_source_match_type if same_source_id else match_type,
                )
            )
        return pairs

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

    def resolve_empty_stub_duplicates(self) -> int:
        """Remove metadata-only (zero-page) sides of a candidate pair, returning the count removed.

        Only acts when exactly one side of a pair has zero pages and the
        other has real content: the empty side adds no search value and its
        removal cannot lose any content. Pairs where both sides have real
        content are left untouched, since a title match alone is not a
        reliable enough signal to delete real content on.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT dc.BookID, dc.DuplicateOfBookID, b1.PageCount AS P1, b2.PageCount AS P2
                FROM DuplicateCandidates dc
                JOIN Books b1 ON b1.BookID = dc.BookID
                JOIN Books b2 ON b2.BookID = dc.DuplicateOfBookID
                """
            ).fetchall()

            empty_side_book_ids: set[int] = set()
            for row in rows:
                is_book1_empty = row["P1"] == 0
                is_book2_empty = row["P2"] == 0
                if is_book1_empty and not is_book2_empty:
                    empty_side_book_ids.add(row["BookID"])
                elif is_book2_empty and not is_book1_empty:
                    empty_side_book_ids.add(row["DuplicateOfBookID"])

            for book_id in empty_side_book_ids:
                connection.execute("DELETE FROM DuplicateCandidates WHERE BookID = ?", (book_id,))
                connection.execute(
                    "DELETE FROM DuplicateCandidates WHERE DuplicateOfBookID = ?", (book_id,)
                )
                connection.execute("DELETE FROM Categories WHERE BookID = ?", (book_id,))
                connection.execute("DELETE FROM Chapters WHERE BookID = ?", (book_id,))
                connection.execute("DELETE FROM Pages WHERE BookID = ?", (book_id,))
                connection.execute("DELETE FROM Books WHERE BookID = ?", (book_id,))
            connection.commit()

        LOGGER.info("Removed %d empty-stub duplicate(s).", len(empty_side_book_ids))
        return len(empty_side_book_ids)

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
