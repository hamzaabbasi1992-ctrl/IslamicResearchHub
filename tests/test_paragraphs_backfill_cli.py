"""Tests for backfilling Paragraphs from already-stored Pages.Content."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.interfaces.paragraphs_backfill_cli import build_parser, run


def _build_args(database_path: Path, library: str | None = None):
    arguments = ["--database", str(database_path)]
    if library:
        arguments += ["--library", library]
    return build_parser().parse_args(arguments)


def _migrate(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)


def _paragraph_rows(database_path: Path, book_id: int) -> list[tuple[int, int, int, str]]:
    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            "SELECT PageNo, ParagraphIndex, IsHeading, Content FROM Paragraphs "
            "WHERE BookID = ? ORDER BY PageNo, ParagraphIndex",
            (book_id,),
        ).fetchall()


def test_flat_page_becomes_exactly_one_paragraph(tmp_path: Path, capsys) -> None:
    """A page with no real newlines (the overwhelming majority of the corpus)
    gets exactly one honest paragraph, not a fabricated split."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Flat page text with no structure", "Plain"),),
    )
    MasterBookRepository().import_books(database_path, (book,), (tmp_path / "one.mjbz",))
    _migrate(database_path)

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "1 paragraph(s) written" in captured.out
    rows = _paragraph_rows(database_path, 1)
    assert rows == [(1, 1, 0, "Flat page text with no structure")]


def test_real_newlines_split_into_multiple_paragraphs_with_heading_detection(
    tmp_path: Path, capsys
) -> None:
    """A page with real "\\n"-separated lines (Shamila Urdu's structure-
    preserving format) splits into multiple paragraphs; a "## " line is
    correctly flagged as a heading."""
    database_path = tmp_path / "books.db"
    content = "## Chapter One\nThe first real paragraph.\nThe second real paragraph."
    book = Book(
        information={"Name": "Book Two"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, content, "Plain"),),
    )
    MasterBookRepository().import_books(database_path, (book,), (tmp_path / "two.mjbz",))
    _migrate(database_path)

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "3 paragraph(s) written" in captured.out
    assert "1 page(s) had real sub-page structure" in captured.out
    rows = _paragraph_rows(database_path, 1)
    assert rows == [
        (1, 1, 1, "## Chapter One"),
        (1, 2, 0, "The first real paragraph."),
        (1, 3, 0, "The second real paragraph."),
    ]


def test_pages_with_null_content_are_skipped(tmp_path: Path, capsys) -> None:
    """A genuinely-empty (NULL) page gets no Paragraph row - never fabricated."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Stub Book"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, None, None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (tmp_path / "stub.mjbz",))
    _migrate(database_path)

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 paragraph(s) written" in captured.out
    assert _paragraph_rows(database_path, 1) == []


def test_backfill_is_resume_safe_via_insert_or_replace(tmp_path: Path) -> None:
    """Running the backfill twice doesn't duplicate or error - INSERT OR REPLACE."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(database_path, (book,), (tmp_path / "one.mjbz",))
    _migrate(database_path)
    run(_build_args(database_path))

    run(_build_args(database_path))

    assert _paragraph_rows(database_path, 1) == [(1, 1, 0, "Some real page content")]


def test_paragraphs_fts_stays_in_sync(tmp_path: Path) -> None:
    """A backfilled paragraph is genuinely findable via ParagraphsFTS."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "A distinctive searchable phrase", "Plain"),),
    )
    MasterBookRepository().import_books(database_path, (book,), (tmp_path / "one.mjbz",))
    _migrate(database_path)

    run(_build_args(database_path))

    with sqlite3.connect(database_path) as connection:
        hit = connection.execute(
            "SELECT rowid FROM ParagraphsFTS WHERE ParagraphsFTS MATCH 'distinctive'"
        ).fetchall()
    assert len(hit) == 1


def test_library_filter_limits_which_books_are_processed(tmp_path: Path, capsys) -> None:
    """--library restricts the backfill to one library's books."""
    database_path = tmp_path / "books.db"
    book_a = Book(
        information={"Name": "Book A"}, categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content A", "Plain"),),
    )
    book_b = Book(
        information={"Name": "Book B"}, categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content B", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_a,), (tmp_path / "a.mjbz",), library_name="Library A"
    )
    MasterBookRepository().import_books(
        database_path, (book_b,), (tmp_path / "b.mjbz",), library_name="Library B"
    )
    _migrate(database_path)

    exit_code = run(_build_args(database_path, library="Library A"))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "1 book(s) to process." in captured.out
    assert _paragraph_rows(database_path, 1) == [(1, 1, 0, "Content A")]
    assert _paragraph_rows(database_path, 2) == []


def test_fails_cleanly_when_database_is_missing(tmp_path: Path) -> None:
    """A missing database returns a non-zero exit code instead of raising."""
    exit_code = run(_build_args(tmp_path / "missing.db"))

    assert exit_code == 1
