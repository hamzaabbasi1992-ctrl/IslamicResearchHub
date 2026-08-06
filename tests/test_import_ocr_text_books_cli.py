"""End-to-end tests for the OCR text books import command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.interfaces.import_ocr_text_books_cli import main


def test_main_imports_usable_files_and_skips_blanks(tmp_path: Path, capsys) -> None:
    folder = tmp_path / "texts"
    folder.mkdir()
    (folder / "Real_Book.txt").write_text("بسم الله الرحمن الرحيم " * 40, encoding="utf-8")
    (folder / "Blank Book.txt").write_text("   \n\n  ", encoding="utf-8")

    database_path = tmp_path / "books.db"
    exit_code = main([str(folder), "--library", "Test Tib", "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books with usable text: 1" in captured.out
    assert "Blank (skipped): 1" in captured.out

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT b.Title FROM Books b JOIN Libraries l ON l.LibraryID = b.LibraryID "
            "WHERE l.Name = 'Test Tib'"
        ).fetchone()
    assert row == ("Real Book",)


def test_main_scans_nested_subfolders(tmp_path: Path, capsys) -> None:
    """Real source shape: a top-level folder plus a nested subfolder both
    contain real .txt files - both must be found and imported."""
    folder = tmp_path / "texts"
    subfolder = folder / "tib and islam"
    subfolder.mkdir(parents=True)
    (folder / "Top Level Book.txt").write_text("Real top-level content " * 20, encoding="utf-8")
    (subfolder / "Nested Book.txt").write_text("Real nested content " * 20, encoding="utf-8")

    database_path = tmp_path / "books.db"
    exit_code = main([str(folder), "--library", "Test Tib", "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books with usable text: 2" in captured.out

    with sqlite3.connect(database_path) as connection:
        titles = {
            row[0]
            for row in connection.execute(
                "SELECT b.Title FROM Books b JOIN Libraries l ON l.LibraryID = b.LibraryID "
                "WHERE l.Name = 'Test Tib'"
            ).fetchall()
        }
    assert titles == {"Top Level Book", "Nested Book"}


def test_main_survives_an_unreadable_file_and_continues(tmp_path: Path, capsys) -> None:
    folder = tmp_path / "texts"
    folder.mkdir()
    (folder / "Real Book.txt").write_text("بسم الله الرحمن الرحيم " * 40, encoding="utf-8")
    # A directory matching the glob pattern is unreadable as text - triggers OSError
    # the same way a corrupted or permission-denied file would.
    (folder / "Broken Book.txt").mkdir()

    database_path = tmp_path / "books.db"
    exit_code = main([str(folder), "--library", "Test Tib", "--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books with usable text: 1" in captured.out
    assert "Failed to read (corrupted/inaccessible): 1" in captured.out
