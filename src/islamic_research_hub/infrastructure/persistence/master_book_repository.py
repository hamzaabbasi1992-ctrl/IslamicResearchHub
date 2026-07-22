"""Transactional SQLite import adapter for the local master book database."""

import logging
import sqlite3
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Category, Chapter, Page

LOGGER = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]

DEFAULT_LIBRARY_NAME = "Maktaba Jibreel (Mobile)"


class MasterBookRepository:
    """Create and populate the master SQLite database from in-memory books."""

    def import_books(
        self,
        database_path: Path,
        books: tuple[Book, ...],
        sources: tuple[Path, ...],
        library_name: str = DEFAULT_LIBRARY_NAME,
        progress: ProgressCallback | None = None,
    ) -> tuple[int, int, int]:
        """Import books transactionally, returning imported, skipped, failed counts."""
        if len(books) != len(sources):
            raise ValueError("Every extracted book must have one source path.")

        database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(database_path)) as connection:
            fts_index_already_existed = self._pages_fts_exists(connection)
            self._create_schema(connection)
            self._ensure_library_id_column(connection)
            self._backfill_legacy_library(connection)
            if not fts_index_already_existed:
                self._backfill_pages_fts(connection)
            library_id = self._get_or_create_library_id(connection, library_name)
            imported_count = 0
            skipped_count = 0
            failed_count = 0
            total_books = len(books)
            if progress is not None:
                progress(0, total_books)

            for completed_count, (book, source) in enumerate(
                zip(books, sources, strict=True),
                start=1,
            ):
                try:
                    if self._is_imported(connection, source):
                        skipped_count += 1
                    else:
                        self._import_book(connection, source, book, library_id)
                        imported_count += 1
                except sqlite3.Error:
                    failed_count += 1
                    connection.rollback()
                    LOGGER.exception("Failed to import MJBZ book: %s", source)
                finally:
                    if progress is not None:
                        progress(completed_count, total_books)

        return imported_count, skipped_count, failed_count

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        """Create the requested master schema when it does not yet exist."""
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS Libraries (
                LibraryID INTEGER PRIMARY KEY,
                Name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS Books (
                BookID INTEGER PRIMARY KEY,
                LibraryID INTEGER REFERENCES Libraries(LibraryID),
                Source TEXT NOT NULL UNIQUE,
                SourceBookID TEXT,
                Title TEXT,
                Author TEXT,
                Publisher TEXT,
                Language TEXT,
                Category TEXT,
                PageCount INTEGER NOT NULL,
                ChapterCount INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS Categories (
                BookID INTEGER NOT NULL REFERENCES Books(BookID),
                MJCN INTEGER,
                ParentMJCN INTEGER,
                Name TEXT,
                SortKey INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_categories_book_id ON Categories(BookID);

            CREATE TABLE IF NOT EXISTS Chapters (
                BookID INTEGER NOT NULL REFERENCES Books(BookID),
                ChapterID INTEGER,
                ParentChapterID INTEGER,
                Title TEXT,
                PageNo INTEGER,
                SortKey INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_chapters_book_id ON Chapters(BookID);

            CREATE TABLE IF NOT EXISTS Pages (
                BookID INTEGER NOT NULL REFERENCES Books(BookID),
                PageNo INTEGER,
                Content TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_pages_book_id ON Pages(BookID);

            CREATE VIRTUAL TABLE IF NOT EXISTS PagesFTS USING fts5(
                Content,
                content='Pages',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS pages_after_insert AFTER INSERT ON Pages BEGIN
                INSERT INTO PagesFTS(rowid, Content) VALUES (new.rowid, new.Content);
            END;
            """
        )
        connection.commit()

    @staticmethod
    def _pages_fts_exists(connection: sqlite3.Connection) -> bool:
        """Return whether the PagesFTS full-text index has already been created."""
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'PagesFTS'"
        ).fetchone()
        return row is not None

    @staticmethod
    def _backfill_pages_fts(connection: sqlite3.Connection) -> None:
        """Populate the full-text index for pages that predate the PagesFTS table."""
        connection.execute("INSERT INTO PagesFTS(PagesFTS) VALUES ('rebuild')")
        connection.commit()

    @staticmethod
    def _ensure_library_id_column(connection: sqlite3.Connection) -> None:
        """Add the LibraryID column to a Books table created before libraries existed."""
        columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)").fetchall()}
        if "LibraryID" not in columns:
            connection.execute(
                "ALTER TABLE Books ADD COLUMN LibraryID INTEGER REFERENCES Libraries(LibraryID)"
            )
            connection.commit()
        connection.execute("CREATE INDEX IF NOT EXISTS idx_books_library_id ON Books(LibraryID)")
        connection.commit()

    @staticmethod
    def _get_or_create_library_id(connection: sqlite3.Connection, name: str) -> int:
        """Return the id for a library, creating it if it does not yet exist."""
        connection.execute("INSERT OR IGNORE INTO Libraries (Name) VALUES (?)", (name,))
        row = connection.execute(
            "SELECT LibraryID FROM Libraries WHERE Name = ?", (name,)
        ).fetchone()
        connection.commit()
        return row[0]

    @classmethod
    def _backfill_legacy_library(cls, connection: sqlite3.Connection) -> None:
        """Tag books imported before the library concept existed as the mobile library."""
        legacy_library_id = cls._get_or_create_library_id(connection, DEFAULT_LIBRARY_NAME)
        connection.execute(
            "UPDATE Books SET LibraryID = ? WHERE LibraryID IS NULL",
            (legacy_library_id,),
        )
        connection.commit()

    @staticmethod
    def _is_imported(connection: sqlite3.Connection, source: Path) -> bool:
        """Return whether this exact source file has already been imported."""
        row = connection.execute(
            "SELECT 1 FROM Books WHERE Source = ?",
            (str(source),),
        ).fetchone()
        return row is not None

    def _import_book(
        self,
        connection: sqlite3.Connection,
        source: Path,
        book: Book,
        library_id: int,
    ) -> None:
        """Insert one complete book and commit its transaction."""
        with connection:
            cursor = connection.execute(
                """
                INSERT INTO Books (
                    LibraryID, Source, SourceBookID, Title, Author, Publisher,
                    Language, Category, PageCount, ChapterCount
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    library_id,
                    str(source),
                    book.information.get("MJBN"),
                    book.information.get("Name"),
                    book.information.get("ANAME"),
                    book.information.get("PNAME"),
                    book.information.get("Language"),
                    book.information.get("MJCN"),
                    len(book.pages),
                    _count_chapters(book.table_of_contents),
                ),
            )
            book_id = cursor.lastrowid
            self._insert_categories(connection, book_id, book.categories)
            self._insert_chapters(connection, book_id, book.table_of_contents)
            self._insert_pages(connection, book_id, book.pages)

    @staticmethod
    def _insert_categories(
        connection: sqlite3.Connection,
        book_id: int,
        categories: tuple[Category, ...],
    ) -> None:
        """Insert the complete category hierarchy as relational rows."""
        connection.executemany(
            """
            INSERT INTO Categories (BookID, MJCN, ParentMJCN, Name, SortKey)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                (
                    book_id,
                    category.mjcn,
                    category.parent_mjcn,
                    category.name,
                    category.sort_key,
                )
                for category in _flatten_categories(categories)
            ),
        )

    @staticmethod
    def _insert_chapters(
        connection: sqlite3.Connection,
        book_id: int,
        chapters: tuple[Chapter, ...],
    ) -> None:
        """Insert the complete table of contents as relational rows."""
        connection.executemany(
            """
            INSERT INTO Chapters (
                BookID, ChapterID, ParentChapterID, Title, PageNo, SortKey
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    book_id,
                    chapter.title_id,
                    chapter.parent_id,
                    chapter.title,
                    chapter.page_number,
                    chapter.sort_key,
                )
                for chapter in _flatten_chapters(chapters)
            ),
        )

    @staticmethod
    def _insert_pages(
        connection: sqlite3.Connection,
        book_id: int,
        pages: tuple[Page, ...],
    ) -> None:
        """Insert every page, preferring ContentF and falling back to ContentP."""
        connection.executemany(
            "INSERT INTO Pages (BookID, PageNo, Content) VALUES (?, ?, ?)",
            (
                (book_id, page.page_number, _page_content(page))
                for page in pages
            ),
        )


def _flatten_categories(categories: tuple[Category, ...]) -> tuple[Category, ...]:
    """Return each hierarchy node once in depth-first order."""
    rows: list[Category] = []
    for category in categories:
        rows.append(category)
        rows.extend(_flatten_categories(category.children))
    return tuple(rows)


def _flatten_chapters(chapters: tuple[Chapter, ...]) -> tuple[Chapter, ...]:
    """Return each hierarchy node once in depth-first order."""
    rows: list[Chapter] = []
    for chapter in chapters:
        rows.append(chapter)
        rows.extend(_flatten_chapters(chapter.children))
    return tuple(rows)


def _count_chapters(chapters: tuple[Chapter, ...]) -> int:
    """Count every TOC node in a hierarchy."""
    return sum(1 + _count_chapters(chapter.children) for chapter in chapters)


def _page_content(page: Page) -> str | None:
    """Return formatted content when available, otherwise plain content."""
    if page.content_f is not None and page.content_f.strip():
        return page.content_f
    return page.content_p
