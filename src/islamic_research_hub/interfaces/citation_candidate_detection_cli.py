"""Detect and store real citation candidates between owned books.

Requires `PagesFTSNormalized`/`Paragraphs` to already exist (run
`MigrationRunner` first, if not already applied). Real measured runtime
against the full production corpus (~83,763 anchors): 15 minutes (warm OS
page cache) to 2+ hours (cold cache) - disk speed and cache warmth vary
per machine, so run with `--sample` first to measure real timing on the
target machine before committing to a full run.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.citation_candidate_repository import (
    CitationCandidateRepository,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Detect and store real citation candidates between owned books."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        metavar="N",
        help="Time N real anchors and extrapolate total runtime, without writing anything.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run detection against the real database."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)
    return run(args)


def run(args: argparse.Namespace) -> int:
    """Run a `--sample` timing measurement, or the full detection pass."""
    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    repository = CitationCandidateRepository(args.database)

    if args.sample is not None:
        result = repository.time_sample(args.sample)
        if result.total_anchors == 0:
            print("No anchors found (unmigrated database, or no eligible titles).")
            return 0
        print(
            f"Sampled {result.sampled}/{result.total_anchors} anchor(s) in "
            f"{result.elapsed_seconds:.1f}s -> estimated full run: "
            f"{result.estimated_total_seconds / 60:.1f} minute(s)."
        )
        return 0

    def _report_progress(done: int, total: int) -> None:
        print(f"  {done}/{total} anchors processed...", end="\r")

    count = repository.detect_and_store(progress_callback=_report_progress)
    print(f"\nCitation candidate detection complete: {count} candidate(s) found.")
    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Urdu text prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
