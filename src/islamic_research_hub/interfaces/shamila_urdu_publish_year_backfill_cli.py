"""Backfill Books.PublishYear for Shamila Urdu books imported before it was captured.

`ShamilaUrduBookReader` now reads "Publish Year" from each book's own
metadata table (real data: 72.5% of a random sample had one), but books
imported before that change never got it. Unlike the Jibreel PDF-hint
backfill, no decryption is needed here - Shamila Urdu's source files are
plain, unencrypted SQLite - so this reads `Books.Source` directly. Resume-
safe: only books with PublishYear IS NULL are considered, and a source file
that no longer exists on disk is skipped, not fatal.
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
DEFAULT_LIBRARY = "Maktaba Shamila Urdu"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Backfill Books.PublishYear for already-imported Shamila Urdu books."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--library", default=DEFAULT_LIBRARY)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the backfill against the real database."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)
    return run(args)


def run(args: argparse.Namespace) -> int:
    """Read each book's own source file and store its real Publish Year."""
    targets = _load_targets(args.database, args.library)
    print(f"{len(targets)} book(s) need a Publish Year.")

    found_count = 0
    missing_source_count = 0
    hints: list[tuple[str, int]] = []
    for book_id, source in targets:
        source_path = Path(source)
        if not source_path.is_file():
            missing_source_count += 1
            continue
        year = _read_publish_year(source_path)
        if year:
            hints.append((year, book_id))
            found_count += 1

    if hints:
        with closing(sqlite3.connect(args.database)) as connection:
            connection.executemany("UPDATE Books SET PublishYear = ? WHERE BookID = ?", hints)
            connection.commit()

    print(f"Found: {found_count}, source file missing: {missing_source_count}.")
    print(f"Done. {found_count}/{len(targets)} book(s) got a real Publish Year.")
    return 0


def _load_targets(database_path: Path, library: str) -> list[tuple[int, str]]:
    """Return (BookID, Source) pairs still missing a Publish Year."""
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT b.BookID, b.Source FROM Books b
            JOIN Libraries l ON l.LibraryID = b.LibraryID
            WHERE l.Name = ? AND b.PublishYear IS NULL
            """,
            (library,),
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def _read_publish_year(source_path: Path) -> str | None:
    """Return the real Publish Year from one book's own metadata table, if any."""
    try:
        with closing(
            sqlite3.connect(f"{source_path.resolve().as_uri()}?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(
                "SELECT fieldValue FROM metadata WHERE fieldName = 'Publish Year'"
            ).fetchone()
    except sqlite3.Error:
        LOGGER.warning("Could not read metadata from %s", source_path)
        return None
    if row is None or row[0] is None:
        return None
    value = str(row[0]).strip()
    return value or None


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Urdu text prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
