"""End-to-end tests for the Maktaba Shamila Urdu import command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.interfaces.shamila_urdu_import_cli import main


def _make_book_db(path: Path, title: str, text: str) -> None:
    """Create a real, minimal Shamila Urdu book database."""
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE Book (ID INTEGER PRIMARY KEY, txt TEXT, fnotes TEXT)")
        connection.execute(
            "CREATE TABLE tableOfContents (ID INTEGER, pageID INTEGER, txt TEXT, headingType TEXT)"
        )
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        connection.execute(
            "INSERT INTO Book (ID, txt, fnotes) VALUES (1, ?, NULL)", (f"<span>{text}</span>",)
        )
        connection.execute(
            "INSERT INTO metadata (fieldName, fieldValue) VALUES ('Book Name', ?)", (title,)
        )


def test_main_imports_real_books_and_skips_the_catalog_file(tmp_path: Path, capsys) -> None:
    """Books/<category>/*.db files are imported; the library.db catalog is skipped."""
    data_folder = tmp_path / "data"
    books_folder = data_folder / "Books" / "ahkaam"
    books_folder.mkdir(parents=True)
    _make_book_db(books_folder / "book-one.db", "کتاب اول", "پہلا صفحہ")
    (data_folder / "library.db").write_bytes(b"not a real book, just the catalog index")

    database_path = tmp_path / "books.db"
    exit_code = main(
        [str(data_folder), "--library", "Test Shamila Urdu", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books processed: 1" in captured.out
    assert "Books imported: 1" in captured.out

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT b.Title, b.Category FROM Books b JOIN Libraries l ON l.LibraryID = b.LibraryID "
            "WHERE l.Name = 'Test Shamila Urdu'"
        ).fetchone()
    assert row == ("کتاب اول", "ahkaam")


def test_main_survives_a_corrupted_book_and_continues(tmp_path: Path, capsys) -> None:
    """A corrupted book database is logged and skipped, not allowed to crash the run."""
    data_folder = tmp_path / "data"
    books_folder = data_folder / "Books" / "aqeeda"
    books_folder.mkdir(parents=True)
    _make_book_db(books_folder / "good-book.db", "اچھی کتاب", "متن")
    (books_folder / "corrupted-book.db").write_bytes(b"not a real sqlite database")

    database_path = tmp_path / "books.db"
    exit_code = main(
        [str(data_folder), "--library", "Test Shamila Urdu", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books processed: 2" in captured.out
    assert "Books failed: 1" in captured.out
    assert "Books imported: 1" in captured.out


def test_main_fails_cleanly_when_folder_is_missing(tmp_path: Path) -> None:
    """A missing source folder returns a non-zero exit code instead of raising."""
    exit_code = main([str(tmp_path / "does_not_exist")])

    assert exit_code == 1


def _make_hadith_db(path: Path, book_name: str) -> None:
    """Create a real, minimal Hadith/ collection database."""
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE hadith (ID INTEGER PRIMARY KEY, KitabID INTEGER, "
            "KitabHiddenID TEXT, KitaabNameArabic TEXT, KitaabNameUrdu TEXT, "
            "BaabID INTEGER, BaabHiddenID TEXT, BaabNameArabic TEXT, BaabNameUrdu TEXT, "
            "HadeesNumber TEXT, HadithArabicText TEXT, HadithUrduText TEXT, "
            "HadithHashiaText TEXT, HadithHukamAjmali TEXT)"
        )
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        connection.execute(
            "INSERT INTO hadith (ID, KitabID, KitabHiddenID, KitaabNameArabic, "
            "KitaabNameUrdu, BaabID, BaabHiddenID, BaabNameArabic, BaabNameUrdu, "
            "HadeesNumber, HadithArabicText, HadithUrduText, HadithHashiaText, HadithHukamAjmali) "
            "VALUES (1, 1, '1', 'کتاب', 'کتاب', 1, '1', 'باب', 'باب', '1', 'عربی', 'اردو', NULL, 'صحیح')"
        )
        connection.execute(
            "INSERT INTO metadata (fieldName, fieldValue) VALUES ('Book Name', ?)", (book_name,)
        )


def _make_quran_translation_db(path: Path, book_name: str) -> None:
    """Create a real, minimal Quran/ Tarjuma database."""
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE Tarjuma (ID INTEGER PRIMARY KEY, txt TEXT, SurahNumber INTEGER, "
            "surahTitle TEXT, ayahNumber INTEGER)"
        )
        connection.execute("CREATE TABLE metadata (fieldName TEXT, fieldValue TEXT)")
        connection.execute(
            "INSERT INTO Tarjuma (ID, txt, SurahNumber, surahTitle, ayahNumber) "
            "VALUES (1, 'ترجمہ کی عبارت', 1, 'الفاتحة', 1)"
        )
        connection.execute(
            "INSERT INTO metadata (fieldName, fieldValue) VALUES ('Book Name', ?)", (book_name,)
        )


def test_main_imports_hadith_and_quran_folders_alongside_books(tmp_path: Path, capsys) -> None:
    """Hadith/ and Quran/ files - previously silently unreadable - are now imported too."""
    data_folder = tmp_path / "data"
    books_folder = data_folder / "Books" / "ahkaam"
    books_folder.mkdir(parents=True)
    _make_book_db(books_folder / "book-one.db", "کتاب اول", "پہلا صفحہ")

    hadith_folder = data_folder / "Hadith"
    hadith_folder.mkdir(parents=True)
    _make_hadith_db(hadith_folder / "bukhari.db", "صحیح البخاری")

    quran_folder = data_folder / "Quran"
    quran_folder.mkdir(parents=True)
    _make_quran_translation_db(quran_folder / "01_TarjumaJunagarhi.db", "ترجمہ جوناگڑھی")

    database_path = tmp_path / "books.db"
    exit_code = main(
        [str(data_folder), "--library", "Test Shamila Urdu", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books processed: 3" in captured.out
    assert "Books failed: 0" in captured.out
    assert "Books imported: 3" in captured.out

    with sqlite3.connect(database_path) as connection:
        titles = {
            row[0]
            for row in connection.execute(
                "SELECT b.Title FROM Books b JOIN Libraries l ON l.LibraryID = b.LibraryID "
                "WHERE l.Name = 'Test Shamila Urdu'"
            ).fetchall()
        }
    assert titles == {"کتاب اول", "صحیح البخاری", "ترجمہ جوناگڑھی"}
