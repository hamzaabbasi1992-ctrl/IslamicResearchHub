"""Read-only SQLite adapter for full-text search over the master book database."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text
from islamic_research_hub.shared.sql_filters import library_filter_clause

LOGGER = logging.getLogger(__name__)


class BookSearchError(Exception):
    """Raised when the master database cannot be searched."""


class SqliteBookSearchRepository:
    """Query the full-text index built by MasterBookRepository/the migration system.

    Prefers `PagesFTSNormalized` (diacritic/letter-form/cross-keyboard-
    normalized text, see `shared/arabic_text_normalization.py`, added by
    migration 5) so spelling variants like "علی"/"علي" and keyboard
    variants like "کتاب"/"كتاب" match each other, normalizing the query
    the same way. Falls back to the plain `PagesFTS` index (literal
    matching) for a database that's been imported but not yet migrated,
    or whenever the caller passes `exact=True`. Excerpts are drawn from
    whichever index matched - stored page content itself (and the book
    viewer) is never touched either way.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def search(
        self,
        query: str,
        limit: int,
        library: str | tuple[str, ...] | None = None,
        author: str | None = None,
        category: str | None = None,
        exact: bool = False,
        scope: str = "content",
    ) -> tuple[SearchResult, ...]:
        """Return the top matching pages, ranked by full-text relevance.

        `library` restricts to one library name, or several at once (a
        tuple - the multi-library search scope picker), `author` to one
        exact `Books.Author` value, and `category` to books linked (in
        the per-book `Categories` table) to a category with that exact
        name.
        `exact=True` requires literal spelling and always searches the
        plain `PagesFTS`/`FootnotesFTS` index; the default (`False`)
        prefers the diacritic/letter-form/cross-keyboard-normalized
        index when available, same as before this parameter existed.

        `scope` is `"content"` (main page text, the default - unchanged
        behavior), `"footnotes"` (only `Footnotes`), or `"both"`. `"both"`
        runs each index's query independently (up to `limit` each) and
        concatenates content results before footnote results, capped at
        `limit` - a real, honest choice given FTS5 `bm25` rank scores
        from two different indexes aren't meaningfully comparable to
        merge-and-re-sort, not an attempt at cross-index relevance fusion.
        """
        LOGGER.info(
            "Searching library for: %s (library=%s, author=%s, category=%s, exact=%s, scope=%s)",
            query,
            library,
            author,
            category,
            exact,
            scope,
        )
        try:
            with closing(self._connect_read_only(self._database_path)) as connection:
                connection.row_factory = sqlite3.Row
                results: list[SearchResult] = []
                if scope in ("content", "both"):
                    results.extend(
                        self._search_content(connection, query, limit, library, author, category, exact)
                    )
                if scope in ("footnotes", "both"):
                    remaining = limit - len(results)
                    if remaining > 0:
                        results.extend(
                            self._search_footnotes(
                                connection, query, remaining, library, author, category, exact
                            )
                        )
        except sqlite3.Error as error:
            LOGGER.exception("Unable to search the library: %s", self._database_path)
            raise BookSearchError(
                "The search query could not be run against the master database."
            ) from error

        LOGGER.info("Search complete: %d result(s) found.", len(results))
        return tuple(results)

    def _search_content(
        self,
        connection: sqlite3.Connection,
        query: str,
        limit: int,
        library: str | tuple[str, ...] | None,
        author: str | None,
        category: str | None,
        exact: bool,
    ) -> tuple[SearchResult, ...]:
        """Search main page content via PagesFTS/PagesFTSNormalized."""
        if not exact and self._index_exists(connection, "PagesFTSNormalized"):
            fts_table = "PagesFTSNormalized"
        elif self._index_exists(connection, "Pages_fts"):
            # Compacted/imported databases use Pages_fts (snake_case) as the
            # FTS table name; prefer it over PagesFTS which may exist but be
            # empty (content-backed FTS created by migration 1 but never rebuilt).
            fts_table = "Pages_fts"
        elif self._index_exists(connection, "PagesFTS"):
            fts_table = "PagesFTS"
        else:
            fts_table = "PagesFTS"

        use_normalized_index = fts_table == "PagesFTSNormalized"
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
        sql, parameters = self._apply_filters(sql, parameters, library, author, category)
        sql += " ORDER BY rank LIMIT ?"
        parameters.append(limit)
        rows = connection.execute(sql, parameters).fetchall()
        return tuple(
            SearchResult(
                book_id=row["BookID"],
                title=row["Title"],
                author=row["Author"],
                page_number=row["PageNo"],
                excerpt=row["Excerpt"],
                library=row["Library"],
                source="content",
            )
            for row in rows
        )

    def _search_footnotes(
        self,
        connection: sqlite3.Connection,
        query: str,
        limit: int,
        library: str | tuple[str, ...] | None,
        author: str | None,
        category: str | None,
        exact: bool,
    ) -> tuple[SearchResult, ...]:
        """Search footnote/commentary text via FootnotesFTS/FootnotesFTSNormalized.

        A silent no-op (empty result) on a database that hasn't run
        migration 10 yet - the same graceful-degrade pattern used
        throughout this codebase.
        """
        if not self._index_exists(connection, "FootnotesFTS"):
            return ()
        use_normalized_index = not exact and self._index_exists(
            connection, "FootnotesFTSNormalized"
        )
        fts_table = "FootnotesFTSNormalized" if use_normalized_index else "FootnotesFTS"
        match_query = normalize_search_text(query) if use_normalized_index else query
        sql = f"""
            SELECT
                Books.BookID AS BookID,
                Books.Title AS Title,
                Books.Author AS Author,
                Footnotes.PageNo AS PageNo,
                snippet({fts_table}, 0, '**', '**', ' ... ', 12) AS Excerpt,
                Libraries.Name AS Library
            FROM {fts_table}
            JOIN Footnotes ON Footnotes.rowid = {fts_table}.rowid
            JOIN Books ON Books.BookID = Footnotes.BookID
            LEFT JOIN Libraries ON Libraries.LibraryID = Books.LibraryID
            WHERE {fts_table} MATCH ?
        """
        parameters: list[object] = [match_query]
        sql, parameters = self._apply_filters(sql, parameters, library, author, category)
        sql += " ORDER BY rank LIMIT ?"
        parameters.append(limit)
        rows = connection.execute(sql, parameters).fetchall()
        return tuple(
            SearchResult(
                book_id=row["BookID"],
                title=row["Title"],
                author=row["Author"],
                page_number=row["PageNo"],
                excerpt=row["Excerpt"],
                library=row["Library"],
                source="footnote",
            )
            for row in rows
        )

    @staticmethod
    def _apply_filters(
        sql: str,
        parameters: list[object],
        library: str | tuple[str, ...] | None,
        author: str | None,
        category: str | None,
    ) -> tuple[str, list[object]]:
        """Append the shared library/author/category filter clauses."""
        library_sql, library_params = library_filter_clause("Libraries.Name", library)
        sql += library_sql
        parameters.extend(library_params)
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
        return sql, parameters

    @staticmethod
    def _connect_read_only(database_path: Path) -> sqlite3.Connection:
        """Open the existing master database without write access."""
        if not database_path.is_file():
            raise BookSearchError(f"Master database does not exist: {database_path}")
        return sqlite3.connect(f"{database_path.resolve().as_uri()}?mode=ro", uri=True)

    @staticmethod
    def _index_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        """Return whether a given FTS index table exists (its migration has run).

        Falls back to the plain (non-normalized) index, or to no result
        at all for footnotes, when it hasn't - so search keeps working
        for a database that's been imported but not yet fully migrated,
        a normal, expected state.
        """
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        ).fetchone()
        return row is not None
