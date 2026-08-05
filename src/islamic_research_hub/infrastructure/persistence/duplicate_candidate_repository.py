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

_BOOK_REFERENCING_TABLES: tuple[str, ...] = (
    "Categories",
    "Chapters",
    "Pages",
    "Footnotes",
    "Paragraphs",
    "BookTaxonomyTerms",
    "PageEmbeddings",
    "PdfMatchCandidates",
    "BookPublicationDetails",
    "BookBookmarks",
    "RecentBooks",
    "BookRatings",
    "EventCandidates",
    "NarratorCandidates",
)
"""Every real table (besides `Books` and `DuplicateCandidates`, handled
separately) with a `BookID` column, found by inspecting the live schema.
Kept explicit rather than introspected at call time, so a future new table
is a deliberate, reviewable addition here - not a silent gap in book
deletion. `resolve_empty_stub_duplicates()`'s original delete list
(Categories/Chapters/Pages only) predates several of these tables
(Footnotes, Paragraphs, BookTaxonomyTerms, PageEmbeddings,
PdfMatchCandidates, ...) - harmless for that method in practice (a
zero-page stub book was never going to have footnotes or paragraphs
either), but a real gap for deleting a book with actual content, which is
exactly what `remove_book()` below needs to do correctly.
"""


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
            # Preserved across the DELETE/re-INSERT below so a pair a human
            # already reviewed and dismiss()'d stays dismissed on rescan -
            # detect_and_store() only recomputes *which pairs* match, not
            # their review status.
            existing_status = {
                (row["BookID"], row["DuplicateOfBookID"]): row["Status"]
                for row in connection.execute(
                    "SELECT BookID, DuplicateOfBookID, Status FROM DuplicateCandidates"
                ).fetchall()
            }
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
                "INSERT INTO DuplicateCandidates (BookID, DuplicateOfBookID, MatchType, Status) "
                "VALUES (?, ?, ?, ?)",
                (
                    (book_id, duplicate_of_book_id, match_type, existing_status.get(
                        (book_id, duplicate_of_book_id), "pending"
                    ))
                    for book_id, duplicate_of_book_id, match_type in candidates
                ),
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

    def list_candidates(self, *, include_dismissed: bool = False) -> tuple[DuplicateCandidate, ...]:
        """Return stored duplicate candidates, excluding dismissed ones by default."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            query = "SELECT BookID, DuplicateOfBookID, MatchType, Status FROM DuplicateCandidates"
            if not include_dismissed:
                query += " WHERE Status != 'dismissed'"
            rows = connection.execute(query).fetchall()
        return tuple(
            DuplicateCandidate(
                book_id=row[0], duplicate_of_book_id=row[1], match_type=row[2], status=row[3]
            )
            for row in rows
        )

    def dismiss(self, book_id: int, duplicate_of_book_id: int) -> None:
        """Mark a candidate pair as reviewed and confirmed not a duplicate.

        Persists (unlike the Duplicate Manager screen's old session-only
        Skip): stays dismissed across future detect_and_store() re-scans,
        since re-flagging a pair a human already reviewed is just noise.
        Purely a status change - no row is deleted, no book content touched.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.execute(
                "UPDATE DuplicateCandidates SET Status = 'dismissed' "
                "WHERE BookID = ? AND DuplicateOfBookID = ?",
                (book_id, duplicate_of_book_id),
            )
            connection.commit()

    def resolve_empty_stub_duplicates(self) -> int:
        """Remove metadata-only (zero-page) sides of a candidate pair, returning the count removed.

        Only acts when exactly one side of a pair has zero pages and the
        other has real content: the empty side adds no search value and its
        removal cannot lose any content. Pairs where both sides have real
        content are left untouched, since a title match alone is not a
        reliable enough signal to delete real content on. Dismissed pairs
        (a human already confirmed these are different books) are excluded
        too - dismissal means the empty side is a real, separate book with
        no content yet, not a stub duplicate of its sibling.
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
                WHERE dc.Status != 'dismissed'
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
                self._delete_book(connection, book_id)
            connection.commit()

        LOGGER.info("Removed %d empty-stub duplicate(s).", len(empty_side_book_ids))
        return len(empty_side_book_ids)

    def export_book(self, book_id: int) -> dict[str, list[dict[str, object]]]:
        """Dump every real row for one book (Books + every referencing table),
        as plain JSON-serializable dicts, for a human-reviewable backup
        before `remove_book()` deletes it. Excludes `PageEmbeddings` (a
        derived BLOB index, regenerable by re-running `semantic_index_cli.py`
        - not original corpus content worth backing up).
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            existing_tables = self._existing_tables(connection)
            export: dict[str, list[dict[str, object]]] = {}
            export["Books"] = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM Books WHERE BookID = ?", (book_id,)
                ).fetchall()
            ]
            for table in _BOOK_REFERENCING_TABLES:
                if table == "PageEmbeddings" or table not in existing_tables:
                    continue
                export[table] = [
                    dict(row)
                    for row in connection.execute(
                        f"SELECT * FROM {table} WHERE BookID = ?", (book_id,)
                    ).fetchall()
                ]
        return export

    def remove_book(self, book_id: int) -> None:
        """Permanently delete one book and every row across the schema that
        references it. Real, irreversible data deletion - callers must have
        already decided (and ideally backed up via `export_book()`) before
        calling this; nothing here asks for confirmation.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            self._delete_book(connection, book_id)
            connection.commit()

    @classmethod
    def _delete_book(cls, connection: sqlite3.Connection, book_id: int) -> None:
        """Delete a book and every row across the schema that references it.
        Shared by `resolve_empty_stub_duplicates()` and `remove_book()` -
        does not commit (callers control the transaction). Skips any table
        in `_BOOK_REFERENCING_TABLES` that doesn't exist yet on this
        database (e.g. a test fixture built directly via
        `MasterBookRepository`, without running `MigrationRunner`, or a
        production database from before a given migration ran).
        """
        connection.execute("DELETE FROM DuplicateCandidates WHERE BookID = ?", (book_id,))
        connection.execute("DELETE FROM DuplicateCandidates WHERE DuplicateOfBookID = ?", (book_id,))
        existing_tables = cls._existing_tables(connection)
        if "CitationCandidates" in existing_tables:
            # CitationCandidates has two book-reference columns (CitingBookID,
            # CitedBookID), so it can't join the generic single-BookID-column
            # loop below - same two-sided treatment as DuplicateCandidates above.
            connection.execute("DELETE FROM CitationCandidates WHERE CitingBookID = ?", (book_id,))
            connection.execute("DELETE FROM CitationCandidates WHERE CitedBookID = ?", (book_id,))
        for table in _BOOK_REFERENCING_TABLES:
            if table in existing_tables:
                connection.execute(f"DELETE FROM {table} WHERE BookID = ?", (book_id,))
        connection.execute("DELETE FROM Books WHERE BookID = ?", (book_id,))

    @staticmethod
    def _existing_tables(connection: sqlite3.Connection) -> set[str]:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        """Create the duplicate candidates table when it does not yet exist.

        `Status` is added defensively (`ALTER TABLE`) rather than in the
        `CREATE TABLE IF NOT EXISTS` above, since this table isn't part of
        the versioned `MigrationRunner` system - it's created ad hoc, right
        here, the first time this repository runs against a database. A
        production database from before `Status` existed already has this
        table without the column, so `IF NOT EXISTS` alone would silently
        skip adding it.
        """
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
        existing_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(DuplicateCandidates)").fetchall()
        }
        if "Status" not in existing_columns:
            connection.execute(
                "ALTER TABLE DuplicateCandidates ADD COLUMN Status TEXT NOT NULL DEFAULT 'pending'"
            )
        connection.commit()
