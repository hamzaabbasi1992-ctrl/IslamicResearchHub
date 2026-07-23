"""End-to-end tests for the Maknoon import command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.interfaces.maknoon_import_cli import main


def test_main_imports_usable_files_and_skips_placeholders(tmp_path: Path, capsys) -> None:
    """Real-text files are imported; placeholder-only files are skipped."""
    folder = tmp_path / "texts"
    folder.mkdir()
    (folder / "Real Book.pdf.txt").write_text("بسم الله الرحمن الرحيم " * 40, encoding="utf-8")
    (folder / "Blank Book.pdf.txt").write_text(
        "\n".join(f"oooooo {n} oooooo" for n in range(1, 30)), encoding="utf-8"
    )

    database_path = tmp_path / "books.db"
    exit_code = main(
        [str(folder), "--library", "Test Maknoon", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books with usable text: 1" in captured.out
    assert "Placeholder-only (skipped): 1" in captured.out

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT b.Title FROM Books b JOIN Libraries l ON l.LibraryID = b.LibraryID "
            "WHERE l.Name = 'Test Maknoon'"
        ).fetchone()
    assert row == ("Real Book",)


def test_main_survives_an_unreadable_file_and_continues(tmp_path: Path, capsys) -> None:
    """A file that cannot be read (e.g. corrupted/inaccessible) is logged and skipped,
    not allowed to crash the whole import run."""
    folder = tmp_path / "texts"
    folder.mkdir()
    (folder / "Real Book.pdf.txt").write_text("بسم الله الرحمن الرحيم " * 40, encoding="utf-8")
    # A directory matching the glob pattern is unreadable as text - triggers OSError
    # the same way a corrupted or permission-denied file would.
    (folder / "Broken Book.pdf.txt").mkdir()

    database_path = tmp_path / "books.db"
    exit_code = main(
        [str(folder), "--library", "Test Maknoon", "--database", str(database_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books with usable text: 1" in captured.out
    assert "Failed to read (corrupted/inaccessible): 1" in captured.out

    with sqlite3.connect(database_path) as connection:
        titles = {
            row[0]
            for row in connection.execute(
                "SELECT b.Title FROM Books b JOIN Libraries l ON l.LibraryID = b.LibraryID "
                "WHERE l.Name = 'Test Maknoon'"
            ).fetchall()
        }
    assert titles == {"Real Book"}
