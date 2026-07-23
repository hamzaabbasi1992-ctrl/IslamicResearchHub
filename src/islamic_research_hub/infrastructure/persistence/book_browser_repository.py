"""Read-only SQLite adapter supporting the web browsing/reading interface."""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book import Page


class BookBrowserRepository:
    """Read-only queries for listing libraries and reading one book's pages."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def list_libraries(self) -> tuple[str, ...]:
        """Return every library name, alphabetically."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute("SELECT Name FROM Libraries ORDER BY Name").fetchall()
        return tuple(row[0] for row in rows)

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
