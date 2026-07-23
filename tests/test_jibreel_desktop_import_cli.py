"""End-to-end tests for the Jibreel Desktop import command-line interface,
using a fake decryptor (the real one requires the external app's own DLL)."""

import sqlite3
from pathlib import Path

from islamic_research_hub.application.jibreel_desktop_import import DecryptResult
from islamic_research_hub.interfaces.jibreel_desktop_import_cli import build_parser, run


class FakeDecryptor:
    """Simulates decryption: writes a valid .mjbz for every unlocked source file."""

    def __init__(self, locked_stems: frozenset[str] = frozenset()) -> None:
        self._locked_stems = locked_stems

    def decrypt_all(self, jobs):
        """Write a valid .mjbz for each job not in locked_stems; report the rest as failed."""
        results = []
        for source, destination in jobs:
            if source.stem in self._locked_stems:
                results.append(DecryptResult(source, destination, succeeded=False))
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            _write_valid_mjbz(destination, mjbn=source.stem, title=f"Book {source.stem}")
            results.append(DecryptResult(source, destination, succeeded=True))
        return tuple(results)


def _write_valid_mjbz(path: Path, mjbn: str, title: str) -> None:
    """Write a minimal SQLite file matching the verified Jibreel schema."""
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE Information ([Key] TEXT, Value TEXT);
            CREATE TABLE Category (MJCN INTEGER, Name TEXT, P_MJCN INTEGER, SortKey INTEGER);
            CREATE TABLE Title (
                TitleID INTEGER, Title TEXT, PageNo INTEGER, ParentID INTEGER, SortKey INTEGER
            );
            CREATE TABLE Content (ContentID INTEGER, PageNo INTEGER, ContentF TEXT, ContentP TEXT);
            """
        )
        connection.execute("INSERT INTO Information VALUES ('MJBN', ?)", (mjbn,))
        connection.execute("INSERT INTO Information VALUES ('Name', ?)", (title,))
        connection.execute(
            "INSERT INTO Content VALUES (1, 1, 'Some real page content', 'Plain')"
        )


def _build_args(tmp_path: Path, app_folder: Path, database_path: Path):
    return build_parser().parse_args(
        [
            str(app_folder),
            "--sqlite-dll",
            "unused.dll",
            "--staging",
            str(tmp_path / "staging"),
            "--database",
            str(database_path),
            "--library",
            "Test Desktop",
        ]
    )


def test_run_decrypts_and_imports_new_files(tmp_path: Path, capsys) -> None:
    """New .mjbx files are decrypted and imported through the existing pipeline."""
    app_folder = tmp_path / "app"
    app_folder.mkdir()
    (app_folder / "10.mjbx").touch()
    (app_folder / "20.mjbx").touch()
    database_path = tmp_path / "books.db"
    args = _build_args(tmp_path, app_folder, database_path)

    exit_code = run(args, FakeDecryptor())

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Found 2 new .mjbx file(s) to decrypt." in captured.out
    assert "Decrypted: 2, failed (wrong/unknown password): 0" in captured.out
    assert "Books imported: 2" in captured.out

    with sqlite3.connect(database_path) as connection:
        titles = {
            row[0]
            for row in connection.execute(
                "SELECT b.Title FROM Books b JOIN Libraries l ON l.LibraryID = b.LibraryID "
                "WHERE l.Name = 'Test Desktop'"
            ).fetchall()
        }
    assert titles == {"Book 10", "Book 20"}


def test_run_skips_locked_files_and_imports_the_rest(tmp_path: Path, capsys) -> None:
    """A file that fails to decrypt (wrong/unknown password) is skipped, not fatal."""
    app_folder = tmp_path / "app"
    app_folder.mkdir()
    (app_folder / "10.mjbx").touch()
    (app_folder / "99.mjbx").touch()
    args = _build_args(tmp_path, app_folder, tmp_path / "books.db")

    exit_code = run(args, FakeDecryptor(locked_stems=frozenset({"99"})))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Decrypted: 1, failed (wrong/unknown password): 1" in captured.out
    assert "Books imported: 1" in captured.out


def test_run_skips_files_already_in_the_database(tmp_path: Path, capsys) -> None:
    """A file whose id is already imported is not re-planned for decryption."""
    app_folder = tmp_path / "app"
    app_folder.mkdir()
    (app_folder / "10.mjbx").touch()
    database_path = tmp_path / "books.db"
    args = _build_args(tmp_path, app_folder, database_path)
    run(args, FakeDecryptor())
    capsys.readouterr()

    exit_code = run(args, FakeDecryptor())

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No new .mjbx files to decrypt." in captured.out


def test_run_reports_when_folder_is_missing(tmp_path: Path) -> None:
    """A nonexistent source folder returns a clear failure instead of crashing."""
    args = _build_args(tmp_path, tmp_path / "does-not-exist", tmp_path / "books.db")

    exit_code = run(args, FakeDecryptor())

    assert exit_code == 1
