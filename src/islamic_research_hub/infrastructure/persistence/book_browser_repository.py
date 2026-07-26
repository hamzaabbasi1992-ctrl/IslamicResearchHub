"""Read-only SQLite adapter supporting the web browsing/reading interface."""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book import Page
from islamic_research_hub.domain.models.book_metadata import BookMetadata
from islamic_research_hub.domain.models.category_node import CategoryNode
from islamic_research_hub.domain.models.header_stats import HeaderStats


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
