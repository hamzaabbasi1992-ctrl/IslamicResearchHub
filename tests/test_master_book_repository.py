"""Tests for transactional import into the master SQLite database."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Category, Chapter, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


def test_repository_imports_and_skips_an_existing_source(tmp_path: Path) -> None:
    """A source is imported once and skipped on the next build."""
    source = tmp_path / "book.mjbz"
    source.touch()
    book = Book(
        information={
            "MJBN": "35",
            "Name": "Book title",
            "ANAME": "Author",
            "PNAME": "Publisher",
            "Language": "ur",
            "MJCN": "1",
        },
        categories=(Category(1, "Category", None, 1),),
        table_of_contents=(Chapter(1, "Chapter", 1, None, 1),),
        pages=(Page(1, 1, "Formatted", "Plain"),),
    )
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()

    assert repository.import_books(database_path, (book,), (source,)) == (1, 0, 0)
    assert repository.import_books(database_path, (book,), (source,)) == (0, 1, 0)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM Books").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM Categories").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM Chapters").fetchone()[0] == 1
        assert connection.execute("SELECT Content FROM Pages").fetchone()[0] == "Formatted"


def test_repository_indexes_book_id_lookups(tmp_path: Path) -> None:
    """BookID indexes exist on the child tables to keep lookups fast."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    source = tmp_path / "book.mjbz"
    source.touch()
    book = Book(
        information={"Name": "Book title"},
        categories=(),
        table_of_contents=(),
        pages=(),
    )

    repository.import_books(database_path, (book,), (source,))

    with sqlite3.connect(database_path) as connection:
        indexed_tables = {
            row[0]
            for row in connection.execute(
                "SELECT tbl_name FROM sqlite_master WHERE type = 'index' "
                "AND name IN ("
                "'idx_categories_book_id', 'idx_chapters_book_id', 'idx_pages_book_id'"
                ")"
            ).fetchall()
        }
    assert indexed_tables == {"Categories", "Chapters", "Pages"}


def test_repository_keeps_pages_full_text_index_in_sync(tmp_path: Path) -> None:
    """Imported page content becomes searchable through the PagesFTS index."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    source = tmp_path / "book.mjbz"
    source.touch()
    book = Book(
        information={"Name": "Book title"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "A distinctive phrase about jurisprudence", "Plain"),),
    )

    repository.import_books(database_path, (book,), (source,))

    with sqlite3.connect(database_path) as connection:
        match = connection.execute(
            "SELECT Content FROM PagesFTS WHERE PagesFTS MATCH 'jurisprudence'"
        ).fetchone()
    assert match == ("A distinctive phrase about jurisprudence",)


def test_repository_backfills_full_text_index_for_pre_existing_pages(
    tmp_path: Path,
) -> None:
    """Pages inserted before the FTS table existed are indexed on the next run."""
    database_path = tmp_path / "books.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Books (
                BookID INTEGER PRIMARY KEY, Source TEXT NOT NULL UNIQUE,
                SourceBookID TEXT, Title TEXT, Author TEXT, Publisher TEXT,
                Language TEXT, Category TEXT, PageCount INTEGER NOT NULL,
                ChapterCount INTEGER NOT NULL
            );
            CREATE TABLE Pages (BookID INTEGER NOT NULL, PageNo INTEGER, Content TEXT);
            """
        )
        connection.execute(
            "INSERT INTO Books (Source, PageCount, ChapterCount) VALUES ('legacy', 1, 0)"
        )
        connection.execute(
            "INSERT INTO Pages (BookID, PageNo, Content) VALUES (1, 1, 'Legacy content')"
        )
        connection.commit()

    repository = MasterBookRepository()
    source = tmp_path / "new.mjbz"
    source.touch()
    book = Book(information={}, categories=(), table_of_contents=(), pages=())
    repository.import_books(database_path, (book,), (source,))

    with sqlite3.connect(database_path) as connection:
        match = connection.execute(
            "SELECT Content FROM PagesFTS WHERE PagesFTS MATCH 'Legacy'"
        ).fetchone()
    assert match == ("Legacy content",)


def test_repository_tags_books_with_their_library(tmp_path: Path) -> None:
    """Books imported under different library names get distinct LibraryID rows."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    mobile_book = Book(information={"Name": "Mobile Book"}, categories=(), table_of_contents=(), pages=())
    desktop_book = Book(information={"Name": "Desktop Book"}, categories=(), table_of_contents=(), pages=())

    repository.import_books(
        database_path, (mobile_book,), (tmp_path / "mobile.mjbz",), library_name="Maktaba Jibreel (Mobile)"
    )
    repository.import_books(
        database_path, (desktop_book,), (tmp_path / "desktop.mjbx",), library_name="Maktaba Jibreel (Desktop)"
    )

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            """
            SELECT Books.Title, Libraries.Name FROM Books
            JOIN Libraries ON Libraries.LibraryID = Books.LibraryID
            ORDER BY Books.Title
            """
        ).fetchall()
    assert rows == [
        ("Desktop Book", "Maktaba Jibreel (Desktop)"),
        ("Mobile Book", "Maktaba Jibreel (Mobile)"),
    ]


def test_repository_backfills_legacy_books_into_the_default_library(tmp_path: Path) -> None:
    """Books imported before the library concept existed default to the mobile library."""
    database_path = tmp_path / "books.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Books (
                BookID INTEGER PRIMARY KEY, Source TEXT NOT NULL UNIQUE,
                SourceBookID TEXT, Title TEXT, Author TEXT, Publisher TEXT,
                Language TEXT, Category TEXT, PageCount INTEGER NOT NULL,
                ChapterCount INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO Books (Source, Title, PageCount, ChapterCount) "
            "VALUES ('legacy.mjbz', 'Legacy Book', 0, 0)"
        )
        connection.commit()

    repository = MasterBookRepository()
    new_book = Book(information={"Name": "New Book"}, categories=(), table_of_contents=(), pages=())
    repository.import_books(database_path, (new_book,), (tmp_path / "new.mjbz",))

    with sqlite3.connect(database_path) as connection:
        library_name = connection.execute(
            """
            SELECT Libraries.Name FROM Books
            JOIN Libraries ON Libraries.LibraryID = Books.LibraryID
            WHERE Books.Title = 'Legacy Book'
            """
        ).fetchone()
    assert library_name == ("Maktaba Jibreel (Mobile)",)
