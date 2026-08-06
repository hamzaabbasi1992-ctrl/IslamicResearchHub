"""Read/write SQLite adapter for real named research collections (Phase
14 Milestone 1), against the `Collections`/`CollectionItems` tables."""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.collection import Collection, CollectionItem


class CollectionNameTakenError(Exception):
    """Raised when creating/renaming a collection to a name that's
    already in use - `Collections.Name` is uniquely indexed for real
    (case-sensitive) collisions."""


class CollectionRepository:
    """Create/rename/delete collections and add/remove/list their items,
    against the `Collections`/`CollectionItems` tables."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def create_collection(self, name: str) -> int:
        """Create a new, empty collection and return its real ID.

        Raises `CollectionNameTakenError` on a real name collision -
        never silently renames or overwrites an existing collection.
        """
        normalized = name.strip()
        if not normalized:
            raise ValueError("Collection name must not be empty.")
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return 0
            with connection:
                try:
                    cursor = connection.execute(
                        "INSERT INTO Collections (Name) VALUES (?)", (normalized,)
                    )
                except sqlite3.IntegrityError as error:
                    raise CollectionNameTakenError(
                        f"A collection named {normalized!r} already exists."
                    ) from error
                return cursor.lastrowid

    def rename_collection(self, collection_id: int, new_name: str) -> None:
        normalized = new_name.strip()
        if not normalized:
            raise ValueError("Collection name must not be empty.")
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                try:
                    connection.execute(
                        "UPDATE Collections SET Name = ? WHERE CollectionID = ?",
                        (normalized, collection_id),
                    )
                except sqlite3.IntegrityError as error:
                    raise CollectionNameTakenError(
                        f"A collection named {normalized!r} already exists."
                    ) from error

    def delete_collection(self, collection_id: int) -> None:
        """Delete a collection and every real item in it."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "DELETE FROM CollectionItems WHERE CollectionID = ?", (collection_id,)
                )
                connection.execute(
                    "DELETE FROM Collections WHERE CollectionID = ?", (collection_id,)
                )

    def list_collections(self) -> tuple[Collection, ...]:
        """Return every real collection, most recently created first,
        each with its real current item count."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return ()
            rows = connection.execute(
                """
                SELECT c.CollectionID, c.Name, c.CreatedAt, COUNT(ci.BookID)
                FROM Collections c
                LEFT JOIN CollectionItems ci ON ci.CollectionID = c.CollectionID
                GROUP BY c.CollectionID
                ORDER BY c.CreatedAt DESC, c.CollectionID DESC
                """
            ).fetchall()
        return tuple(Collection(*row) for row in rows)

    def add_item(self, collection_id: int, book_id: int, page_number: int) -> None:
        """Add a real page to a collection, safe to call more than once
        for the same page - never requires the page to already be a
        separate bookmark."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO CollectionItems (CollectionID, BookID, PageNo) "
                    "VALUES (?, ?, ?)",
                    (collection_id, book_id, page_number),
                )

    def remove_item(self, collection_id: int, book_id: int, page_number: int) -> None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "DELETE FROM CollectionItems "
                    "WHERE CollectionID = ? AND BookID = ? AND PageNo = ?",
                    (collection_id, book_id, page_number),
                )

    def list_items(self, collection_id: int) -> tuple[CollectionItem, ...]:
        """Return every real item in one collection, in the real order
        they were added."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return ()
            rows = connection.execute(
                """
                SELECT ci.BookID, ci.PageNo, b.Title, ci.AddedAt
                FROM CollectionItems ci
                JOIN Books b ON b.BookID = ci.BookID
                WHERE ci.CollectionID = ?
                ORDER BY ci.AddedAt ASC, ci.rowid ASC
                """,
                (collection_id,),
            ).fetchall()
        return tuple(
            CollectionItem(book_id, page_number, title or "", added_at)
            for book_id, page_number, title, added_at in rows
        )

    @staticmethod
    def _table_exists(connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'Collections'"
            ).fetchone()
            is not None
        )
