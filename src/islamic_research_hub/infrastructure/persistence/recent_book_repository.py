"""Read/write SQLite adapter for real "recently opened" book tracking (Phase 5)."""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book_summary import BookSummary

MAX_RECENT_BOOKS = 20
"""Cap on how many recent books are ever returned, so the list stays useful."""


class RecentBookRepository:
    """Record and list real recently-opened books against `RecentBooks`."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def record_open(self, book_id: int, page_number: int | None = None) -> None:
        """Record (or update) that a real book was just opened, at this page.

        A silent no-op on a database that hasn't run migration 8 yet (the
        `RecentBooks` table doesn't exist) - same graceful-degrade pattern
        used throughout this codebase.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "INSERT INTO RecentBooks (BookID, LastPageNo, OpenedAt) "
                    "VALUES (?, ?, datetime('now')) "
                    "ON CONFLICT(BookID) DO UPDATE SET "
                    "LastPageNo = excluded.LastPageNo, OpenedAt = excluded.OpenedAt",
                    (book_id, page_number),
                )

    def list_recent(self, limit: int = MAX_RECENT_BOOKS) -> tuple[BookSummary, ...]:
        """Return real recently-opened books, most recent first."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return ()
            rows = connection.execute(
                """
                SELECT b.BookID, b.Title, b.Author, l.Name
                FROM RecentBooks r
                JOIN Books b ON b.BookID = r.BookID
                LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                ORDER BY r.OpenedAt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(BookSummary(*row) for row in rows)

    def list_recent_categories(self, limit: int = 5) -> tuple[str, ...]:
        """Return real, distinct category names from recently-opened books,
        most-recent-book-first - a new read-only JOIN against the existing
        `RecentBooks`/`Categories` tables, no new persistence. A book can
        belong to more than one category; only its first (by MJCN) is used
        here, to keep one book from crowding out other recently-viewed
        categories.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection) or not self._categories_table_exists(
                connection
            ):
                return ()
            rows = connection.execute(
                """
                SELECT c.Name
                FROM RecentBooks r
                JOIN (
                    SELECT BookID, MIN(MJCN) AS FirstMJCN FROM Categories GROUP BY BookID
                ) first_cat ON first_cat.BookID = r.BookID
                JOIN Categories c ON c.BookID = first_cat.BookID AND c.MJCN = first_cat.FirstMJCN
                ORDER BY r.OpenedAt DESC
                """
            ).fetchall()
        seen: list[str] = []
        for (name,) in rows:
            if name and name not in seen:
                seen.append(name)
            if len(seen) >= limit:
                break
        return tuple(seen)

    @staticmethod
    def _categories_table_exists(connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'Categories'"
            ).fetchone()
            is not None
        )

    def last_page_number(self, book_id: int) -> int | None:
        """Return the real last-read page for a book, or None if never opened."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return None
            row = connection.execute(
                "SELECT LastPageNo FROM RecentBooks WHERE BookID = ?", (book_id,)
            ).fetchone()
        return row[0] if row else None

    @staticmethod
    def _table_exists(connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'RecentBooks'"
            ).fetchone()
            is not None
        )
