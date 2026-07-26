"""Read-only SQLite adapter supporting the web browsing/reading interface."""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book import Page
from islamic_research_hub.domain.models.book_metadata import BookMetadata


class BookBrowserRepository:
    """Read-only queries for listing libraries and reading one book's pages."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_libraries(self) -> tuple[str, ...]:
        """Return every library name, alphabetically."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute("SELECT Name FROM Libraries ORDER BY Name").fetchall()
        return tuple(row[0] for row in rows)

    def list_libraries_with_counts(self) -> tuple[tuple[str, int], ...]:
        """Return every library name paired with its real book count, alphabetically."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                """
                SELECT l.Name, COUNT(b.BookID)
                FROM Libraries l
                LEFT JOIN Books b ON b.LibraryID = l.LibraryID
                GROUP BY l.LibraryID
                ORDER BY l.Name
                """
            ).fetchall()
        return tuple((row[0], row[1]) for row in rows)

    def get_book_source(self, book_id: int) -> tuple[str, str | None] | None:
        """Return (source path, library name) for one book, or None if missing."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            row = connection.execute(
                """
                SELECT b.Source, l.Name FROM Books b
                LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE b.BookID = ?
                """,
                (book_id,),
            ).fetchone()
        return (row[0], row[1]) if row else None

    def get_book_detail(
        self, book_id: int
    ) -> tuple[str | None, str | None, tuple[Page, ...]] | None:
        """Return (title, author, pages in page order) for one book, or None if missing."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            book_row = connection.execute(
                "SELECT Title, Author FROM Books WHERE BookID = ?", (book_id,)
            ).fetchone()
            if book_row is None:
                return None
            page_rows = connection.execute(
                "SELECT PageNo, Content FROM Pages WHERE BookID = ? ORDER BY PageNo",
                (book_id,),
            ).fetchall()
        pages = tuple(
            Page(
                content_id=index,
                page_number=row["PageNo"],
                content_f=row["Content"],
                content_p=None,
            )
            for index, row in enumerate(page_rows, start=1)
        )
        return (book_row["Title"], book_row["Author"], pages)

    def get_book_metadata(self, book_id: int) -> BookMetadata | None:
        """Return one book's full catalog metadata, or None if it doesn't exist.

        `Series`/`Books.SeriesID`/`Books.VolumeNumber` only exist on a
        database that has run migration 4 - a freshly imported database
        (before any migration) won't have them yet, so this falls back to
        a query without them rather than raising.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            connection.row_factory = sqlite3.Row
            if self._has_series_support(connection):
                row = connection.execute(
                    """
                    SELECT
                        b.BookID, b.Title, b.Author, b.Publisher, b.Language, b.Category,
                        l.Name AS Library, b.PageCount, b.ChapterCount,
                        s.Title AS SeriesTitle, b.VolumeNumber
                    FROM Books b
                    LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                    LEFT JOIN Series s ON s.SeriesID = b.SeriesID
                    WHERE b.BookID = ?
                    """,
                    (book_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT
                        b.BookID, b.Title, b.Author, b.Publisher, b.Language, b.Category,
                        l.Name AS Library, b.PageCount, b.ChapterCount
                    FROM Books b
                    LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                    WHERE b.BookID = ?
                    """,
                    (book_id,),
                ).fetchone()
        if row is None:
            return None
        row_keys = row.keys()
        return BookMetadata(
            book_id=row["BookID"],
            title=row["Title"],
            author=row["Author"],
            publisher=row["Publisher"],
            language=row["Language"],
            category=row["Category"],
            library=row["Library"],
            page_count=row["PageCount"],
            chapter_count=row["ChapterCount"],
            series_title=row["SeriesTitle"] if "SeriesTitle" in row_keys else None,
            volume_number=row["VolumeNumber"] if "VolumeNumber" in row_keys else None,
        )

    @staticmethod
    def _has_series_support(connection: sqlite3.Connection) -> bool:
        """Return whether the Series table and Books.SeriesID column exist."""
        series_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'Series'"
        ).fetchone()
        if series_table is None:
            return False
        columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)")}
        return "SeriesID" in columns
