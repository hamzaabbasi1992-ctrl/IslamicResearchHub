"""Command-line interface for full-text search over the master book database."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
    BookSearchError,
    SqliteBookSearchRepository,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_LIMIT = 20


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Search the master book database for matching pages."
    )
    parser.add_argument("query", help="Free-text search query")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Maximum number of results to return (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--library",
        default=None,
        help="Restrict results to one library name (default: search all libraries)",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Search the master database and print ranked results."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)
    service = BookSearchService(SqliteBookSearchRepository(args.database))

    try:
        results = service.search(args.query, args.limit, args.library)
    except ValueError as error:
        LOGGER.error("Invalid search request: %s", error)
        return 1
    except BookSearchError as error:
        LOGGER.error("Search failed: %s", error)
        return 1

    _print_results(results)
    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Persian search results print safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _print_results(results: tuple[SearchResult, ...]) -> None:
    """Print ranked search results, or a no-match message."""
    if not results:
        print("No matches found.")
        return

    for index, result in enumerate(results, start=1):
        title = result.title or "(untitled)"
        author = result.author or "Unknown"
        page = result.page_number if result.page_number is not None else "?"
        library = result.library or "Unknown library"
        print(f"{index}. {title} — {author} (page {page}) [{library}]")
        print(f"   {result.excerpt}")


if __name__ == "__main__":
    raise SystemExit(main())
