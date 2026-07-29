"""Tests for backfilling Books.PublishYear from Shamila Urdu's own source files."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.interfaces.shamila_urdu_publish_year_backfill_cli import (
    build_parser,
    run,
)


def _make_source_db(path: Path, publish_year: str | None) -> None:
    """Create a real, minimal Shamila Urdu source file with the given metadata."""
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS metadata (fieldName TEXT, fieldValue TEXT)")
        connection.execute("DELETE FROM metadata")
        if publish_year is not None:
            connection.execute(
                "INSERT INTO metadata VALUES ('Publish Year', ?)", (publish_year,)
            )
        connection.commit()
    finally:
        connection.close()


def _seed_book(database_path: Path, source: Path, title: str) -> None:
    """Import one real book whose Source points at a real Shamila Urdu file."""
    book = Book(
        information={"Name": title},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", None),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (source,), library_name="Maktaba Shamila Urdu"
    )


def _build_args(database_path: Path):
    return build_parser().parse_args(["--database", str(database_path)])


def test_backfills_a_real_publish_year(tmp_path: Path, capsys) -> None:
    """A book whose source file has a real Publish Year gets it stored."""
    database_path = tmp_path / "books.db"
    source = tmp_path / "book.db"
    _make_source_db(source, publish_year="1998")
    _seed_book(database_path, source, "Book One")

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "1 book(s) need a Publish Year." in captured.out
    assert "Done. 1/1 book(s) got a real Publish Year." in captured.out
    with sqlite3.connect(database_path) as connection:
        year = connection.execute("SELECT PublishYear FROM Books").fetchone()[0]
    assert year == "1998"


def test_leaves_year_null_when_the_source_has_none(tmp_path: Path, capsys) -> None:
    """A book whose source has no Publish Year field stays NULL, not an error."""
    database_path = tmp_path / "books.db"
    source = tmp_path / "book.db"
    _make_source_db(source, publish_year=None)
    _seed_book(database_path, source, "Book One")

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Done. 0/1 book(s) got a real Publish Year." in captured.out


def test_skips_a_book_whose_source_file_no_longer_exists(tmp_path: Path, capsys) -> None:
    """A missing source file (e.g. a session-scoped scratch extraction) is skipped, not fatal."""
    database_path = tmp_path / "books.db"
    missing_source = tmp_path / "gone.db"
    _seed_book(database_path, missing_source, "Book One")

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "source file missing: 1" in captured.out


def test_rerun_skips_books_that_already_have_a_year(tmp_path: Path, capsys) -> None:
    """Resume-safe: a book with a stored year is not re-read on the next run."""
    database_path = tmp_path / "books.db"
    source = tmp_path / "book.db"
    _make_source_db(source, publish_year="1998")
    _seed_book(database_path, source, "Book One")
    run(_build_args(database_path))
    capsys.readouterr()

    _make_source_db(source, publish_year="2005")
    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 book(s) need a Publish Year." in captured.out
    with sqlite3.connect(database_path) as connection:
        year = connection.execute("SELECT PublishYear FROM Books").fetchone()[0]
    assert year == "1998"


def test_only_processes_the_requested_library(tmp_path: Path, capsys) -> None:
    """A book in a different library is left alone."""
    database_path = tmp_path / "books.db"
    source = tmp_path / "book.mjbz"
    source.touch()
    book = Book(
        information={"Name": "Jibreel Book"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", None),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (source,), library_name="Maktaba Jibreel (Desktop)"
    )

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 book(s) need a Publish Year." in captured.out
