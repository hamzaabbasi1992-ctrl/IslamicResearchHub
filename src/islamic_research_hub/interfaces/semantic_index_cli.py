"""Command-line interface for building a pilot semantic embedding index.

Indexes every page belonging to books under one root subject/category, so
the approach can be validated on a small slice of the library before
committing to embedding the full corpus. Requires the optional "ai"
dependency group (`pip install -e .[ai]`).
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
        description="Build a pilot semantic embedding index for one subject."
    )
    parser.add_argument("subject", help="Root category name to index, e.g. حدیث شریف")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Embed and index every page belonging to books under one subject."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    try:
        pages = _load_subject_pages(args.database, args.subject)
    except sqlite3.Error as error:
        LOGGER.error("Unable to read the master database: %s", error)
        return 1

    if not pages:
        print(f"No books found under subject: {args.subject}")
        return 0

    print(f"Found {len(pages)} pages to index under: {args.subject}")
    embedder = SentenceTransformerEmbedder()
    store = SqlitePageEmbeddingRepository(args.database)
    indexer = PageEmbeddingIndexer(embedder, store)

    try:
        indexed_count = indexer.index_pages(pages)
    except PageEmbeddingError as error:
        LOGGER.error("Indexing failed: %s", error)
        return 1

    print(f"Indexed {indexed_count} pages.")
    return 0


def _load_subject_pages(
    database_path: Path, subject: str
) -> tuple[tuple[int, int, str], ...]:
    """Return (book_id, page_number, content) for every page under one subject."""
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        books = connection.execute("SELECT BookID, Category FROM Books").fetchall()
        matching_book_ids = [
            book["BookID"]
            for book in books
            if _resolve_subject(connection, book["BookID"], book["Category"]) == subject
        ]
        if not matching_book_ids:
            return ()
        placeholders = ",".join("?" for _ in matching_book_ids)
        rows = connection.execute(
            f"SELECT BookID, PageNo, Content FROM Pages WHERE BookID IN ({placeholders})",
            matching_book_ids,
        ).fetchall()
        return tuple(
            (row["BookID"], row["PageNo"], row["Content"])
            for row in rows
            if row["Content"] and row["Content"].strip()
        )


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
