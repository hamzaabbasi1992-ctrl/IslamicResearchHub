"""Versioned schema migrations for the master database.

Uses SQLite's own `PRAGMA user_version` as the version counter, so no extra
tracking table is needed. Migration 1 is deliberately a no-op: it adopts the
schema `MasterBookRepository` already creates (Libraries, Books, Categories,
Chapters, Pages, PagesFTS) as the migration baseline, without re-declaring
any of it, so existing databases (at version 0) can be tagged version 1
without risk. Real structural changes start at version 2.
"""

import logging
import sqlite3
from collections import Counter

from islamic_research_hub.domain.models.migration import Migration

LOGGER = logging.getLogger(__name__)


def _adopt_existing_schema(connection: sqlite3.Connection) -> None:
    """No-op: the schema at this version already exists, created elsewhere."""


def _normalize_authors(connection: sqlite3.Connection) -> None:
    """Add a real Authors entity, backfilled from the existing free-text column.

    `Books.Author` (free text) is left untouched - search and the web app
    read it directly and must keep working unmodified. `Books.AuthorID` is
    additive: NULL wherever `Author` is NULL/empty, and only used by future
    features (author browsing/filtering) built on top of this.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Authors (
            AuthorID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL UNIQUE
        )
        """
    )
    connection.execute(
        "ALTER TABLE Books ADD COLUMN AuthorID INTEGER REFERENCES Authors(AuthorID)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_books_author_id ON Books(AuthorID)")

    connection.execute(
        """
        INSERT OR IGNORE INTO Authors (Name)
        SELECT DISTINCT TRIM(Author) FROM Books
        WHERE Author IS NOT NULL AND TRIM(Author) != ''
        """
    )
    connection.execute(
        """
        UPDATE Books
        SET AuthorID = (
            SELECT AuthorID FROM Authors WHERE Authors.Name = TRIM(Books.Author)
        )
        WHERE Books.Author IS NOT NULL AND TRIM(Books.Author) != ''
        """
    )


def _pick_canonical(counter: Counter) -> object:
    """Return the most frequent value, tie-broken by the smallest value."""
    max_count = max(counter.values())
    candidates = sorted(value for value, count in counter.items() if count == max_count)
    return candidates[0]


def _normalize_categories(connection: sqlite3.Connection) -> None:
    """Add a cross-library category taxonomy, deduplicated from per-book rows.

    The per-book `Categories` table (BookID, MJCN, ParentMJCN, Name, SortKey)
    is left completely untouched - nothing downstream reads it outside the
    existing category-chain-to-subject logic, which keeps working unmodified.
    `MJCN` is shared across the two Jibreel libraries (same source
    classification scheme), so one taxonomy row per distinct MJCN is a real
    cross-library category, not a per-library duplicate. A handful of MJCN
    codes have inconsistent Name spelling or ParentMJCN across books (found
    by inspecting the real data); the most frequent value wins, tie-broken
    deterministically by the smallest value.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS CategoryTaxonomy (
            MJCN INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            ParentMJCN INTEGER
        )
        """
    )

    names_by_mjcn: dict[int, Counter] = {}
    parents_by_mjcn: dict[int, Counter] = {}
    for mjcn, name, parent_mjcn in connection.execute(
        "SELECT MJCN, Name, ParentMJCN FROM Categories"
    ):
        names_by_mjcn.setdefault(mjcn, Counter())[name] += 1
        parents_by_mjcn.setdefault(mjcn, Counter())[parent_mjcn] += 1

    connection.executemany(
        "INSERT OR IGNORE INTO CategoryTaxonomy (MJCN, Name, ParentMJCN) VALUES (?, ?, ?)",
        (
            (mjcn, _pick_canonical(names_by_mjcn[mjcn]), _pick_canonical(parents_by_mjcn[mjcn]))
            for mjcn in sorted(names_by_mjcn)
        ),
    )


BASELINE_VERSION = 1
AUTHORS_VERSION = 2
CATEGORIES_VERSION = 3

MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        BASELINE_VERSION,
        "Adopt the existing Libraries/Books/Categories/Chapters/Pages/PagesFTS "
        "schema as the migration baseline.",
        _adopt_existing_schema,
    ),
    Migration(
        AUTHORS_VERSION,
        "Add a normalized Authors table and Books.AuthorID, backfilled from "
        "the existing Books.Author free-text column.",
        _normalize_authors,
    ),
    Migration(
        CATEGORIES_VERSION,
        "Add a cross-library CategoryTaxonomy table, deduplicated by MJCN "
        "from the existing per-book Categories table.",
        _normalize_categories,
    ),
)


class MigrationRunner:
    """Apply pending versioned migrations to a database, in order."""

    def __init__(self, migrations: tuple[Migration, ...] = MIGRATIONS) -> None:
        versions = [migration.version for migration in migrations]
        if len(versions) != len(set(versions)):
            raise ValueError("Migration versions must be unique.")
        self._migrations = tuple(sorted(migrations, key=lambda migration: migration.version))

    @staticmethod
    def current_version(connection: sqlite3.Connection) -> int:
        """Return the database's current schema version."""
        row = connection.execute("PRAGMA user_version").fetchone()
        return row[0]

    def pending_migrations(self, connection: sqlite3.Connection) -> tuple[Migration, ...]:
        """Return every migration newer than the database's current version."""
        current = self.current_version(connection)
        return tuple(migration for migration in self._migrations if migration.version > current)

    def migrate(self, connection: sqlite3.Connection) -> tuple[Migration, ...]:
        """Apply every pending migration in order, returning those applied."""
        applied: list[Migration] = []
        for migration in self.pending_migrations(connection):
            with connection:
                migration.apply(connection)
                connection.execute(f"PRAGMA user_version = {migration.version}")
            LOGGER.info(
                "Applied migration %d: %s", migration.version, migration.description
            )
            applied.append(migration)
        return tuple(applied)
