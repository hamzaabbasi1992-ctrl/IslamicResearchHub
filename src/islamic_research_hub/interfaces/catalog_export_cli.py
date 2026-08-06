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

from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_OUTPUT_PATH = Path("data/exports/catalog.db")
"""Mirrors `database_backup.py`'s `DEFAULT_BACKUP_FOLDER = Path("data/backups")`
convention - a real, predictable `data/<subfolder>` default."""


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


def main(arguments: Sequence[str] | None = None) -> int:
    """Export the real catalog and print a real row-count/size summary."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.unlink(missing_ok=True)

    with closing(sqlite3.connect(args.database)) as source:
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

    with closing(sqlite3.connect(args.output)) as destination:
        _create_schema(destination)
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
        destination.commit()

    output_size_mb = args.output.stat().st_size / 1_048_576
    print("Catalog Export Summary")
    print(f"Libraries: {len(libraries)}")
    print(f"Books: {len(books)}")
    print(f"Output: {args.output} ({output_size_mb:.1f} MB)")
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
            LibraryID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL
        );
        CREATE TABLE Books (
            BookID INTEGER PRIMARY KEY,
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
