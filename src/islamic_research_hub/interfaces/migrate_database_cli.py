"""Command-line interface for applying versioned migrations to the master database."""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Apply pending schema migrations to the master database."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Apply every pending migration and print what ran."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    runner = MigrationRunner()
    with closing(sqlite3.connect(args.database)) as connection:
        starting_version = runner.current_version(connection)
        applied = runner.migrate(connection)
        ending_version = runner.current_version(connection)

    print(f"Database: {args.database}")
    print(f"Version before: {starting_version}")
    if not applied:
        print("Already up to date. No migrations applied.")
    else:
        for migration in applied:
            print(f"  Applied {migration.version}: {migration.description}")
    print(f"Version after: {ending_version}")
    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so any non-ASCII content in messages prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
