"""End-to-end tests for the database migration command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.interfaces.migrate_database_cli import main


def _make_database(path: Path) -> None:
    """Create a tiny real, unversioned SQLite database."""
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE Marker (Value TEXT)")


def test_main_applies_pending_migrations_and_reports_them(tmp_path: Path, capsys) -> None:
    """Running against a fresh database applies the baseline migration."""
    database_path = tmp_path / "books.db"
    _make_database(database_path)

    exit_code = main(["--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Version before: 0" in captured.out
    assert "Applied 1:" in captured.out
    assert "Version after: 1" in captured.out


def test_main_reports_up_to_date_on_second_run(tmp_path: Path, capsys) -> None:
    """Running again after everything is applied reports no pending migrations."""
    database_path = tmp_path / "books.db"
    _make_database(database_path)
    main(["--database", str(database_path)])

    exit_code = main(["--database", str(database_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Already up to date." in captured.out


def test_main_fails_cleanly_when_database_is_missing(tmp_path: Path) -> None:
    """A missing database returns a non-zero exit code instead of raising."""
    exit_code = main(["--database", str(tmp_path / "missing.db")])

    assert exit_code == 1
