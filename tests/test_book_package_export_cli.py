"""End-to-end tests for the single-book package export command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Chapter, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.interfaces.book_package_export_cli import (
    MOBILE_ROOM_SCHEMA_VERSION,
    main,
)


def _seed_database(database_path: Path) -> int:
    book = Book(
        information={
            "Name": "Book of Fiqh",
            "ANAME": "Author One",
            "Language": "Arabic",
            "PNAME": "Publisher One",
        },
        categories=(),
        table_of_contents=(
            Chapter(title_id=1, title="Chapter One", page_number=1, parent_id=None, sort_key=1),
        ),
        pages=(
            Page(1, 1, "First page content", None),
            Page(2, 2, "Second page content", None),
        ),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "a.mjbz",)
    )
    return 1


def test_exports_a_real_book_with_pages_and_chapters(tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "book_1.db"
    book_id = _seed_database(database_path)

    exit_code = main(
        [
            "--database",
            str(database_path),
            "--book-id",
            str(book_id),
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Book of Fiqh" in captured.out
    assert "Pages: 2" in captured.out
    assert output_path.is_file()

    with sqlite3.connect(output_path) as connection:
        book_row = connection.execute("SELECT Title, Author, Language FROM Books").fetchone()
        assert book_row == ("Book of Fiqh", "Author One", "Arabic")
        pages = connection.execute(
            "SELECT PageNo, Content FROM Pages ORDER BY PageNo"
        ).fetchall()
        assert pages == [(1, "First page content"), (2, "Second page content")]
        chapters = connection.execute("SELECT Title, PageNo FROM Chapters").fetchall()
        assert chapters == [("Chapter One", 1)]
        library_row = connection.execute("SELECT Name FROM Libraries").fetchone()
        assert library_row is not None


def test_pages_and_chapters_get_a_real_primary_key(tmp_path: Path) -> None:
    """Real fix: Room (the Android companion app's SQLite ORM) requires
    a declared primary key on every table it opens - Pages/Chapters
    originally had none. PageID is a real, synthesized 1-based row
    number (Pages has no natural per-row ID in the source schema);
    ChapterID reuses the source database's own real chapter ID."""
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "book_1.db"
    _seed_database(database_path)

    exit_code = main(
        ["--database", str(database_path), "--book-id", "1", "--output", str(output_path)]
    )

    assert exit_code == 0
    with sqlite3.connect(output_path) as connection:
        page_ids = [
            row[0] for row in connection.execute("SELECT PageID FROM Pages ORDER BY PageNo")
        ]
        assert page_ids == [1, 2]
        chapter_ids = [row[0] for row in connection.execute("SELECT ChapterID FROM Chapters")]
        assert chapter_ids == [1]


def test_fails_cleanly_when_database_is_missing(tmp_path: Path) -> None:
    exit_code = main(
        [
            "--database",
            str(tmp_path / "missing.db"),
            "--book-id",
            "1",
        ]
    )

    assert exit_code == 1


def test_fails_cleanly_when_book_id_does_not_exist(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    exit_code = main(
        ["--database", str(database_path), "--book-id", "999"]
    )

    assert exit_code == 1


def test_default_output_path_uses_book_id(tmp_path: Path, monkeypatch) -> None:
    """Without --output, the file lands at data/exports/book_<id>.db,
    relative to the current working directory."""
    database_path = tmp_path / "books.db"
    book_id = _seed_database(database_path)
    monkeypatch.chdir(tmp_path)

    exit_code = main(["--database", str(database_path), "--book-id", str(book_id)])

    assert exit_code == 0
    assert (tmp_path / "data" / "exports" / f"book_{book_id}.db").is_file()


def test_a_book_with_no_chapters_exports_cleanly(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "book.db"
    book = Book(
        information={"Name": "No TOC Book", "ANAME": "Author"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Only page", None),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "a.mjbz",)
    )

    exit_code = main(
        ["--database", str(database_path), "--book-id", "1", "--output", str(output_path)]
    )

    assert exit_code == 0
    with sqlite3.connect(output_path) as connection:
        chapter_count = connection.execute("SELECT COUNT(*) FROM Chapters").fetchone()[0]
    assert chapter_count == 0


def test_output_file_carries_the_room_expected_schema_version(tmp_path: Path) -> None:
    """Real regression guard for the confirmed Room prepackaged-database
    crash (2026-08-12) - see the identical test in test_catalog_export_cli.py."""
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "book_1.db"
    book_id = _seed_database(database_path)

    main(
        [
            "--database", str(database_path),
            "--book-id", str(book_id),
            "--output", str(output_path),
        ]
    )

    with sqlite3.connect(output_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert version == MOBILE_ROOM_SCHEMA_VERSION
