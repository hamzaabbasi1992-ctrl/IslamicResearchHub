"""Backfill `Paragraphs` (+ `ParagraphsFTS`/`ParagraphsFTSNormalized`) from
already-stored `Pages.Content` - no source files needed.

Every real page becomes at least one `Paragraph` row (`ParagraphIndex` 1).
Only where `Pages.Content` actually contains real "\\n"-separated lines -
Shamila Urdu's structure-preserving extraction (`shared/html_text_extraction.py`)
is the only reader that ever writes more than one line per page - does a
page get split into more than one paragraph. No book is ever credited
with paragraph granularity it doesn't have. `IsHeading` is set only where
a line literally starts with "## ", a real, checkable predicate.

Resume-safe via `INSERT OR REPLACE`, keyed on `Paragraphs`'
`UNIQUE(BookID, PageNo, ParagraphIndex)` constraint - re-running after a
future `strip_html_to_text()` improvement is always safe. Processes one
book's pages per commit (never one commit per row), matching this
project's other backfill CLIs.
"""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
_HEADING_PREFIX = "## "


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Backfill Paragraphs from already-stored Pages.Content."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument(
        "--library", default=None, help="Limit to one library's books (default: every library)"
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the backfill against the real database."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)
    return run(args)


def run(args: argparse.Namespace) -> int:
    """Split every real page's Content into Paragraph rows, one commit per book."""
    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    book_ids = _load_target_book_ids(args.database, args.library)
    print(f"{len(book_ids)} book(s) to process.")

    processed_books = 0
    written_paragraphs = 0
    multi_paragraph_pages = 0

    with closing(sqlite3.connect(args.database)) as connection:
        for book_id in book_ids:
            pages = connection.execute(
                "SELECT PageNo, Content FROM Pages WHERE BookID = ? AND Content IS NOT NULL",
                (book_id,),
            ).fetchall()

            rows: list[tuple[int, int, int, int, str]] = []
            for page_no, content in pages:
                paragraphs = _split_paragraphs(content)
                if len(paragraphs) > 1:
                    multi_paragraph_pages += 1
                for index, is_heading, text in paragraphs:
                    rows.append((book_id, page_no, index, is_heading, text))

            if rows:
                connection.executemany(
                    """
                    INSERT OR REPLACE INTO Paragraphs
                        (BookID, PageNo, ParagraphIndex, IsHeading, Content)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                connection.commit()
                written_paragraphs += len(rows)
            processed_books += 1

    print(
        f"Processed {processed_books}/{len(book_ids)} book(s): "
        f"{written_paragraphs} paragraph(s) written, "
        f"{multi_paragraph_pages} page(s) had real sub-page structure."
    )
    return 0


def _split_paragraphs(content: str) -> list[tuple[int, int, str]]:
    """Split one page's real content into (index, is_heading, text) triples.

    A page with no real "\\n"-separated lines (the overwhelming majority
    of the corpus - flat per-page text) becomes exactly one paragraph,
    honestly - not a fabricated split.
    """
    lines = [line for line in content.split("\n") if line.strip()]
    if not lines:
        return [(1, 0, content)]
    return [
        (index, 1 if line.startswith(_HEADING_PREFIX) else 0, line)
        for index, line in enumerate(lines, start=1)
    ]


def _load_target_book_ids(database_path: Path, library: str | None) -> list[int]:
    """Return every BookID to process, optionally limited to one library."""
    with closing(sqlite3.connect(database_path)) as connection:
        if library:
            rows = connection.execute(
                """
                SELECT b.BookID FROM Books b
                JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE l.Name = ?
                """,
                (library,),
            ).fetchall()
        else:
            rows = connection.execute("SELECT BookID FROM Books").fetchall()
    return [row[0] for row in rows]


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Urdu text prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
