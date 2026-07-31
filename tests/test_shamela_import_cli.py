"""End-to-end tests for the Maktaba Shamela import command-line interface.

`PowerShellShamelaReader.read_all` is mocked (real 32-bit PowerShell/COM
was verified by hand against real files - see CHANGELOG); everything
downstream of it (catalog lookup, Book construction, master-database
import, volume/Series grouping) runs for real against real SQLite
fixtures, the same way the rest of this project's CLI tests work.
"""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.infrastructure.persistence.powershell_shamela_reader import (
    PowerShellShamelaReader,
    ShamelaRawBook,
    ShamelaReaderError,
)
from islamic_research_hub.interfaces.shamela_import_cli import BATCH_SIZE, main

_CATALOG_COLUMNS = (
    "id, bookName, shamelaID, bookInfo, filePath, authorId, authorName, "
    "authorDeath, version, cat, archive, titleTable, bookTable, indexFLags"
)


def _make_catalog(path: Path, entries: tuple[tuple[int, str, str | None], ...]) -> None:
    """Create a real, minimal book_index.db: (shamelaID, bookName, authorName)."""
    with sqlite3.connect(path) as connection:
        connection.execute(f"CREATE TABLE books ({_CATALOG_COLUMNS})")
        for row_id, (shamela_id, book_name, author_name) in enumerate(entries, start=1):
            connection.execute(
                "INSERT INTO books (id, bookName, shamelaID, authorName) VALUES (?, ?, ?, ?)",
                (row_id, book_name, shamela_id, author_name),
            )


def _fake_reader(book_rows_by_stem: dict[str, tuple[dict, ...]]):
    """A fake `read_all` returning canned rows keyed by each path's filename stem."""

    def _read_all(self, paths: tuple[Path, ...]) -> tuple[ShamelaRawBook, ...]:
        results = []
        for path in paths:
            rows = book_rows_by_stem.get(path.stem)
            if rows is None:
                results.append(
                    ShamelaRawBook(path, succeeded=False, error="not found", book_rows=(), title_rows=())
                )
            else:
                results.append(
                    ShamelaRawBook(
                        path,
                        succeeded=True,
                        error=None,
                        book_rows=rows,
                        title_rows=({"id": 1, "tit": "Heading", "lvl": 1, "sub": 0},),
                    )
                )
        return tuple(results)

    return _read_all


def test_main_imports_a_real_book_using_the_catalog_for_title_and_author(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real .mdb is titled/authored from the catalog, not the bare filename."""
    source_folder = tmp_path / "source"
    books_folder = source_folder / "Books"
    books_folder.mkdir(parents=True)
    (books_folder / "1.mdb").write_bytes(b"placeholder")
    _make_catalog(source_folder / "book_index.db", ((1, "كتاب الزكاة", "الإمام النووي"),))
    monkeypatch.setattr(
        PowerShellShamelaReader,
        "read_all",
        _fake_reader({"1": ({"id": 1, "nass": "Content", "page": 1, "part": 1},)}),
    )

    database_path = tmp_path / "books.db"
    exit_code = main(
        [str(books_folder), "--database", str(database_path), "--library", "Test Shamela"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Real .mdb files processed: 1" in captured.out
    assert "Books imported: 1" in captured.out
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT b.Title, b.Author FROM Books b "
            "JOIN Libraries l ON l.LibraryID = b.LibraryID WHERE l.Name = 'Test Shamela'"
        ).fetchone()
    assert row == ("كتاب الزكاة", "الإمام النووي")


def test_main_splits_a_multi_volume_file_and_groups_it_into_a_series(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real multi-part .mdb becomes multiple Books, grouped into one Series."""
    source_folder = tmp_path / "source"
    books_folder = source_folder / "Books"
    books_folder.mkdir(parents=True)
    (books_folder / "2.mdb").write_bytes(b"placeholder")
    _make_catalog(source_folder / "book_index.db", ((2, "تفسير", None),))
    monkeypatch.setattr(
        PowerShellShamelaReader,
        "read_all",
        _fake_reader(
            {
                "2": (
                    {"id": 1, "nass": "Vol1", "page": 1, "part": 1},
                    {"id": 2, "nass": "Vol2", "page": 1, "part": 2},
                )
            }
        ),
    )

    database_path = tmp_path / "books.db"
    exit_code = main([str(books_folder), "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books imported: 2" in captured.out
    assert "Series (multi-volume works) after grouping: 1" in captured.out
    with sqlite3.connect(database_path) as connection:
        titles = {
            row[0] for row in connection.execute("SELECT Title FROM Books").fetchall()
        }
    assert titles == {"تفسير - part 1", "تفسير - part 2"}


def test_main_survives_a_failed_file_and_continues(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file the reader couldn't open is logged and skipped, not a crash."""
    source_folder = tmp_path / "source"
    books_folder = source_folder / "Books"
    books_folder.mkdir(parents=True)
    (books_folder / "1.mdb").write_bytes(b"placeholder")
    (books_folder / "2.mdb").write_bytes(b"placeholder")
    monkeypatch.setattr(
        PowerShellShamelaReader,
        "read_all",
        _fake_reader({"1": ({"id": 1, "nass": "Content", "page": 1, "part": 1},)}),
        # "2" is intentionally absent -> fake reader reports it as failed
    )

    database_path = tmp_path / "books.db"
    exit_code = main([str(books_folder), "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Files failed to read: 1" in captured.out
    assert "Books imported: 1" in captured.out


def test_main_survives_a_whole_batch_failure_and_continues_to_the_next_batch(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real bug found and fixed: a whole-batch failure (PowerShell OOM on a
    large batch, previously invisible as a raw JSONDecodeError) used to kill
    the entire multi-hour import run. It must instead fail just that batch's
    files and continue - proven here with enough files to span 2 batches."""
    source_folder = tmp_path / "source"
    books_folder = source_folder / "Books"
    books_folder.mkdir(parents=True)
    total_files = BATCH_SIZE + 5
    for index in range(total_files):
        (books_folder / f"{index}.mdb").write_bytes(b"placeholder")

    call_count = 0

    def _read_all(self, paths):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ShamelaReaderError("simulated whole-batch failure (e.g. PowerShell OOM)")
        return tuple(
            ShamelaRawBook(
                path=path,
                succeeded=True,
                error=None,
                book_rows=({"id": 1, "nass": "Content", "page": 1, "part": 1},),
                title_rows=(),
            )
            for path in paths
        )

    monkeypatch.setattr(PowerShellShamelaReader, "read_all", _read_all)

    database_path = tmp_path / "books.db"
    exit_code = main([str(books_folder), "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert call_count == 2  # both batches were attempted, not just the first
    assert f"Files failed to read: {BATCH_SIZE}" in captured.out
    assert "Books imported: 5" in captured.out  # the second batch's files


def test_earlier_batches_are_already_persisted_when_a_later_batch_crashes_fatally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real bug found and fixed: the whole run used to hold every Book in
    memory and write to the database only once at the very end - a fatal,
    unhandled crash partway through (the real MemoryError this project hit
    at full-corpus scale) discarded ALL prior progress, however far it got.
    Batches are now written to the database immediately as each completes,
    so an unhandled crash in a later batch leaves earlier batches' books
    already safely in the database, not lost."""
    source_folder = tmp_path / "source"
    books_folder = source_folder / "Books"
    books_folder.mkdir(parents=True)
    total_files = BATCH_SIZE + 5
    for index in range(total_files):
        (books_folder / f"{index}.mdb").write_bytes(b"placeholder")

    call_count = 0

    def _read_all(self, paths):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise MemoryError("simulated fatal, unhandled crash in the second batch")
        return tuple(
            ShamelaRawBook(
                path=path,
                succeeded=True,
                error=None,
                book_rows=({"id": 1, "nass": "Content", "page": 1, "part": 1},),
                title_rows=(),
            )
            for path in paths
        )

    monkeypatch.setattr(PowerShellShamelaReader, "read_all", _read_all)

    database_path = tmp_path / "books.db"
    with pytest.raises(MemoryError):
        main([str(books_folder), "--database", str(database_path)])

    assert database_path.is_file()
    with sqlite3.connect(database_path) as connection:
        book_count = connection.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
    assert book_count == BATCH_SIZE  # the first (completed) batch's books survived


def test_main_falls_back_to_filename_titles_when_no_catalog_is_found(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No book_index.db at all is a real, honest situation, not a crash."""
    source_folder = tmp_path / "source"
    books_folder = source_folder / "Books"
    books_folder.mkdir(parents=True)
    (books_folder / "5.mdb").write_bytes(b"placeholder")
    monkeypatch.setattr(
        PowerShellShamelaReader,
        "read_all",
        _fake_reader({"5": ({"id": 1, "nass": "Content", "page": 1, "part": 1},)}),
    )

    database_path = tmp_path / "books.db"
    exit_code = main([str(books_folder), "--database", str(database_path)])

    assert exit_code == 0
    with sqlite3.connect(database_path) as connection:
        title = connection.execute("SELECT Title FROM Books").fetchone()[0]
    assert title == "5"


def test_main_respects_the_limit_flag_for_a_pilot_run(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--limit caps how many real files are processed, for a pilot batch."""
    source_folder = tmp_path / "source"
    books_folder = source_folder / "Books"
    books_folder.mkdir(parents=True)
    for stem in ("1", "2", "3"):
        (books_folder / f"{stem}.mdb").write_bytes(b"placeholder")
    monkeypatch.setattr(
        PowerShellShamelaReader,
        "read_all",
        _fake_reader(
            {stem: ({"id": 1, "nass": "Content", "page": 1, "part": 1},) for stem in ("1", "2", "3")}
        ),
    )

    database_path = tmp_path / "books.db"
    exit_code = main([str(books_folder), "--database", str(database_path), "--limit", "2"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Real .mdb files processed: 2" in captured.out
