"""Read/write SQLite adapter for a real per-book personal rating (Phase 9)."""

import sqlite3
from contextlib import closing
from pathlib import Path

MIN_RATING = 1
MAX_RATING = 5


class BookRatingRepository:
    """Set/clear/list real personal ratings against the `BookRatings` table."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def set_rating(self, book_id: int, rating: int) -> None:
        """Record a real rating (1-5), replacing any existing one for this book."""
        if not MIN_RATING <= rating <= MAX_RATING:
            raise ValueError(f"Rating must be between {MIN_RATING} and {MAX_RATING}: {rating}")
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "INSERT INTO BookRatings (BookID, Rating, RatedAt) "
                    "VALUES (?, ?, datetime('now')) "
                    "ON CONFLICT(BookID) DO UPDATE SET Rating = excluded.Rating, "
                    "RatedAt = excluded.RatedAt",
                    (book_id, rating),
                )

    def clear_rating(self, book_id: int) -> None:
        """Remove a book's rating, if it has one."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute("DELETE FROM BookRatings WHERE BookID = ?", (book_id,))

    def get_rating(self, book_id: int) -> int | None:
        """Return one book's real rating, or None if it hasn't been rated."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return None
            row = connection.execute(
                "SELECT Rating FROM BookRatings WHERE BookID = ?", (book_id,)
            ).fetchone()
        return row[0] if row else None

    @staticmethod
    def _table_exists(connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'BookRatings'"
            ).fetchone()
            is not None
        )
