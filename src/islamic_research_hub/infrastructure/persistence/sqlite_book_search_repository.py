"""Read-only SQLite adapter for full-text search over the master book database."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text

LOGGER = logging.getLogger(__name__)


class BookSearchError(Exception):
    """Raised when the master database cannot be searched."""


class SqliteBookSearchRepository:
    """Query the full-text index built by MasterBookRepository/the migration system.

    Prefers `PagesFTSNormalized` (diacritic/letter-form-normalized text, see
    `shared/arabic_text_normalization.py`, added by migration 5) so spelling
    variants like "علی" and "علي" match each other, normalizing the query the
    same way. Falls back to the plain `PagesFTS` index (literal matching) for
    a database that's been imported but not yet migrated. Excerpts are drawn
    from whichever index matched - stored page content itself (and the book
    viewer) is never touched either way.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def search(
        self,
        query: str,
        limit: int,
        library: str | None = None,
        author: str | None = None,
        category: str | None = None,
    ) -> tuple[SearchResult, ...]:
        """Return the top matching pages, ranked by full-text relevance.

        `library` restricts to one library name, `author` to one exact
        `Books.Author` value, and `category` to books linked (in the
        per-book `Categories` table) to a category with that exact name.
        """
        LOGGER.info(
            "Searching library for: %s (library=%s, author=%s, category=%s)",
            query,
            library,
            author,
            category,
        )
        try:
            with closing(self._connect_read_only(self._database_path)) as connection:
                connection.row_factory = sqlite3.Row
                use_normalized_index = self._normalized_index_exists(connection)
                fts_table = "PagesFTSNormalized" if use_normalized_index else "PagesFTS"
                match_query = normalize_search_text(query) if use_normalized_index else query
                sql = f"""
                    SELECT
                        Books.BookID AS BookID,
                        Books.Title AS Title,
                        Books.Author AS Author,
                        Pages.PageNo AS PageNo,
                        snippet({fts_table}, 0, '**', '**', ' ... ', 12) AS Excerpt,
                        Libraries.Name AS Library
                    FROM {fts_table}
                    JOIN Pages ON Pages.rowid = {fts_table}.rowid
                    JOIN Books ON Books.BookID = Pages.BookID
                    LEFT JOIN Libraries ON Libraries.LibraryID = Books.LibraryID
                    WHERE {fts_table} MATCH ?
                """
                parameters: list[object] = [match_query]
                if library is not None:
                    sql += " AND Libraries.Name = ?"
                    parameters.append(library)
                if author is not None:
                    sql += " AND Books.Author = ?"
                    parameters.append(author)
                if category is not None:
                    sql += """
                        AND EXISTS (
                            SELECT 1 FROM Categories
                            WHERE Categories.BookID = Books.BookID
                            AND Categories.Name = ?
                        )
                    """
                    parameters.append(category)
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

    @staticmethod
    def _normalized_index_exists(connection: sqlite3.Connection) -> bool:
        """Return whether PagesFTSNormalized exists (migration 5 has run).

        Falls back to the plain PagesFTS index when it hasn't, so search
        keeps working for a database that's been imported but not yet
        migrated - a normal, expected state.
        """
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'PagesFTSNormalized'"
        ).fetchone()
        return row is not None
