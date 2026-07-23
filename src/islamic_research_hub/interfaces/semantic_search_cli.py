"""Command-line interface for semantic (embedding-based) search.

Queries the pilot page embedding index built by semantic_index_cli. Requires
the optional "ai" dependency group (`pip install -e .[ai]`).
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult
from islamic_research_hub.infrastructure.ai.sentence_transformer_embedder import (
    SentenceTransformerEmbedder,
)
from islamic_research_hub.infrastructure.persistence.sqlite_page_embedding_repository import (
    PageEmbeddingError,
    SqlitePageEmbeddingRepository,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_LIMIT = 10


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Semantically search the pilot page embedding index."
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
    """Search the pilot embedding index and print ranked results."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    embedder = SentenceTransformerEmbedder()
    store = SqlitePageEmbeddingRepository(args.database)
    service = SemanticBookSearchService(embedder, store)

    try:
        results = service.search(args.query, args.limit, args.library)
    except ValueError as error:
        LOGGER.error("Invalid search request: %s", error)
        return 1
    except PageEmbeddingError as error:
        LOGGER.error("Search failed: %s", error)
        return 1

    _print_results(results)
    return 0


def _print_results(results: tuple[SemanticSearchResult, ...]) -> None:
    """Print ranked semantic search results, or a no-match message."""
    if not results:
        print("No matches found.")
        return
    for index, result in enumerate(results, start=1):
        title = result.title or "(untitled)"
        author = result.author or "Unknown"
        page = result.page_number if result.page_number is not None else "?"
        print(f"{index}. {title} — {author} (page {page}, similarity {result.similarity:.3f})")
        print(f"   {result.excerpt}")


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Persian search results print safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
