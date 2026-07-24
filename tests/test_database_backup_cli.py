"""End-to-end tests for the database backup/restore command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.interfaces.database_backup_cli import main


def _make_database(path: Path, marker: str) -> None:
    """Create a tiny real SQLite database containing a distinguishing marker value."""
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE Marker (Value TEXT)")
        connection.execute("INSERT INTO Marker VALUES (?)", (marker,))


def test_backup_subcommand_creates_a_backup_file(tmp_path: Path, capsys) -> None:
    """The `backup` subcommand creates a backup and prints its path."""
    database_path = tmp_path / "books.db"
    backup_folder = tmp_path / "backups"
    _make_database(database_path, "original")

    exit_code = main(
        [
            "backup",
            "--database",
            str(database_path),
            "--backup-folder",
            str(backup_folder),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Backup created:" in captured.out
    assert list(backup_folder.glob("*_backup_*.db"))


def test_backup_subcommand_fails_cleanly_when_database_is_missing(
    tmp_path: Path,
) -> None:
    """A missing source database returns a non-zero exit code instead of raising."""
    exit_code = main(
        [
            "backup",
            "--database",
            str(tmp_path / "missing.db"),
            "--backup-folder",
            str(tmp_path / "backups"),
        ]
    )

    assert exit_code == 1


def test_list_subcommand_reports_no_backups_when_folder_is_empty(
    tmp_path: Path, capsys
) -> None:
    """Listing an empty/nonexistent backup folder reports no backups, exit 0."""
    exit_code = main(["list", "--backup-folder", str(tmp_path / "backups")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "No backups found." in captured.out


def test_list_subcommand_reports_existing_backups(tmp_path: Path, capsys) -> None:
    """Listing a folder with backups prints each backup's name."""
    database_path = tmp_path / "books.db"
    backup_folder = tmp_path / "backups"
    _make_database(database_path, "original")
    main(["backup", "--database", str(database_path), "--backup-folder", str(backup_folder)])

    exit_code = main(["list", "--backup-folder", str(backup_folder)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "books_backup_" in captured.out


def test_restore_subcommand_requires_explicit_confirmation(tmp_path: Path) -> None:
    """Restoring without --yes is refused and leaves the live database untouched."""
    database_path = tmp_path / "books.db"
    backup_folder = tmp_path / "backups"
    _make_database(database_path, "original")
    main(["backup", "--database", str(database_path), "--backup-folder", str(backup_folder)])
    backup_file = next(backup_folder.glob("*_backup_*.db"))
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Marker SET Value = 'changed'")

    exit_code = main(["restore", str(backup_file), "--database", str(database_path)])

    assert exit_code == 1
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT Value FROM Marker").fetchone() == ("changed",)


def test_restore_subcommand_restores_when_confirmed(tmp_path: Path, capsys) -> None:
    """Restoring with --yes overwrites the live database with the backup's content."""
    database_path = tmp_path / "books.db"
    backup_folder = tmp_path / "backups"
    _make_database(database_path, "original")
    main(["backup", "--database", str(database_path), "--backup-folder", str(backup_folder)])
    backup_file = next(backup_folder.glob("*_backup_*.db"))
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Marker SET Value = 'changed'")

    exit_code = main(
        ["restore", str(backup_file), "--database", str(database_path), "--yes"]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Restored" in captured.out
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT Value FROM Marker").fetchone() == ("original",)


def test_restore_subcommand_fails_cleanly_when_backup_file_is_missing(
    tmp_path: Path,
) -> None:
    """A missing backup file returns a non-zero exit code instead of raising."""
    exit_code = main(
        [
            "restore",
            str(tmp_path / "missing_backup.db"),
            "--database",
            str(tmp_path / "books.db"),
            "--yes",
        ]
    )

    assert exit_code == 1
