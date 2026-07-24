"""Tests for the versioned schema migration runner."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.domain.models.migration import Migration
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (
    AUTHORS_VERSION,
    BASELINE_VERSION,
    MIGRATIONS,
    MigrationRunner,
)


def test_current_version_defaults_to_zero_on_a_fresh_database() -> None:
    """A brand-new SQLite database has no schema version set."""
    connection = sqlite3.connect(":memory:")

    assert MigrationRunner.current_version(connection) == 0


def test_pending_migrations_returns_migrations_newer_than_current_version() -> None:
    """Only migrations above the database's current version are pending."""
    connection = sqlite3.connect(":memory:")
    applied_marker = []
    migrations = (
        Migration(1, "first", lambda c: applied_marker.append(1)),
        Migration(2, "second", lambda c: applied_marker.append(2)),
    )
    runner = MigrationRunner(migrations)

    pending = runner.pending_migrations(connection)

    assert [migration.version for migration in pending] == [1, 2]


def test_migrate_applies_pending_migrations_in_order_and_bumps_version() -> None:
    """Migrations run in ascending version order and update PRAGMA user_version."""
    connection = sqlite3.connect(":memory:")
    order: list[int] = []
    migrations = (
        Migration(2, "second", lambda c: order.append(2)),
        Migration(1, "first", lambda c: order.append(1)),
    )
    runner = MigrationRunner(migrations)

    applied = runner.migrate(connection)

    assert order == [1, 2]
    assert [migration.version for migration in applied] == [1, 2]
    assert runner.current_version(connection) == 2


def test_migrate_is_idempotent_once_up_to_date() -> None:
    """Running migrate again after everything is applied does nothing."""
    connection = sqlite3.connect(":memory:")
    call_count = []
    migrations = (Migration(1, "first", lambda c: call_count.append(1)),)
    runner = MigrationRunner(migrations)
    runner.migrate(connection)

    second_run_applied = runner.migrate(connection)

    assert second_run_applied == ()
    assert call_count == [1]


def test_migration_apply_function_can_alter_the_schema() -> None:
    """A migration's apply function can run real DDL/DML against the connection."""
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE Widgets (Name TEXT)")

    def _add_column(conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE Widgets ADD COLUMN Color TEXT")

    runner = MigrationRunner((Migration(1, "add color column", _add_column),))

    runner.migrate(connection)

    columns = {row[1] for row in connection.execute("PRAGMA table_info(Widgets)").fetchall()}
    assert "Color" in columns


def test_duplicate_migration_versions_are_rejected() -> None:
    """Constructing a runner with two migrations at the same version raises."""
    migrations = (
        Migration(1, "first", lambda c: None),
        Migration(1, "duplicate", lambda c: None),
    )

    with pytest.raises(ValueError):
        MigrationRunner(migrations)


def test_real_migrations_registry_adopts_a_freshly_imported_database(
    tmp_path: Path,
) -> None:
    """The real MIGRATIONS registry applies cleanly to a just-created database.

    Databases always get their baseline schema from `MasterBookRepository`
    (via an import) before migrations ever run against them - migration 1 is
    a no-op precisely because that schema already exists by then.
    """
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")
    runner = MigrationRunner(MIGRATIONS)

    with sqlite3.connect(database_path) as connection:
        applied = runner.migrate(connection)

        assert [migration.version for migration in applied] == [
            BASELINE_VERSION,
            AUTHORS_VERSION,
        ]
        assert runner.current_version(connection) == AUTHORS_VERSION


def _seed_book(database_path: Path, title: str, author: str | None, source: str) -> None:
    """Import one minimal real book with the given author into a master database."""
    book = Book(
        information={"Name": title, "ANAME": author},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / source,)
    )


def test_authors_migration_creates_and_backfills_a_normalized_authors_table(
    tmp_path: Path,
) -> None:
    """Migration 2 creates Authors and backfills Books.AuthorID from Books.Author."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", "Imam Al-Ghazali", "one.mjbz")
    _seed_book(database_path, "Book Two", "Imam Al-Ghazali", "two.mjbz")
    _seed_book(database_path, "Book Three", "Ibn Kathir", "three.mjbz")
    _seed_book(database_path, "Book Four", None, "four.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner = MigrationRunner(MIGRATIONS)
        applied = runner.migrate(connection)

        assert [migration.version for migration in applied] == [
            BASELINE_VERSION,
            AUTHORS_VERSION,
        ]

        authors = dict(connection.execute("SELECT Name, AuthorID FROM Authors").fetchall())
        assert set(authors) == {"Imam Al-Ghazali", "Ibn Kathir"}

        rows = connection.execute(
            "SELECT Title, Author, AuthorID FROM Books ORDER BY Title"
        ).fetchall()
        by_title = {title: (author, author_id) for title, author, author_id in rows}
        assert by_title["Book One"] == ("Imam Al-Ghazali", authors["Imam Al-Ghazali"])
        assert by_title["Book Two"] == ("Imam Al-Ghazali", authors["Imam Al-Ghazali"])
        assert by_title["Book Three"] == ("Ibn Kathir", authors["Ibn Kathir"])
        assert by_title["Book Four"] == (None, None)
