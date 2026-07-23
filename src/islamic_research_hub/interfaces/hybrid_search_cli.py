"""Command-line interface for fused keyword + semantic search.

Falls back to keyword-only results when the optional "ai" dependency group
is not installed, or when a page simply is not covered by the (currently
pilot-scale) embedding index.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.hybrid_search import HybridSearchService
from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.domain.models.hybrid_search_result import HybridSearchResult
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
        description="Search using both keyword and semantic matching, fused into one ranking."
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
    parser.add_argument(
        "--keyword-only",
        action="store_true",
        help="Skip semantic search even if the ai extra is installed",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Search with fused keyword + semantic ranking and print results."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    keyword_service = BookSearchService(SqliteBookSearchRepository(args.database))
    semantic_service = None if args.keyword_only else _build_semantic_service(args.database)
    service = HybridSearchService(keyword_service, semantic_service)

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


def _build_semantic_service(database_path: Path) -> SemanticBookSearchService | None:
    """Build the semantic search service, or None if the ai extra isn't installed."""
    try:
        from islamic_research_hub.infrastructure.ai.sentence_transformer_embedder import (
            SentenceTransformerEmbedder,
        )
        from islamic_research_hub.infrastructure.persistence.sqlite_page_embedding_repository import (
            SqlitePageEmbeddingRepository,
        )
    except ImportError:
        LOGGER.info(
            "Semantic search unavailable (install with `pip install -e .[ai]`); "
            "running keyword-only."
        )
        return None
    return SemanticBookSearchService(
        SentenceTransformerEmbedder(), SqlitePageEmbeddingRepository(database_path)
    )


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Persian search results print safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _print_results(results: tuple[HybridSearchResult, ...]) -> None:
    """Print fused, ranked results, or a no-match message."""
    if not results:
        print("No matches found.")
        return
    for index, result in enumerate(results, start=1):
        title = result.title or "(untitled)"
        author = result.author or "Unknown"
        page = result.page_number if result.page_number is not None else "?"
        library = result.library or "Unknown library"
        matched_by = "+".join(result.matched_by)
        print(
            f"{index}. {title} — {author} (page {page}) [{library}] "
            f"(matched by: {matched_by}, score {result.score:.4f})"
        )
        print(f"   {result.excerpt}")


if __name__ == "__main__":
    raise SystemExit(main())
