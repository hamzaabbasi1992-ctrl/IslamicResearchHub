"""Read/write SQLite adapter for real named saved searches (Phase 14
deferred scope), against the `SavedSearches` table.

Mirrors `collection_repository.py`'s exact shape: same
`_table_exists()` honest-degrade guard for a database that hasn't run
this migration yet, same unique-name collision handling.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.saved_search import SavedSearch


class SavedSearchNameTakenError(Exception):
    """Raised when saving a search under a name already in use -
    `SavedSearches.Name` is uniquely indexed for real (case-sensitive)
    collisions."""


class SavedSearchRepository:
    """Save/list/delete real saved searches, against the `SavedSearches` table."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def save_search(
        self,
        name: str,
        query: str,
        library: str | None,
        author: str | None,
        category: str | None,
        exact: bool,
        scope: str,
        search_target: str,
    ) -> int:
        """Save one real search and return its new ID.

        Raises `SavedSearchNameTakenError` on a real name collision -
        never silently renames or overwrites an existing saved search.
        """
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Saved search name must not be empty.")
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Saved search query must not be empty.")
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return 0
            with connection:
                try:
                    cursor = connection.execute(
                        """
                        INSERT INTO SavedSearches (
                            Name, Query, Library, Author, Category,
                            ExactMatch, Scope, SearchTarget
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            normalized_name,
                            normalized_query,
                            library,
                            author,
                            category,
                            int(exact),
                            scope,
                            search_target,
                        ),
                    )
                except sqlite3.IntegrityError as error:
                    raise SavedSearchNameTakenError(
                        f"A saved search named {normalized_name!r} already exists."
                    ) from error
                return cursor.lastrowid

    def list_searches(self) -> tuple[SavedSearch, ...]:
        """Return every real saved search, most recently created first."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return ()
            rows = connection.execute(
                """
                SELECT SavedSearchID, Name, Query, Library, Author, Category,
                       ExactMatch, Scope, SearchTarget, CreatedAt
                FROM SavedSearches
                ORDER BY CreatedAt DESC, SavedSearchID DESC
                """
            ).fetchall()
        return tuple(
            SavedSearch(
                saved_search_id=row[0],
                name=row[1],
                query=row[2],
                library=row[3],
                author=row[4],
                category=row[5],
                exact=bool(row[6]),
                scope=row[7],
                search_target=row[8],
                created_at=row[9],
            )
            for row in rows
        )

    def delete_search(self, saved_search_id: int) -> None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "DELETE FROM SavedSearches WHERE SavedSearchID = ?", (saved_search_id,)
                )

    @staticmethod
    def _table_exists(connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'SavedSearches'"
            ).fetchone()
            is not None
        )
