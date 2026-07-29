"""Tests for backfilling Books.SourcePdfHint, using a fake decryptor
(the real one requires the external app's own DLL)."""

import sqlite3
from pathlib import Path

from islamic_research_hub.application.jibreel_desktop_import import DecryptResult
from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (
    MIGRATIONS,
    MigrationRunner,
)
from islamic_research_hub.interfaces.jibreel_pdf_hint_backfill_cli import build_parser, run

STUB_PAGE_COUNT = 25


class FakeDecryptor:
    """Simulates decryption: writes a real .mjbz carrying the given PDF hints."""

    def __init__(self, pdf_hints: dict[str, str] | None = None) -> None:
        self._pdf_hints = pdf_hints or {}

    def decrypt_all(self, jobs):
        results = []
        for source, destination in jobs:
            destination.parent.mkdir(parents=True, exist_ok=True)
            _write_mjbz(destination, hint=self._pdf_hints.get(source.stem))
            results.append(DecryptResult(source, destination, succeeded=True))
        return tuple(results)


def _write_mjbz(path: Path, hint: str | None) -> None:
    """Write a minimal SQLite file matching the verified Jibreel schema.

    `sqlite3.Connection` used as a context manager only commits/rolls
    back on exit - it does not close the connection, which left the file
    handle open long enough to conflict with the CLI's own
    `TemporaryDirectory` cleanup on Windows. Closed explicitly instead.
    """
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            'CREATE TABLE Information ([Key] TEXT, Value TEXT);'
        )
        if hint is not None:
            connection.execute("INSERT INTO Information VALUES ('PDF', ?)", (hint,))
        connection.commit()
    finally:
        connection.close()


def _seed_stub_book(database_path: Path, source_id: str, library: str) -> None:
    """Import one real heading-only book with the given SourceBookID."""
    stub_pages = tuple(Page(i, i, "hd", None) for i in range(1, STUB_PAGE_COUNT + 1))
    book = Book(
        information={"Name": f"Book {source_id}", "MJBN": source_id},
        categories=(),
        table_of_contents=(),
        pages=stub_pages,
    )
    MasterBookRepository().import_books(
        database_path, (book,), (Path(f"{source_id}.mjbz"),), library_name=library
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)


def _build_args(books_folder: Path, database_path: Path, **overrides):
    argv = [
        "--books-folder", str(books_folder),
        "--sqlite-dll", "unused.dll",
        "--database", str(database_path),
        "--library", overrides.get("library", "Maktaba Jibreel (Desktop)"),
    ]
    if overrides.get("all"):
        argv.append("--all")
    return build_parser().parse_args(argv)


def test_backfills_a_real_pdf_hint_for_a_stub_book(tmp_path: Path, capsys) -> None:
    """A heading-only book with a real PDF hint gets Books.SourcePdfHint set."""
    database_path = tmp_path / "books.db"
    _seed_stub_book(database_path, "853", "Maktaba Jibreel (Desktop)")
    args = _build_args(tmp_path / "books", database_path)

    exit_code = run(args, FakeDecryptor({"853": "AASAAR_UL_HADEES_VOL_01.pdf"}))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "1 book(s) need a PDF hint." in captured.out
    assert "Done. 1/1 book(s) got a real PDF hint." in captured.out

    with sqlite3.connect(database_path) as connection:
        hint = connection.execute("SELECT SourcePdfHint FROM Books").fetchone()[0]
    assert hint == "AASAAR_UL_HADEES_VOL_01.pdf"


def test_leaves_hint_null_when_the_source_has_none(tmp_path: Path, capsys) -> None:
    """A book whose decrypted source has no PDF key stays NULL, not an error."""
    database_path = tmp_path / "books.db"
    _seed_stub_book(database_path, "700", "Maktaba Jibreel (Desktop)")
    args = _build_args(tmp_path / "books", database_path)

    exit_code = run(args, FakeDecryptor({}))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Done. 0/1 book(s) got a real PDF hint." in captured.out
    with sqlite3.connect(database_path) as connection:
        hint = connection.execute("SELECT SourcePdfHint FROM Books").fetchone()[0]
    assert hint is None


def test_rerun_skips_books_that_already_have_a_hint(tmp_path: Path, capsys) -> None:
    """Resume-safe: a book with a stored hint is not re-decrypted on the next run."""
    database_path = tmp_path / "books.db"
    _seed_stub_book(database_path, "853", "Maktaba Jibreel (Desktop)")
    args = _build_args(tmp_path / "books", database_path)
    run(args, FakeDecryptor({"853": "AASAAR_UL_HADEES_VOL_01.pdf"}))
    capsys.readouterr()

    exit_code = run(args, FakeDecryptor({"853": "SOMETHING_ELSE.pdf"}))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 book(s) need a PDF hint." in captured.out
    with sqlite3.connect(database_path) as connection:
        hint = connection.execute("SELECT SourcePdfHint FROM Books").fetchone()[0]
    assert hint == "AASAAR_UL_HADEES_VOL_01.pdf"


def test_ignores_books_with_real_content_by_default(tmp_path: Path, capsys) -> None:
    """A book with real page content is not treated as a stub needing a hint."""
    database_path = tmp_path / "books.db"
    full_pages = tuple(
        Page(i, i, "Real substantial page content " * 10, None)
        for i in range(1, STUB_PAGE_COUNT + 1)
    )
    book = Book(
        information={"Name": "Full Book", "MJBN": "900"},
        categories=(),
        table_of_contents=(),
        pages=full_pages,
    )
    MasterBookRepository().import_books(
        database_path, (book,), (Path("900.mjbz"),), library_name="Maktaba Jibreel (Desktop)"
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)
    args = _build_args(tmp_path / "books", database_path)

    exit_code = run(args, FakeDecryptor({"900": "SHOULD_NOT_BE_USED.pdf"}))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 book(s) need a PDF hint." in captured.out


def test_all_flag_includes_books_with_real_content(tmp_path: Path, capsys) -> None:
    """--all backfills every book in the library, not just heading-only stubs."""
    database_path = tmp_path / "books.db"
    full_pages = tuple(
        Page(i, i, "Real substantial page content " * 10, None)
        for i in range(1, STUB_PAGE_COUNT + 1)
    )
    book = Book(
        information={"Name": "Full Book", "MJBN": "900"},
        categories=(),
        table_of_contents=(),
        pages=full_pages,
    )
    MasterBookRepository().import_books(
        database_path, (book,), (Path("900.mjbz"),), library_name="Maktaba Jibreel (Desktop)"
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)
    args = _build_args(tmp_path / "books", database_path, all=True)

    exit_code = run(args, FakeDecryptor({"900": "REAL_PDF.pdf"}))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Done. 1/1 book(s) got a real PDF hint." in captured.out


def test_only_processes_the_requested_library(tmp_path: Path, capsys) -> None:
    """A stub book in a different library is left alone."""
    database_path = tmp_path / "books.db"
    _seed_stub_book(database_path, "111", "Maktaba Jibreel (Mobile)")
    args = _build_args(tmp_path / "books", database_path, library="Maktaba Jibreel (Desktop)")

    exit_code = run(args, FakeDecryptor({"111": "SHOULD_NOT_BE_USED.pdf"}))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 book(s) need a PDF hint." in captured.out
