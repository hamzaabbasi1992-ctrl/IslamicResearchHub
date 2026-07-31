"""Tests for re-extracting already-imported Shamila Urdu content with
structure (headings, Arabic-script quotations) preserved."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.interfaces.shamila_urdu_structure_backfill_cli import (
    build_parser,
    run,
)

_HADITH_COLUMNS = (
    "ID", "BookId", "BookNameArabic", "BookNameUrdu", "KitabID", "KitabHiddenID",
    "KitaabNameArabic", "KitaabNameUrdu", "BaabID", "BaabHiddenID",
    "BaabNameArabic", "BaabNameUrdu", "HadeesNumber", "HadithArabicText",
    "HadithArabicTextSearch", "HadithUrduText", "HadithHashiaText",
    "HadithTypeAtraaf", "HadithTypeRawaat", "HadithTypeQFT",
    "HadithHukamAjmali", "HadithHukamTafseeli", "HadithMouzuhArabic",
    "HadithMouzuhUrdu", "HadithHukamTafseeliArabic", "HadithTakhreej",
)


def _make_book_source(path: Path, html: str, fnotes_html: str | None = None) -> None:
    """Create a real, minimal Shamila Urdu Books/-style source file."""
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE Book (ID INTEGER PRIMARY KEY, txt TEXT, fnotes TEXT)")
        connection.execute(
            "CREATE TABLE tableOfContents (ID INTEGER, pageID INTEGER, txt TEXT, headingType TEXT)"
        )
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        connection.execute(
            "INSERT INTO Book (ID, txt, fnotes) VALUES (1, ?, ?)", (html, fnotes_html)
        )
        connection.execute("INSERT INTO metadata VALUES ('Book Name', 'Test Book')")
        connection.commit()
    finally:
        connection.close()


def _make_hadith_source(path: Path, arabic: str, urdu: str, hadees_number: str = "") -> None:
    """Create a real, minimal Shamila Urdu Hadith/-style source file."""
    columns_sql = ", ".join(f"{name} TEXT" for name in _HADITH_COLUMNS if name != "ID")
    values = {name: "" for name in _HADITH_COLUMNS}
    values.update(
        {"ID": 1, "HadithArabicText": arabic, "HadithUrduText": urdu, "KitabID": 1,
         "KitaabNameArabic": "Kitab", "KitaabNameUrdu": "Kitab", "BaabID": 1,
         "BaabNameArabic": "Baab", "BaabNameUrdu": "Baab", "HadeesNumber": hadees_number}
    )
    connection = sqlite3.connect(path)
    try:
        connection.execute(f"CREATE TABLE hadith (ID INTEGER PRIMARY KEY, {columns_sql})")
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        placeholders = ", ".join("?" for _ in _HADITH_COLUMNS)
        connection.execute(
            f"INSERT INTO hadith ({', '.join(_HADITH_COLUMNS)}) VALUES ({placeholders})",
            tuple(values[c] for c in _HADITH_COLUMNS),
        )
        connection.execute("INSERT INTO metadata VALUES ('Book Name', 'Test Hadith')")
        connection.commit()
    finally:
        connection.close()


def _seed_old_flattened_book(
    database_path: Path, source: Path, old_content: str, old_footnote: str | None = None
) -> int:
    """Import a book with OLD-style already-flattened content, simulating a
    book imported before structure preservation existed - the real state
    this backfill has to upgrade."""
    book = Book(
        information={"Name": "Test Book"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, old_content, None, footnote=old_footnote),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (source,), library_name="Maktaba Shamila Urdu"
    )
    with sqlite3.connect(database_path) as connection:
        return connection.execute("SELECT BookID FROM Books").fetchone()[0]


def _build_args(database_path: Path):
    return build_parser().parse_args(["--database", str(database_path)])


def test_reformats_a_books_folder_book_from_its_real_source(tmp_path: Path, capsys) -> None:
    """A book's stored Content is replaced with the freshly re-extracted,
    structure-preserving version read from its own real source file."""
    database_path = tmp_path / "books.db"
    source = tmp_path / "book.db"
    _make_book_source(
        source,
        html='<span class="mu mb1 ms22">مقدمہ</span><span class="mu mb0 ms14">متن</span>',
    )
    _seed_old_flattened_book(database_path, source, old_content="مقدمہ متن (old flattened)")

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Reformatted 1/1 book(s): 1 page(s), 0 footnote(s) updated" in captured.out
    with sqlite3.connect(database_path) as connection:
        content = connection.execute("SELECT Content FROM Pages").fetchone()[0]
    assert content == "## مقدمہ\nمتن"


def test_reformats_footnotes_too(tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "books.db"
    source = tmp_path / "book.db"
    _make_book_source(
        source,
        html='<span class="mu mb0 ms14">متن</span>',
        fnotes_html='<span class="mu mb1 ms14">نوٹ</span>',
    )
    _seed_old_flattened_book(
        database_path, source, old_content="متن (old)", old_footnote="نوٹ (old)"
    )

    run(_build_args(database_path))

    with sqlite3.connect(database_path) as connection:
        footnote = connection.execute("SELECT FootnoteText FROM Footnotes").fetchone()[0]
    assert footnote == "## نوٹ"


def test_a_books_folder_file_with_hadith_in_its_filename_is_not_misrouted(
    tmp_path: Path, capsys
) -> None:
    """A Books/-folder file whose filename contains "hadith" (a real production
    case: "fazail-e-ahle-hadith.db") must still use the generic Book reader,
    not the Hadith reader - 62 real books failed this exact way on the first
    real run, when detection matched "hadith" as a path substring instead of
    a real path segment."""
    database_path = tmp_path / "books.db"
    books_folder = tmp_path / "Books"
    books_folder.mkdir()
    source = books_folder / "fazail-e-ahle-hadith.db"
    _make_book_source(source, html='<span class="mu mb1 ms18">مقدمہ</span>')
    _seed_old_flattened_book(database_path, source, old_content="old flattened")

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Reformatted 1/1 book(s)" in captured.out
    assert "read errors: 0" in captured.out
    with sqlite3.connect(database_path) as connection:
        content = connection.execute("SELECT Content FROM Pages").fetchone()[0]
    assert content == "## مقدمہ"


def test_reformats_a_hadith_folder_book_by_folder_detection(tmp_path: Path, capsys) -> None:
    """A Source path containing "Hadith" is re-read with the Hadith reader, not the generic one."""
    database_path = tmp_path / "books.db"
    hadith_folder = tmp_path / "Hadith"
    hadith_folder.mkdir()
    source = hadith_folder / "bukhari.db"
    _make_hadith_source(source, arabic="نص عربی", urdu="ترجمہ اردو")
    _seed_old_flattened_book(database_path, source, old_content="old flattened hadith text")

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Reformatted 1/1 book(s)" in captured.out
    with sqlite3.connect(database_path) as connection:
        content = connection.execute("SELECT Content FROM Pages").fetchone()[0]
    assert content == "نص عربی\n\nترجمہ اردو"


def test_captures_hadees_number_during_the_same_re_read_pass(tmp_path: Path, capsys) -> None:
    """Migration 14's HadeesNumber is backfilled alongside the structure re-read,
    not via a separate CLI - the real hadith number, previously dropped."""
    database_path = tmp_path / "books.db"
    hadith_folder = tmp_path / "Hadith"
    hadith_folder.mkdir()
    source = hadith_folder / "bukhari.db"
    _make_hadith_source(source, arabic="نص عربی", urdu="ترجمہ اردو", hadees_number="42")
    _seed_old_flattened_book(database_path, source, old_content="old flattened hadith text")

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "1 HadeesNumber(s)" in captured.out
    with sqlite3.connect(database_path) as connection:
        hadees_number = connection.execute("SELECT HadeesNumber FROM Pages").fetchone()[0]
    assert hadees_number == "42"


def test_skips_a_book_whose_source_file_no_longer_exists(tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "books.db"
    missing_source = tmp_path / "gone.db"
    _seed_old_flattened_book(database_path, missing_source, old_content="old content")

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Source file missing: 1" in captured.out
    with sqlite3.connect(database_path) as connection:
        content = connection.execute("SELECT Content FROM Pages").fetchone()[0]
    assert content == "old content"


def test_only_processes_the_requested_library(tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "books.db"
    source = tmp_path / "book.mjbz"
    source.touch()
    book = Book(
        information={"Name": "Jibreel Book"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "some content", None),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (source,), library_name="Maktaba Jibreel (Desktop)"
    )

    exit_code = run(_build_args(database_path))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "0 book(s) to reformat." in captured.out
