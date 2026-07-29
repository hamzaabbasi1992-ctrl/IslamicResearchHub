"""Command-line interface for populating the taxonomy system from existing normalized data.

Real, scoped Phase 8 work: migration 6 built the general nine-dimension
taxonomy schema, additive and empty. This populates the "subject" and
"author" dimensions from data that already exists (`CategoryTaxonomy`,
`Authors` - both built by earlier migrations), and links every real book
to its real subject(s)/author. Safe to re-run after new libraries are
imported - every step is idempotent.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.taxonomy_repository import (
    TaxonomyRepository,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Populate the taxonomy system's subject/author dimensions "
        "from existing normalized data, and link every real book to them."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Populate subject/author taxonomy terms and link every real book to them."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    repository = TaxonomyRepository(args.database)
    subject_count = repository.populate_subjects_from_category_taxonomy()
    author_count = repository.populate_authors_from_authors_table()
    subject_links, author_links = repository.link_books_to_populated_taxonomy()

    print(f"Database: {args.database}")
    print(f"Subject terms: {subject_count}")
    print(f"Author terms: {author_count}")
    print(f"Book-subject links: {subject_links}")
    print(f"Book-author links: {author_links}")
    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so any non-ASCII content in messages prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
