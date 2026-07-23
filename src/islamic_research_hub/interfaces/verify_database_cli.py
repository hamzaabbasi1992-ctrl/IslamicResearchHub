"""Command-line interface for verifying the master database's integrity."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.database_verifier import DatabaseVerifier
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")


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

    report = DatabaseVerifier(args.database).verify()
    print(f"Checked: {args.database}")
    print(f"Errors: {report.error_count}")
    print(f"Warnings: {report.warning_count}")
    for issue in report.issues:
        print(f"  [{issue.severity.upper()}] {issue.category}: {issue.message}")

    if not report.issues:
        print("Database is healthy.")
    elif report.is_healthy:
        print("No errors found (see warnings above).")

    return 0 if report.is_healthy else 1


def _configure_unicode_output() -> None:
    """Use UTF-8 output so any non-ASCII content in messages prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
