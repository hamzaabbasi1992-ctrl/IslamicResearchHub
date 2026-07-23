"""Read-only SQLite adapter for full-text search over the master book database."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.search_result import SearchResult

LOGGER = logging.getLogger(__name__)


class BookSearchError(Exception):
    """Raised when the master database cannot be searched."""


class SqliteBookSearchRepository:
    """Query the PagesFTS full-text index built by MasterBookRepository."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def search(
        self, query: str, limit: int, library: str | None = None
    ) -> tuple[SearchResult, ...]:
        """Return the top matching pages, ranked by full-text relevance.

        When `library` is given, results are restricted to that library name.
        """
        LOGGER.info("Searching library for: %s (library filter: %s)", query, library)
        try:
            with closing(self._connect_read_only(self._database_path)) as connection:
                connection.row_factory = sqlite3.Row
                sql = """
                    SELECT
                        Books.BookID AS BookID,
                        Books.Title AS Title,
                        Books.Author AS Author,
                        Pages.PageNo AS PageNo,
                        snippet(PagesFTS, 0, '**', '**', ' ... ', 12) AS Excerpt,
                        Libraries.Name AS Library
                    FROM PagesFTS
                    JOIN Pages ON Pages.rowid = PagesFTS.rowid
                    JOIN Books ON Books.BookID = Pages.BookID
                    LEFT JOIN Libraries ON Libraries.LibraryID = Books.LibraryID
                    WHERE PagesFTS MATCH ?
                """
                parameters: list[object] = [query]
                if library is not None:
                    sql += " AND Libraries.Name = ?"
                    parameters.append(library)
                sql += " ORDER BY rank LIMIT ?"
                parameters.append(limit)
                rows = connection.execute(sql, parameters).fetchall()
        except sqlite3.Error as error:
            LOGGER.exception("Unable to search the library: %s", self._database_path)
            raise BookSearchError(
                "The search query could not be run against the master database."
            ) from error

        results = tuple(
            SearchResult(
                book_id=row["BookID"],
                title=row["Title"],
                author=row["Author"],
                page_number=row["PageNo"],
                excerpt=row["Excerpt"],
                library=row["Library"],
            )
            for row in rows
        )
        LOGGER.info("Search complete: %d result(s) found.", len(results))
        return results

    @staticmethod
    def _connect_read_only(database_path: Path) -> sqlite3.Connection:
        """Open the existing master database without write access."""
        if not database_path.is_file():
            raise BookSearchError(f"Master database does not exist: {database_path}")
        return sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)
