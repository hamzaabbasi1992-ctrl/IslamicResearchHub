"""Read/write SQLite adapter for real per-book, per-page bookmarks (Phase 5)."""

import sqlite3
from contextlib import closing
from pathlib import Path


class BookmarkRepository:
    """Create/remove/list real bookmarks against the `BookBookmarks` table."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def add_bookmark(self, book_id: int, page_number: int) -> None:
        """Record a real bookmark, safe to call more than once for the same page.

        A silent no-op on a database that hasn't run migration 8 yet (the
        `BookBookmarks` table doesn't exist) - the same graceful-degrade
        pattern used throughout this codebase (e.g.
        `BookBrowserRepository._table_exists`), so opening a book on a
        freshly-imported, not-yet-migrated database never crashes.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO BookBookmarks (BookID, PageNo, CreatedAt) "
                    "VALUES (?, ?, datetime('now'))",
                    (book_id, page_number),
                )

    def remove_bookmark(self, book_id: int, page_number: int) -> None:
        """Remove a bookmark, if it exists."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "DELETE FROM BookBookmarks WHERE BookID = ? AND PageNo = ?",
                    (book_id, page_number),
                )

    def set_bookmark(self, book_id: int, page_number: int, bookmarked: bool) -> None:
        """Add or remove a bookmark depending on `bookmarked`."""
        if bookmarked:
            self.add_bookmark(book_id, page_number)
        else:
            self.remove_bookmark(book_id, page_number)

    def list_bookmarked_pages(self, book_id: int) -> set[int]:
        """Return every real bookmarked page number for one book."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return set()
            rows = connection.execute(
                "SELECT PageNo FROM BookBookmarks WHERE BookID = ?", (book_id,)
            ).fetchall()
        return {row[0] for row in rows}

    @staticmethod
    def _table_exists(connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'BookBookmarks'"
            ).fetchone()
            is not None
        )
