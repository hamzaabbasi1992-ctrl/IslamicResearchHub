"""Re-extract already-imported Shamila Urdu page/footnote content with the
new structure-preserving `strip_html_to_text()` (headings promoted to their
own "## " line, embedded Arabic-script quotations wrapped in guillemets -
see `shared/html_text_extraction.py`).

Only affects already-imported books - a fresh import already gets the new
format directly. Real urgency: this reads from each book's own source file
(`Books.Source`, unchanged since import), which for this corpus only still
exists because of this session's own scratch extraction; a future session
would have no way to recover it.

Re-reads each book with the same reader class its Source path indicates
(`Books/`, `Hadith/`, or `Quran/` folder - all three of Shamila Urdu's real
schemas), then updates only `Pages.Content`, `Footnotes.FootnoteText`, and
(since migration 14) `Pages.HadeesNumber`/`Pages.AyahNumber` for existing
rows, matched by (BookID, PageNo) - never touches Chapters, Categories, or
any other table, and never inserts/deletes a row. The two number columns
piggyback on this same re-read pass rather than getting their own CLI,
since `ShamilaUrduHadithReader`/`ShamilaUrduQuranReader` now capture them
directly and every book here is already being re-read anyway.
"""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.shamila_urdu_book_reader import (
    ShamilaUrduBookReadError,
    ShamilaUrduBookReader,
)
from islamic_research_hub.infrastructure.persistence.shamila_urdu_hadith_reader import (
    ShamilaUrduHadithReadError,
    ShamilaUrduHadithReader,
)
from islamic_research_hub.infrastructure.persistence.shamila_urdu_quran_reader import (
    ShamilaUrduQuranReadError,
    ShamilaUrduQuranReader,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_LIBRARY = "Maktaba Shamila Urdu"

_BOOK_READER = ShamilaUrduBookReader()
_HADITH_READER = ShamilaUrduHadithReader()
_QURAN_READER = ShamilaUrduQuranReader()
_READ_ERRORS = (ShamilaUrduBookReadError, ShamilaUrduHadithReadError, ShamilaUrduQuranReadError)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Re-extract already-imported Shamila Urdu content with structure preserved."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--library", default=DEFAULT_LIBRARY)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the reformat against the real database."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)
    return run(args)


def run(args: argparse.Namespace) -> int:
    """Re-read each book from its own source file and update its stored content."""
    targets = _load_targets(args.database, args.library)
    print(f"{len(targets)} book(s) to reformat.")

    updated_books = 0
    updated_pages = 0
    updated_footnotes = 0
    updated_hadees_numbers = 0
    updated_ayah_numbers = 0
    missing_source_count = 0
    read_error_count = 0

    with closing(sqlite3.connect(args.database)) as connection:
        for book_id, source in targets:
            source_path = Path(source)
            if not source_path.is_file():
                missing_source_count += 1
                continue

            reader = _reader_for(source_path)
            try:
                book = reader.read(source_path)
            except _READ_ERRORS:
                LOGGER.warning("Could not re-read: %s", source_path)
                read_error_count += 1
                continue

            page_updates = [
                (page.content_f, book_id, page.page_number)
                for page in book.pages
                if page.content_f is not None
            ]
            footnote_updates = [
                (page.footnote, book_id, page.page_number)
                for page in book.pages
                if page.footnote is not None
            ]
            hadees_number_updates = [
                (page.hadees_number, book_id, page.page_number)
                for page in book.pages
                if page.hadees_number is not None
            ]
            ayah_number_updates = [
                (page.ayah_number, book_id, page.page_number)
                for page in book.pages
                if page.ayah_number is not None
            ]
            connection.executemany(
                "UPDATE Pages SET Content = ? WHERE BookID = ? AND PageNo = ?",
                page_updates,
            )
            connection.executemany(
                "UPDATE Footnotes SET FootnoteText = ? WHERE BookID = ? AND PageNo = ?",
                footnote_updates,
            )
            connection.executemany(
                "UPDATE Pages SET HadeesNumber = ? WHERE BookID = ? AND PageNo = ?",
                hadees_number_updates,
            )
            connection.executemany(
                "UPDATE Pages SET AyahNumber = ? WHERE BookID = ? AND PageNo = ?",
                ayah_number_updates,
            )
            connection.commit()
            updated_books += 1
            updated_pages += len(page_updates)
            updated_footnotes += len(footnote_updates)
            updated_hadees_numbers += len(hadees_number_updates)
            updated_ayah_numbers += len(ayah_number_updates)

    print(
        f"Reformatted {updated_books}/{len(targets)} book(s): "
        f"{updated_pages} page(s), {updated_footnotes} footnote(s) updated, "
        f"{updated_hadees_numbers} HadeesNumber(s), {updated_ayah_numbers} AyahNumber(s) captured."
    )
    print(f"Source file missing: {missing_source_count}, read errors: {read_error_count}.")
    return 0


def _reader_for(source_path: Path):
    """Return the reader matching this book's real source folder.

    Matches a real path *segment* ("...\\Hadith\\...", not just the
    substring "hadith" anywhere in the path) - real production data has
    Books/-folder files like "fazail-e-ahle-hadith.db" whose filename
    alone contains "hadith", which a substring check wrongly routed to
    the Hadith reader (62 books failed this way on the first real run).
    """
    segments = {part.lower() for part in source_path.parts}
    if "hadith" in segments:
        return _HADITH_READER
    if "quran" in segments:
        return _QURAN_READER
    return _BOOK_READER


def _load_targets(database_path: Path, library: str) -> list[tuple[int, str]]:
    """Return (BookID, Source) for every real book in this library."""
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT b.BookID, b.Source FROM Books b
            JOIN Libraries l ON l.LibraryID = b.LibraryID
            WHERE l.Name = ?
            """,
            (library,),
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Urdu text prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
