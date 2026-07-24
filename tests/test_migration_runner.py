"""Tests for the versioned schema migration runner."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.domain.models.migration import Migration
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (
    AUTHORS_VERSION,
    BASELINE_VERSION,
    CATEGORIES_VERSION,
    MIGRATIONS,
    VOLUMES_VERSION,
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
            CATEGORIES_VERSION,
            VOLUMES_VERSION,
        ]
        assert runner.current_version(connection) == VOLUMES_VERSION


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
            CATEGORIES_VERSION,
            VOLUMES_VERSION,
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


def _seed_book_with_categories(
    database_path: Path, title: str, categories: tuple[Category, ...], source: str
) -> None:
    """Import one minimal real book carrying the given category hierarchy."""
    book = Book(
        information={"Name": title},
        categories=categories,
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / source,)
    )


def test_categories_migration_deduplicates_by_mjcn_across_books(tmp_path: Path) -> None:
    """Migration 3 builds one taxonomy row per distinct MJCN across all books."""
    database_path = tmp_path / "books.db"
    fiqh = Category(mjcn=9, name="Fiqh", parent_mjcn=0, sort_key=1)
    hadith = Category(mjcn=10, name="Hadith", parent_mjcn=0, sort_key=2)
    _seed_book_with_categories(database_path, "Book One", (fiqh,), "one.mjbz")
    _seed_book_with_categories(database_path, "Book Two", (fiqh, hadith), "two.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner = MigrationRunner(MIGRATIONS)
        applied = runner.migrate(connection)

        assert [migration.version for migration in applied] == [
            BASELINE_VERSION,
            AUTHORS_VERSION,
            CATEGORIES_VERSION,
            VOLUMES_VERSION,
        ]

        rows = connection.execute(
            "SELECT MJCN, Name, ParentMJCN FROM CategoryTaxonomy ORDER BY MJCN"
        ).fetchall()
        assert rows == [(9, "Fiqh", 0), (10, "Hadith", 0)]


def test_categories_migration_resolves_inconsistent_spelling_by_frequency(
    tmp_path: Path,
) -> None:
    """When the same MJCN has conflicting Name/ParentMJCN, the most common wins."""
    database_path = tmp_path / "books.db"
    majority_a = Category(mjcn=5, name="Common Name", parent_mjcn=1, sort_key=1)
    majority_b = Category(mjcn=5, name="Common Name", parent_mjcn=1, sort_key=1)
    minority = Category(mjcn=5, name="Rare Spelling", parent_mjcn=2, sort_key=1)
    _seed_book_with_categories(database_path, "Book One", (majority_a,), "one.mjbz")
    _seed_book_with_categories(database_path, "Book Two", (majority_b,), "two.mjbz")
    _seed_book_with_categories(database_path, "Book Three", (minority,), "three.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        row = connection.execute(
            "SELECT Name, ParentMJCN FROM CategoryTaxonomy WHERE MJCN = 5"
        ).fetchone()
        assert row == ("Common Name", 1)


def test_categories_migration_produces_no_rows_when_no_books_have_categories(
    tmp_path: Path,
) -> None:
    """A database with no categorized books gets an empty (but present) taxonomy."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        count = connection.execute("SELECT COUNT(*) FROM CategoryTaxonomy").fetchone()[0]
        assert count == 0


def test_volumes_migration_groups_books_sharing_a_base_title(tmp_path: Path) -> None:
    """Migration 4 groups titles like 'X جلد N' into one Series with volume numbers."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "کفایت المفتی جلد 1", None, "one.mjbz")
    _seed_book(database_path, "کفایت المفتی جلد 2", None, "two.mjbz")
    _seed_book(database_path, "کفایت المفتی جلد 3", None, "three.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner = MigrationRunner(MIGRATIONS)
        applied = runner.migrate(connection)

        assert [migration.version for migration in applied] == [
            BASELINE_VERSION,
            AUTHORS_VERSION,
            CATEGORIES_VERSION,
            VOLUMES_VERSION,
        ]

        series_rows = connection.execute("SELECT SeriesID, Title FROM Series").fetchall()
        assert series_rows == [(1, "کفایت المفتی")]

        rows = connection.execute(
            "SELECT Title, SeriesID, VolumeNumber FROM Books ORDER BY VolumeNumber"
        ).fetchall()
        assert rows == [
            ("کفایت المفتی جلد 1", 1, 1),
            ("کفایت المفتی جلد 2", 1, 2),
            ("کفایت المفتی جلد 3", 1, 3),
        ]


def test_volumes_migration_leaves_a_lone_volume_title_ungrouped(tmp_path: Path) -> None:
    """A title with a volume suffix but no sibling volumes gets no Series."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Some Book جلد 1", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        series_count = connection.execute("SELECT COUNT(*) FROM Series").fetchone()[0]
        assert series_count == 0

        row = connection.execute(
            "SELECT SeriesID, VolumeNumber FROM Books WHERE Title = 'Some Book جلد 1'"
        ).fetchone()
        assert row == (None, None)


def test_volumes_migration_leaves_non_volume_titles_untouched(tmp_path: Path) -> None:
    """A title with no volume suffix is left with SeriesID/VolumeNumber NULL."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "A Standalone Book", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        row = connection.execute(
            "SELECT SeriesID, VolumeNumber FROM Books WHERE Title = 'A Standalone Book'"
        ).fetchone()
        assert row == (None, None)
