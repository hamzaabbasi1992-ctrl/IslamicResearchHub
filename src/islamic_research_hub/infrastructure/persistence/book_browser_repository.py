"""Read-only SQLite adapter supporting the web browsing/reading interface."""

import logging
import sqlite3
from collections.abc import Iterable
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book import Chapter, Page
from islamic_research_hub.domain.models.book_metadata import BookMetadata
from islamic_research_hub.domain.models.book_summary import BookSummary
from islamic_research_hub.domain.models.category_node import CategoryNode
from islamic_research_hub.domain.models.header_stats import HeaderStats
from islamic_research_hub.shared.arabic_text_normalization import (
    build_sql_normalize_expression,
    normalize_search_text,
)

MAX_BROWSE_RESULTS = 200
"""Cap on books returned per browse call, so a large library/category stays usable."""

_MAX_IDS_PER_QUERY = 500
"""Real SQLite builds cap bound parameters well below what a large
candidate table can produce (confirmed: 44,310 distinct book ids in one
`list_books_by_ids()` call raised `sqlite3.OperationalError: too many
SQL variables`) - 500 stays comfortably under any real SQLite build's
limit (900-32766 depending on build) while keeping each batch a real,
sizable query, not one-row-at-a-time."""

LOGGER = logging.getLogger(__name__)


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

    def list_books_in_category(self, category_name: str) -> tuple[BookSummary, ...]:
        """Return real books whose per-book Categories entry matches this exact name."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT b.BookID, b.Title, b.Author, l.Name
                FROM Books b
                JOIN Categories c ON c.BookID = b.BookID
                LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE c.Name = ?
                ORDER BY b.Title
                LIMIT ?
                """,
                (category_name, MAX_BROWSE_RESULTS),
            ).fetchall()
        return tuple(BookSummary(*row) for row in rows)

    def list_books_by_author(self, author_name: str) -> tuple[BookSummary, ...]:
        """Return real books by this exact author name."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                """
                SELECT b.BookID, b.Title, b.Author, l.Name
                FROM Books b
                LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE b.Author = ?
                ORDER BY b.Title
                LIMIT ?
                """,
                (author_name, MAX_BROWSE_RESULTS),
            ).fetchall()
        return tuple(BookSummary(*row) for row in rows)

    def list_books_in_library(self, library_name: str) -> tuple[BookSummary, ...]:
        """Return real books in this exact library."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                """
                SELECT b.BookID, b.Title, b.Author, l.Name
                FROM Books b
                JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE l.Name = ?
                ORDER BY b.Title
                LIMIT ?
                """,
                (library_name, MAX_BROWSE_RESULTS),
            ).fetchall()
        return tuple(BookSummary(*row) for row in rows)

    def search_by_title(
        self,
        query: str,
        limit: int = 30,
        library: str | None = None,
        author: str | None = None,
        category: str | None = None,
        exact: bool = False,
    ) -> tuple[BookSummary, ...]:
        """Return real books matching this query by title/author, ranked by
        real full-text relevance (bm25) via `BooksFTS`/`BooksFTSNormalized`
        (migration 15) - previously a plain `LIKE` scan in fixed
        alphabetical order, the weakest of this project's independent
        search indexes.

        Uses the same diacritic/letter-form/cross-keyboard normalization
        page-content search already applies (e.g. Arabic yeh "ي" vs Urdu
        yeh "ی", Arabic kaf "ك" vs Urdu keheh "ک") so a title search is
        just as tolerant of real spelling variation, typed in whichever
        script the book's own title is actually in. `exact=True` requires
        literal spelling and always uses the plain `BooksFTS` index.
        `library`/`author`/`category` are the same exact-match filters
        content search uses.

        Real, honest behavior change from the old substring scan: matching
        is now whole-word/phrase (the same FTS5 tokenizer content search
        already uses), not an arbitrary substring - "Bar" no longer
        matches "Bari" the way `LIKE '%...%'` did, but ranking is now real
        relevance instead of a fixed alphabetical order, and a query like
        a quoted "exact phrase" or `AND`/`OR`/`NOT` now works here too,
        consistent with content search. Falls back to the old `LIKE` scan
        on a database that's been imported but not yet migrated.
        """
        query = query.strip()
        if not query:
            return ()

        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection, "BooksFTS"):
                return self._search_by_title_like(
                    connection, query, limit, library, author, category, exact
                )

            use_normalized_index = not exact and self._table_exists(
                connection, "BooksFTSNormalized"
            )
            fts_table = "BooksFTSNormalized" if use_normalized_index else "BooksFTS"
            match_query = normalize_search_text(query) if use_normalized_index else query

            conditions = [f"{fts_table} MATCH ?"]
            parameters: list[object] = [match_query]
            if library is not None:
                conditions.append("l.Name = ?")
                parameters.append(library)
            if author is not None:
                conditions.append("b.Author = ?")
                parameters.append(author)
            if category is not None:
                conditions.append(
                    "EXISTS (SELECT 1 FROM Categories c WHERE c.BookID = b.BookID AND c.Name = ?)"
                )
                parameters.append(category)
            parameters.append(limit)

            # Real bug found via voice search's own end-to-end verification:
            # this query passes `query` straight into FTS5's MATCH operator,
            # which has its own query-expression syntax (deliberately, so a
            # typed `AND`/`OR`/`NOT` or a quoted "exact phrase" works here -
            # see this method's docstring) - but that means a query
            # containing *unescaped* FTS5-special punctuation (a period,
            # comma, colon, apostrophe, parenthesis...) raises a raw
            # `sqlite3.OperationalError`, uncaught here or by any caller
            # (unlike content search, which already wraps this same failure
            # mode as `BookSearchError`). Confirmed directly: a plain typed
            # query like "hadith." or "hadith's prayer" already crashed this
            # method before this fix - not something voice search
            # introduced, but voice search's real transcripts (Whisper
            # reliably adds terminal punctuation) hit it on nearly every
            # query, which is how this was found. A malformed query simply
            # finding no title matches (like any other no-match query)
            # is the correct degrade-gracefully behavior, matching content
            # search's own precedent.
            try:
                rows = connection.execute(
                    f"""
                    SELECT b.BookID, b.Title, b.Author, l.Name
                    FROM {fts_table}
                    JOIN Books b ON b.BookID = {fts_table}.rowid
                    LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                    WHERE {" AND ".join(conditions)}
                    ORDER BY rank
                    LIMIT ?
                    """,
                    parameters,
                ).fetchall()
            except sqlite3.OperationalError:
                LOGGER.warning("Title search query could not be parsed as FTS5 syntax: %r", query)
                return ()
        return tuple(BookSummary(*row) for row in rows)

    @staticmethod
    def _search_by_title_like(
        connection: sqlite3.Connection,
        query: str,
        limit: int,
        library: str | None,
        author: str | None,
        category: str | None,
        exact: bool,
    ) -> tuple[BookSummary, ...]:
        """Substring fallback for a database that hasn't run migration 15 yet."""
        if exact:
            title_match_expression = "b.Title"
            match_value = query
        else:
            title_match_expression = build_sql_normalize_expression("b.Title")
            match_value = normalize_search_text(query)

        conditions = [f"b.Title IS NOT NULL AND {title_match_expression} LIKE ?"]
        parameters: list[object] = [f"%{match_value}%"]
        if library is not None:
            conditions.append("l.Name = ?")
            parameters.append(library)
        if author is not None:
            conditions.append("b.Author = ?")
            parameters.append(author)
        if category is not None:
            conditions.append(
                "EXISTS (SELECT 1 FROM Categories c WHERE c.BookID = b.BookID AND c.Name = ?)"
            )
            parameters.append(category)
        parameters.append(limit)

        rows = connection.execute(
            f"""
            SELECT b.BookID, b.Title, b.Author, l.Name
            FROM Books b
            LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
            WHERE {" AND ".join(conditions)}
            ORDER BY b.Title
            LIMIT ?
            """,
            parameters,
        ).fetchall()
        return tuple(BookSummary(*row) for row in rows)

    def get_volume_siblings(self, book_id: int) -> tuple[BookSummary, ...]:
        """Return every other real book that's a volume of the same work as
        `book_id`, ordered by volume number.

        Uses `Series`/`Books.VolumeNumber` (migration 4) - a `Books` row
        already *is* one physical volume, so this reads that existing
        relationship rather than adding a second `Volumes` table (which
        would just create two sources of truth for the same fact). Only
        2,501 of 15,162 titles carry a parseable volume suffix
        (`_parse_volume_title`'s own docstring), so a book with no
        detected series membership honestly returns an empty tuple, not
        an error.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection, "Series"):
                return ()
            row = connection.execute(
                "SELECT SeriesID FROM Books WHERE BookID = ?", (book_id,)
            ).fetchone()
            if row is None or row[0] is None:
                return ()
            series_id = row[0]
            rows = connection.execute(
                """
                SELECT b.BookID, b.Title, b.Author, l.Name
                FROM Books b
                LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE b.SeriesID = ? AND b.BookID != ?
                ORDER BY b.VolumeNumber
                """,
                (series_id, book_id),
            ).fetchall()
        return tuple(BookSummary(*row) for row in rows)

    def list_books_by_ids(self, book_ids: tuple[int, ...]) -> dict[int, BookSummary]:
        """Return real book summaries (title/author/library) for a batch of
        book IDs, keyed by BookID.

        The efficient alternative to calling `get_book_source()`/
        `get_book_detail()` once per book in a loop - `get_book_detail()`
        in particular fetches a book's *entire* page content, which is
        wasteful when only the title is needed (confirmed as a real
        25-second startup cost in `DuplicateManagerScreen`, which was
        doing exactly that for every duplicate-candidate pair).

        Real crash found running this against the production citation
        graph (44,310 distinct citing books in one call):
        `sqlite3.OperationalError: too many SQL variables` - one `IN (...)`
        query with a placeholder per id blows past SQLite's real bound-
        parameter limit at that scale. Batched in chunks well under any
        real SQLite build's limit instead of one unbounded query.
        """
        if not book_ids:
            return {}
        summaries: dict[int, BookSummary] = {}
        with closing(sqlite3.connect(self._database_path)) as connection:
            for batch in _chunked(book_ids, _MAX_IDS_PER_QUERY):
                placeholders = ", ".join("?" for _ in batch)
                rows = connection.execute(
                    f"""
                    SELECT b.BookID, b.Title, b.Author, l.Name
                    FROM Books b
                    LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                    WHERE b.BookID IN ({placeholders})
                    """,
                    batch,
                ).fetchall()
                summaries.update((row[0], BookSummary(*row)) for row in rows)
        return summaries

    def list_books_by_filters(
        self,
        library: str | None = None,
        author: str | None = None,
        category: str | None = None,
        limit: int = MAX_BROWSE_RESULTS,
    ) -> tuple[BookSummary, ...]:
        """Return real books matching any combination of exact library/author/category filters.

        Unlike `search_by_title`, this takes no query text - it's for
        browsing directly by filter alone (e.g. the Author/Category boxes
        with no search text typed).
        """
        conditions = ["1 = 1"]
        parameters: list[object] = []
        if library is not None:
            conditions.append("l.Name = ?")
            parameters.append(library)
        if author is not None:
            conditions.append("b.Author = ?")
            parameters.append(author)
        if category is not None:
            conditions.append(
                "EXISTS (SELECT 1 FROM Categories c WHERE c.BookID = b.BookID AND c.Name = ?)"
            )
            parameters.append(category)
        parameters.append(limit)

        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                f"""
                SELECT DISTINCT b.BookID, b.Title, b.Author, l.Name
                FROM Books b
                LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE {" AND ".join(conditions)}
                ORDER BY b.Title
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return tuple(BookSummary(*row) for row in rows)

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

    def list_chapters(self, book_id: int) -> tuple[Chapter, ...]:
        """Return one book's real table-of-contents, as a parent/child tree.

        Reads the existing `Chapters` table (populated by every importer
        already, never queried by any UI before now) - real data, no new
        persistence, the same "expose already-imported data" shape as
        this repository's other read methods.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                "SELECT ChapterID, ParentChapterID, Title, PageNo, SortKey "
                "FROM Chapters WHERE BookID = ? ORDER BY SortKey, ChapterID",
                (book_id,),
            ).fetchall()
        flat = tuple(
            Chapter(
                title_id=chapter_id,
                title=title,
                page_number=page_no,
                parent_id=parent_chapter_id,
                sort_key=sort_key,
            )
            for chapter_id, parent_chapter_id, title, page_no, sort_key in rows
        )
        return _build_chapter_tree(flat)

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

    def get_header_stats(self) -> HeaderStats:
        """Return corpus-wide counts for the app header, real on any database.

        Authors/CategoryTaxonomy/Series are each added by their own
        migration (2/3/4), so a database that predates one of them simply
        falls back to a plain count over the always-present raw columns
        instead of erroring - same guard pattern as `get_book_metadata`.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            book_count = connection.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
            library_count = connection.execute("SELECT COUNT(*) FROM Libraries").fetchone()[0]

            if self._table_exists(connection, "Authors"):
                author_count = connection.execute("SELECT COUNT(*) FROM Authors").fetchone()[0]
            else:
                author_count = connection.execute(
                    "SELECT COUNT(DISTINCT TRIM(Author)) FROM Books "
                    "WHERE Author IS NOT NULL AND TRIM(Author) != ''"
                ).fetchone()[0]

            if self._table_exists(connection, "CategoryTaxonomy"):
                category_count = connection.execute(
                    "SELECT COUNT(*) FROM CategoryTaxonomy"
                ).fetchone()[0]
            else:
                category_count = connection.execute(
                    "SELECT COUNT(DISTINCT MJCN) FROM Categories WHERE MJCN IS NOT NULL"
                ).fetchone()[0]

            if self._table_exists(connection, "Series"):
                series_count = connection.execute("SELECT COUNT(*) FROM Series").fetchone()[0]
            else:
                series_count = 0

        return HeaderStats(
            book_count=book_count,
            library_count=library_count,
            author_count=author_count,
            category_count=category_count,
            series_count=series_count,
        )

    def list_authors_with_counts(self) -> tuple[tuple[str, int], ...]:
        """Return every author paired with their real book count, alphabetically.

        Uses the normalized `Authors` table when available (migration 2)
        for a stable per-author identity across spelling variants;
        otherwise groups the raw `Books.Author` text directly.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            if self._table_exists(connection, "Authors"):
                rows = connection.execute(
                    """
                    SELECT a.Name, COUNT(b.BookID)
                    FROM Authors a
                    JOIN Books b ON b.AuthorID = a.AuthorID
                    GROUP BY a.AuthorID
                    ORDER BY a.Name
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT TRIM(Author), COUNT(*)
                    FROM Books
                    WHERE Author IS NOT NULL AND TRIM(Author) != ''
                    GROUP BY TRIM(Author)
                    ORDER BY 1
                    """
                ).fetchall()
        return tuple((row[0], row[1]) for row in rows)

    def get_category_tree(self) -> tuple[CategoryNode, ...]:
        """Return the top-level categories, each with its children, real book counts.

        Uses the normalized `CategoryTaxonomy` table when available
        (migration 3) for cross-library canonical names; otherwise builds
        the tree directly from the per-book `Categories` table (which
        always exists), one node per distinct MJCN.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            if self._table_exists(connection, "CategoryTaxonomy"):
                nodes = connection.execute(
                    """
                    SELECT t.MJCN, t.Name, t.ParentMJCN, COUNT(DISTINCT c.BookID)
                    FROM CategoryTaxonomy t
                    LEFT JOIN Categories c ON c.MJCN = t.MJCN
                    GROUP BY t.MJCN
                    ORDER BY t.Name
                    """
                ).fetchall()
            else:
                nodes = connection.execute(
                    """
                    SELECT MJCN, Name, ParentMJCN, COUNT(DISTINCT BookID)
                    FROM Categories
                    WHERE MJCN IS NOT NULL
                    GROUP BY MJCN
                    ORDER BY Name
                    """
                ).fetchall()
        return _build_category_tree(nodes)

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
        """Return whether a table exists, so older databases degrade gracefully."""
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            is not None
        )

    def _has_series_support(self, connection: sqlite3.Connection) -> bool:
        """Return whether the Series table and Books.SeriesID column exist."""
        if not self._table_exists(connection, "Series"):
            return False
        columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)")}
        return "SeriesID" in columns


def _build_category_tree(
    rows: list[tuple[int, str, int | None, int]],
) -> tuple[CategoryNode, ...]:
    """Assemble flat (mjcn, name, parent_mjcn, count) rows into a real tree.

    A root category's ParentMJCN is `0` in this corpus's data (the MJCN
    sentinel used throughout this project - see e.g. `Category(mjcn=9,
    parent_mjcn=0, ...)` in tests), not `NULL` - both are treated as root.
    """
    children_by_parent: dict[int | None, list[tuple[int, str, int]]] = {}
    for mjcn, name, parent_mjcn, count in rows:
        children_by_parent.setdefault(parent_mjcn or None, []).append((mjcn, name, count))

    def build(parent_mjcn: int | None) -> tuple[CategoryNode, ...]:
        return tuple(
            CategoryNode(
                mjcn=mjcn,
                name=name,
                book_count=count,
                children=build(mjcn),
            )
            for mjcn, name, count in children_by_parent.get(parent_mjcn, ())
        )

    return build(None)


def _build_chapter_tree(flat: tuple[Chapter, ...]) -> tuple[Chapter, ...]:
    """Assemble flat, already-ordered `Chapter` rows (with `parent_id`) into
    a real tree - same shape as `_build_category_tree` above."""
    by_id = {chapter.title_id: chapter for chapter in flat}
    children_by_parent: dict[int | None, list[Chapter]] = {}
    for chapter in flat:
        parent_id = chapter.parent_id if chapter.parent_id in by_id else None
        children_by_parent.setdefault(parent_id, []).append(chapter)

    def build(parent_id: int | None) -> tuple[Chapter, ...]:
        return tuple(
            Chapter(
                title_id=chapter.title_id,
                title=chapter.title,
                page_number=chapter.page_number,
                parent_id=chapter.parent_id,
                sort_key=chapter.sort_key,
                children=build(chapter.title_id),
            )
            for chapter in children_by_parent.get(parent_id, ())
        )

    return build(None)


def _chunked(items: tuple[int, ...], size: int) -> Iterable[tuple[int, ...]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
