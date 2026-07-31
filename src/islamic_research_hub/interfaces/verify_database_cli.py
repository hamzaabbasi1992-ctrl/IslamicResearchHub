"""Command-line interface for verifying the master database's integrity.

Also the project's diagnostics command: reports real corpus-wide counts
(books/pages/paragraphs/authors/categories/FTS index sizes) alongside the
integrity issues `DatabaseVerifier` finds (orphan records, duplicate IDs,
missing metadata, FTS sync, taxonomy quality, SQLite-level corruption) -
one combined report rather than two overlapping tools.
"""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.database_verifier import DatabaseVerifier
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")

_STATS_QUERIES: tuple[tuple[str, str], ...] = (
    ("Books", "SELECT COUNT(*) FROM Books"),
    ("Pages", "SELECT COUNT(*) FROM Pages"),
    ("Paragraphs", "SELECT COUNT(*) FROM Paragraphs"),
    ("Authors", "SELECT COUNT(*) FROM Authors"),
    ("Categories (taxonomy)", "SELECT COUNT(*) FROM CategoryTaxonomy"),
    ("Libraries", "SELECT COUNT(*) FROM Libraries"),
    ("PagesFTS rows", "SELECT COUNT(*) FROM PagesFTS"),
    ("ParagraphsFTS rows", "SELECT COUNT(*) FROM ParagraphsFTS"),
    ("BooksFTS rows", "SELECT COUNT(*) FROM BooksFTS"),
    ("FootnotesFTS rows", "SELECT COUNT(*) FROM FootnotesFTS"),
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Verify the master database's integrity.")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run every integrity check and print a report. Exits non-zero if errors are found."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    print(f"Checked: {args.database}")
    print()
    print("Corpus statistics:")
    for label, count in _collect_stats(args.database):
        print(f"  {label}: {count}")

    print()
    report = DatabaseVerifier(args.database).verify()
    print(f"Errors: {report.error_count}")
    print(f"Warnings: {report.warning_count}")
    for issue in report.issues:
        print(f"  [{issue.severity.upper()}] {issue.category}: {issue.message}")

    if not report.issues:
        print("Database is healthy.")
    elif report.is_healthy:
        print("No errors found (see warnings above).")

    return 0 if report.is_healthy else 1


def _collect_stats(database_path: Path) -> list[tuple[str, int | str]]:
    """Return real corpus-wide counts, skipping any table that doesn't exist
    yet (e.g. a database that hasn't run every migration) rather than
    failing the whole report over one missing optional table."""
    stats: list[tuple[str, int | str]] = []
    with closing(sqlite3.connect(database_path)) as connection:
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for label, query in _STATS_QUERIES:
            table_name = query.rsplit("FROM ", 1)[1]
            if table_name not in existing_tables:
                stats.append((label, "not migrated yet"))
                continue
            stats.append((label, connection.execute(query).fetchone()[0]))
    return stats


def _configure_unicode_output() -> None:
    """Use UTF-8 output so any non-ASCII content in messages prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
