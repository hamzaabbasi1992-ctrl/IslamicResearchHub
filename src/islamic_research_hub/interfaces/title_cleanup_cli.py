"""Command-line interface for cosmetically cleaning up filename-derived titles.

Does not recover real titles - only makes all-caps, underscore-style
filenames more readable. See shared/title_cleanup.py.
"""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.shared.logging_config import configure_logging
from islamic_research_hub.shared.title_cleanup import clean_filename_title

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Cosmetically clean up filename-derived titles for one or more libraries."
    )
    parser.add_argument(
        "--library",
        action="append",
        required=True,
        dest="libraries",
        help="Library name to clean up titles for (repeatable)",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Clean up titles in the given libraries and report how many changed."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    changed_count = 0
    with closing(sqlite3.connect(args.database)) as connection:
        placeholders = ",".join("?" for _ in args.libraries)
        rows = connection.execute(
            f"""
            SELECT b.BookID, b.Title FROM Books b
            JOIN Libraries l ON l.LibraryID = b.LibraryID
            WHERE l.Name IN ({placeholders}) AND b.Title IS NOT NULL
            """,
            args.libraries,
        ).fetchall()

        updates = []
        for book_id, title in rows:
            cleaned = clean_filename_title(title)
            if cleaned != title:
                updates.append((cleaned, book_id))

        connection.executemany("UPDATE Books SET Title = ? WHERE BookID = ?", updates)
        connection.commit()
        changed_count = len(updates)

    print(f"Books scanned: {len(rows)}")
    print(f"Titles cleaned up: {changed_count}")
    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Urdu titles print safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
