"""Backup and restore support for the master book database.

Uses SQLite's own online backup API (`Connection.backup`), which safely
copies a database even if it is currently in use, rather than a raw file
copy that could capture a database mid-write.
"""

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DEFAULT_BACKUP_FOLDER = Path("data/backups")
_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


class DatabaseBackupService:
    """Create, list, and restore timestamped backups of the master database."""

    def __init__(self, backup_folder: Path = DEFAULT_BACKUP_FOLDER) -> None:
        self._backup_folder = backup_folder

    def create_backup(self, database_path: Path, timestamp: str | None = None) -> Path:
        """Create a timestamped backup copy of the database, returning its path."""
        self._backup_folder.mkdir(parents=True, exist_ok=True)
        stamp = timestamp or datetime.now().strftime(_TIMESTAMP_FORMAT)
        backup_path = self._backup_folder / f"{database_path.stem}_backup_{stamp}.db"
        with (
            closing(sqlite3.connect(database_path)) as source,
            closing(sqlite3.connect(backup_path)) as destination,
        ):
            source.backup(destination)
        return backup_path

    def list_backups(self, database_stem: str | None = None) -> tuple[Path, ...]:
        """Return every backup file, most recent first."""
        if not self._backup_folder.is_dir():
            return ()
        pattern = f"{database_stem}_backup_*.db" if database_stem else "*_backup_*.db"
        return tuple(
            sorted(self._backup_folder.glob(pattern), key=lambda path: path.name, reverse=True)
        )

    def restore_backup(self, backup_path: Path, database_path: Path) -> None:
        """Restore a backup file over the live database, overwriting it."""
        with (
            closing(sqlite3.connect(backup_path)) as source,
            closing(sqlite3.connect(database_path)) as destination,
        ):
            source.backup(destination)
