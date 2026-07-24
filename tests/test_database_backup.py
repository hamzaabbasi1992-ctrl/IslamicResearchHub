"""Tests for creating, listing, and restoring master database backups."""

import sqlite3
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.database_backup import (
    DatabaseBackupService,
)


def _make_database(path: Path, marker: str) -> None:
    """Create a tiny real SQLite database containing a distinguishing marker value."""
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE Marker (Value TEXT)")
        connection.execute("INSERT INTO Marker VALUES (?)", (marker,))


def test_create_backup_produces_a_working_copy(tmp_path: Path) -> None:
    """A created backup is a real, independently-readable SQLite database."""
    database_path = tmp_path / "books.db"
    _make_database(database_path, "original")
    service = DatabaseBackupService(tmp_path / "backups")

    backup_path = service.create_backup(database_path, timestamp="20260101_000000")

    assert backup_path.is_file()
    assert backup_path.name == "books_backup_20260101_000000.db"
    with sqlite3.connect(backup_path) as connection:
        assert connection.execute("SELECT Value FROM Marker").fetchone() == ("original",)


def test_list_backups_returns_most_recent_first(tmp_path: Path) -> None:
    """Backups are listed newest-first by timestamp."""
    database_path = tmp_path / "books.db"
    _make_database(database_path, "original")
    service = DatabaseBackupService(tmp_path / "backups")
    service.create_backup(database_path, timestamp="20260101_000000")
    service.create_backup(database_path, timestamp="20260102_000000")

    backups = service.list_backups()

    assert [path.name for path in backups] == [
        "books_backup_20260102_000000.db",
        "books_backup_20260101_000000.db",
    ]


def test_list_backups_returns_empty_when_no_backup_folder(tmp_path: Path) -> None:
    """A nonexistent backup folder returns no backups rather than raising."""
    service = DatabaseBackupService(tmp_path / "nonexistent")

    assert service.list_backups() == ()


def test_restore_backup_overwrites_the_live_database(tmp_path: Path) -> None:
    """Restoring a backup replaces the live database's content with the backup's."""
    database_path = tmp_path / "books.db"
    _make_database(database_path, "original")
    service = DatabaseBackupService(tmp_path / "backups")
    backup_path = service.create_backup(database_path, timestamp="20260101_000000")

    # Change the live database after the backup was taken.
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Marker SET Value = 'changed'")

    service.restore_backup(backup_path, database_path)

    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT Value FROM Marker").fetchone() == ("original",)
