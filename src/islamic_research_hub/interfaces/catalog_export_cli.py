"""Command-line interface for exporting a lightweight, metadata-only
catalog of every real book - the file the Android companion app's
catalog browse/search screen loads (Phase 18 Milestone 1).

Real per-book page content is deliberately excluded - a phone can't
hold this project's 100GB+ corpus, so this file only ever needs to be
small enough to ship whole to a device. Writes a real, self-contained
SQLite file (not JSON) so the mobile side can query it directly with
its own embedded SQLite engine, no serialization layer needed.
"""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.shared.category_names import CATEGORY_NAME_TRANSLATIONS
from islamic_research_hub.shared.logging_config import configure_logging

MOBILE_CATEGORY_DISPLAY_LANGUAGE = "ur"
"""Which `CATEGORY_NAME_TRANSLATIONS` language the mobile Categories tab
ships - this library's primary audience/UI language (matches the
reference app's own Urdu category screen). `CategoryNameEntity` on the
Android side carries one display name, not a per-language map, so this
is resolved once here rather than shipping every language to the phone."""

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_OUTPUT_PATH = Path("data/exports/catalog.db")
"""Mirrors `database_backup.py`'s `DEFAULT_BACKUP_FOLDER = Path("data/backups")`
convention - a real, predictable `data/<subfolder>` default."""

MOBILE_ROOM_SCHEMA_VERSION = 1
"""Must match `@Database(version = ...)` on the Android side
(`CatalogDatabase.kt`). See the identical constant/docstring in
`book_package_export_cli.py` for why this is required - the same fix
for the same confirmed Room prepackaged-database crash applies to both
exported file types."""


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Export a lightweight, metadata-only catalog of every real book "
            "(no page content) for the Android companion app."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to write the catalog file (default: {DEFAULT_OUTPUT_PATH})",
    )
    return parser


def export_catalog_to_file(database_path: Path, output_path: Path) -> tuple[int, int, float]:
    """Export a lightweight catalog database for mobile directly to output_path."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    with closing(sqlite3.connect(database_path)) as source:
        libraries = source.execute("SELECT LibraryID, Name FROM Libraries").fetchall()
        if _has_series_columns(source):
            books = source.execute(
                """
                SELECT BookID, LibraryID, Title, Author, Publisher, Language, Category,
                       PageCount, ChapterCount, PublishYear, SeriesID, VolumeNumber
                FROM Books
                """
            ).fetchall()
        else:
            books = source.execute(
                """
                SELECT BookID, LibraryID, Title, Author, Publisher, Language, Category,
                       PageCount, ChapterCount, PublishYear, NULL, NULL
                FROM Books
                """
            ).fetchall()
        category_names, book_categories = _read_real_categories(source)

    with closing(sqlite3.connect(output_path)) as destination:
        _create_schema(destination)
        destination.execute(f"PRAGMA user_version = {MOBILE_ROOM_SCHEMA_VERSION}")
        destination.executemany(
            "INSERT INTO Libraries (LibraryID, Name) VALUES (?, ?)", libraries
        )
        destination.executemany(
            """
            INSERT INTO Books (
                BookID, LibraryID, Title, Author, Publisher, Language, Category,
                PageCount, ChapterCount, PublishYear, SeriesID, VolumeNumber
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            books,
        )
        destination.executemany(
            "INSERT INTO CategoryNames (MJCN, Name, ParentMJCN) VALUES (?, ?, ?)",
            category_names,
        )
        destination.executemany(
            "INSERT INTO BookCategories (BookID, MJCN) VALUES (?, ?)", book_categories
        )
        destination.commit()

    output_size_mb = output_path.stat().st_size / 1_048_576
    return len(libraries), len(books), output_size_mb


def _read_real_categories(
    connection: sqlite3.Connection,
) -> tuple[list[tuple[int, str, int | None]], list[tuple[int, int]]]:
    """Return (real named categories, real book<->category links) for the
    mobile Categories tab.

    Deliberately NOT `Books.Category` (that free-text column is mostly
    empty - 32,485 of 36,249 real rows on the actual production database
    - and where populated, is often a bare MJCN number or a library-
    internal slug, not something to show a user). The real, cross-
    library category names live in `CategoryTaxonomy` (added by
    migration 3); `Categories` is the real per-book membership table.
    Joining them and excluding purely-numeric names is the exact same
    real-data discipline `BookBrowserRepository.get_category_tree()`
    already applies for the desktop's own category browser - mirrored
    here rather than reused directly since that method returns a typed
    `CategoryNode` tree, not export-ready rows.

    Returns empty lists (not an error) when `CategoryTaxonomy` doesn't
    exist yet (e.g. a database that hasn't run migration 3) - the mobile
    Categories tab then just shows nothing to browse, same honest
    degradation `_has_series_columns` already models for `SeriesID`.
    """
    if not _table_exists(connection, "CategoryTaxonomy") or not _table_exists(
        connection, "Categories"
    ):
        return [], []

    raw_category_names = connection.execute(
        "SELECT MJCN, Name, ParentMJCN FROM CategoryTaxonomy WHERE Name GLOB '*[^0-9]*'"
    ).fetchall()
    category_names = [
        (mjcn, _display_category_name(name), parent_mjcn)
        for mjcn, name, parent_mjcn in raw_category_names
    ]
    real_mjcns = {row[0] for row in raw_category_names}
    if not real_mjcns:
        return [], []

    book_categories = connection.execute(
        "SELECT DISTINCT BookID, MJCN FROM Categories WHERE MJCN IS NOT NULL"
    ).fetchall()
    book_categories = [(book_id, mjcn) for book_id, mjcn in book_categories if mjcn in real_mjcns]
    return category_names, book_categories


def _display_category_name(canonical_name: str) -> str:
    """Resolve one `CategoryTaxonomy.Name` (a canonical, often English-
    slug-shaped key like "ahkaam" or "seerat-o-sawanih") to the real
    display name the mobile Categories tab shows, in
    `MOBILE_CATEGORY_DISPLAY_LANGUAGE`. Falls back to the raw canonical
    name (rather than dropping the category) for any name not yet in
    `CATEGORY_NAME_TRANSLATIONS` - confirmed all 32 real categories on
    the production database have a translation today, but a future new
    category shouldn't silently vanish from the export just because its
    translation hasn't been added yet.
    """
    translations = CATEGORY_NAME_TRANSLATIONS.get(canonical_name)
    if translations is None:
        return canonical_name
    return translations.get(MOBILE_CATEGORY_DISPLAY_LANGUAGE, canonical_name)


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)
    ).fetchone()
    return row is not None


def main(arguments: Sequence[str] | None = None) -> int:
    """Export the real catalog and print a real row-count/size summary."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    try:
        num_libs, num_books, size_mb = export_catalog_to_file(args.database, args.output)
    except Exception as err:
        LOGGER.error("Catalog export failed: %s", err)
        return 1

    print("Catalog Export Summary")
    print(f"Libraries: {num_libs}")
    print(f"Books: {num_books}")
    print(f"Output: {args.output} ({size_mb:.1f} MB)")
    return 0


def _has_series_columns(connection: sqlite3.Connection) -> bool:
    """Return whether Books.SeriesID/VolumeNumber exist yet - added by a
    later migration, so a database that hasn't run it (e.g. a freshly
    imported test database) doesn't have them. Mirrors
    `BookBrowserRepository._has_series_support()`'s exact guard."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)")}
    return "SeriesID" in columns


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE Libraries (
            LibraryID INTEGER NOT NULL PRIMARY KEY,
            Name TEXT NOT NULL
        );
        CREATE TABLE Books (
            BookID INTEGER NOT NULL PRIMARY KEY,
            LibraryID INTEGER,
            Title TEXT,
            Author TEXT,
            Publisher TEXT,
            Language TEXT,
            Category TEXT,
            PageCount INTEGER,
            ChapterCount INTEGER,
            PublishYear TEXT,
            SeriesID INTEGER,
            VolumeNumber INTEGER
        );
        CREATE TABLE CategoryNames (
            MJCN INTEGER NOT NULL PRIMARY KEY,
            Name TEXT NOT NULL,
            ParentMJCN INTEGER
        );
        CREATE TABLE BookCategories (
            BookID INTEGER NOT NULL,
            MJCN INTEGER NOT NULL,
            PRIMARY KEY (BookID, MJCN)
        );
        """
    )


def _configure_unicode_output() -> None:
    """Use UTF-8 output so real Arabic/Urdu titles print safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
