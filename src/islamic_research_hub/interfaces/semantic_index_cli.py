"""Command-line interface for building a pilot semantic embedding index.

Indexes real page content, optionally restricted to one root subject/
category so the approach can be validated (or run) on a slice of the
library at a time instead of the whole corpus in one go. Requires the
optional "ai" dependency group (`pip install -e .[ai]`).

Resume-safe by construction: every page already present in
`PageEmbeddings` is skipped automatically (see `_load_pages_to_index`),
so re-running the exact same command after an interruption (crash, power
loss, deliberate stop) picks up where it left off instead of re-embedding
already-done work. `--limit` runs one deliberately bounded batch and
exits cleanly, for splitting a large indexing job into several sessions.
"""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.application.page_embedding import PageEmbeddingIndexer
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


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Build or resume the pilot semantic embedding index."
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="Root category name to restrict indexing to, e.g. حدیث شریف. "
        "Omit to index every book in the corpus.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of not-yet-indexed pages to embed in this run. "
        "Omit to process everything remaining. Already-indexed pages are "
        "always skipped, so running this again later (with the same "
        "--subject) continues rather than restarting.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Embed and index real pages, skipping any already indexed."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    store = SqlitePageEmbeddingRepository(args.database)
    store.ensure_schema()

    try:
        pages = _load_pages_to_index(args.database, args.subject, args.limit)
    except sqlite3.Error as error:
        LOGGER.error("Unable to read the master database: %s", error)
        return 1

    scope = f'subject "{args.subject}"' if args.subject else "the full corpus"
    if not pages:
        print(f"Nothing to index for {scope} - every matching page is already embedded.")
        return 0

    print(f"Found {len(pages)} not-yet-indexed page(s) to embed ({scope}).")
    embedder = SentenceTransformerEmbedder()
    indexer = PageEmbeddingIndexer(embedder, store)

    try:
        indexed_count = indexer.index_pages(pages)
    except PageEmbeddingError as error:
        LOGGER.error("Indexing failed: %s", error)
        return 1

    print(f"Indexed {indexed_count} page(s) this run.")
    return 0


def _load_pages_to_index(
    database_path: Path, subject: str | None, limit: int | None
) -> tuple[tuple[int, int, str], ...]:
    """Return (book_id, page_number, content) for real pages still needing an embedding.

    Restricted to books under `subject` (a root category name) when
    given; every book in the corpus otherwise. Pages already present in
    `PageEmbeddings` are always excluded (the resume/skip behavior), and
    `limit` - when given - caps how many new pages this call returns, for
    deliberately batched runs.
    """
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        if subject is None:
            matching_book_ids = [
                row["BookID"] for row in connection.execute("SELECT BookID FROM Books")
            ]
        else:
            books = connection.execute("SELECT BookID, Category FROM Books").fetchall()
            matching_book_ids = [
                book["BookID"]
                for book in books
                if _resolve_subject(connection, book["BookID"], book["Category"]) == subject
            ]
        if not matching_book_ids:
            return ()

        placeholders = ",".join("?" for _ in matching_book_ids)
        query = f"""
            SELECT Pages.BookID, Pages.PageNo, Pages.Content
            FROM Pages
            WHERE Pages.BookID IN ({placeholders})
              AND Pages.Content IS NOT NULL
              AND TRIM(Pages.Content) != ''
              AND NOT EXISTS (
                  SELECT 1 FROM PageEmbeddings pe
                  WHERE pe.BookID = Pages.BookID AND pe.PageNo = Pages.PageNo
              )
        """
        parameters: list[object] = list(matching_book_ids)
        if limit is not None:
            query += " LIMIT ?"
            parameters.append(limit)

        rows = connection.execute(query, parameters).fetchall()
        return tuple((row["BookID"], row["PageNo"], row["Content"]) for row in rows)


def _resolve_subject(
    connection: sqlite3.Connection, book_id: int, category_value: str | None
) -> str | None:
    """Resolve one book's root category name by walking its stored category chain."""
    if category_value is None:
        return None
    try:
        category_id = int(category_value)
    except ValueError:
        return None

    rows = connection.execute(
        "SELECT MJCN, ParentMJCN, Name FROM Categories WHERE BookID = ?",
        (book_id,),
    ).fetchall()
    by_id = {row["MJCN"]: row for row in rows if row["MJCN"] is not None}
    node = by_id.get(category_id)
    if node is None:
        return None

    visited: set[int] = set()
    while (
        node["ParentMJCN"] is not None
        and node["ParentMJCN"] in by_id
        and node["MJCN"] not in visited
    ):
        visited.add(node["MJCN"])
        node = by_id[node["ParentMJCN"]]
    return node["Name"]


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Persian text prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
