"""Command-line interface for exporting one real, whole book into a
single self-contained package file - what the Android companion app
imports to make one book readable fully offline (Phase 18 Milestone 1).

Real per-page content (`HadeesNumber`/`AyahNumber` included) plus real
chapters, so the mobile reader has everything it needs from one file
and never needs to reach the desktop database again. Writes a real
SQLite file (not JSON) for the same reason `catalog_export_cli.py`
does - the mobile side queries it directly with its own embedded
SQLite engine.

Reads directly against `Books`/`Libraries`/`Pages`/`Chapters` rather
than through `BookBrowserRepository` - its own `get_book_detail()`
doesn't select `HadeesNumber`/`AyahNumber` or the raw `LibraryID`/
`SeriesID`/`PublishYear` this package needs, so a direct query (mirroring
that repository's own query style) is more honest here than forcing a
reuse that would silently drop real data.
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
DEFAULT_OUTPUT_FOLDER = Path("data/exports")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Export one real book's full content (pages, chapters, metadata) "
            "into a single self-contained package file."
        )
    )
    parser.add_argument("--book-id", type=int, required=True, help="Real BookID to export")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Path to write the package (default: {DEFAULT_OUTPUT_FOLDER}/book_<id>.db)",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Export one real book's full content and print a real summary."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    output_path = args.output or (DEFAULT_OUTPUT_FOLDER / f"book_{args.book_id}.db")

    with closing(sqlite3.connect(args.database)) as source:
        source.row_factory = sqlite3.Row
        if _has_series_columns(source):
            book_row = source.execute(
                """
                SELECT b.BookID, b.LibraryID, b.Title, b.Author, b.Publisher, b.Language,
                       b.Category, b.PageCount, b.ChapterCount, b.PublishYear, b.SeriesID,
                       b.VolumeNumber, l.Name AS LibraryName
                FROM Books b
                LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE b.BookID = ?
                """,
                (args.book_id,),
            ).fetchone()
        else:
            book_row = source.execute(
                """
                SELECT b.BookID, b.LibraryID, b.Title, b.Author, b.Publisher, b.Language,
                       b.Category, b.PageCount, b.ChapterCount, b.PublishYear,
                       NULL AS SeriesID, NULL AS VolumeNumber, l.Name AS LibraryName
                FROM Books b
                LEFT JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE b.BookID = ?
                """,
                (args.book_id,),
            ).fetchone()
        if book_row is None:
            LOGGER.error("No book found with BookID=%d", args.book_id)
            return 1

        pages = source.execute(
            "SELECT ROW_NUMBER() OVER (ORDER BY PageNo) AS PageID, "
            "PageNo, Content, HadeesNumber, AyahNumber FROM Pages "
            "WHERE BookID = ? ORDER BY PageNo",
            (args.book_id,),
        ).fetchall()
        chapters = source.execute(
            "SELECT ChapterID, ParentChapterID, Title, PageNo, SortKey FROM Chapters "
            "WHERE BookID = ? ORDER BY SortKey, ChapterID",
            (args.book_id,),
        ).fetchall()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    with closing(sqlite3.connect(output_path)) as destination:
        _create_schema(destination)
        destination.execute(
            "INSERT INTO Libraries (LibraryID, Name) VALUES (?, ?)",
            (book_row["LibraryID"], book_row["LibraryName"]),
        )
        destination.execute(
            """
            INSERT INTO Books (
                BookID, LibraryID, Title, Author, Publisher, Language, Category,
                PageCount, ChapterCount, PublishYear, SeriesID, VolumeNumber
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_row["BookID"],
                book_row["LibraryID"],
                book_row["Title"],
                book_row["Author"],
                book_row["Publisher"],
                book_row["Language"],
                book_row["Category"],
                book_row["PageCount"],
                book_row["ChapterCount"],
                book_row["PublishYear"],
                book_row["SeriesID"],
                book_row["VolumeNumber"],
            ),
        )
        destination.executemany(
            "INSERT INTO Pages (PageID, PageNo, Content, HadeesNumber, AyahNumber) "
            "VALUES (?, ?, ?, ?, ?)",
            [tuple(row) for row in pages],
        )
        destination.executemany(
            "INSERT INTO Chapters (ChapterID, ParentChapterID, Title, PageNo, SortKey) "
            "VALUES (?, ?, ?, ?, ?)",
            [tuple(row) for row in chapters],
        )
        destination.commit()

    output_size_mb = output_path.stat().st_size / 1_048_576
    print("Book Package Export Summary")
    print(f"Book: {book_row['Title']} (BookID={book_row['BookID']})")
    print(f"Pages: {len(pages)}")
    print(f"Chapters: {len(chapters)}")
    print(f"Output: {output_path} ({output_size_mb:.2f} MB)")
    return 0


def _has_series_columns(connection: sqlite3.Connection) -> bool:
    """Return whether Books.SeriesID/VolumeNumber exist yet - added by a
    later migration, so a database that hasn't run it (e.g. a freshly
    imported test database) doesn't have them. Mirrors
    `BookBrowserRepository._has_series_support()`'s exact guard."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)")}
    return "SeriesID" in columns


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE Libraries (
            LibraryID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL
        );
        CREATE TABLE Books (
            BookID INTEGER PRIMARY KEY,
            LibraryID INTEGER,
            Title TEXT,
            Author TEXT,
            Publisher TEXT,
            Language TEXT,
            Category TEXT,
            PageCount INTEGER,
            ChapterCount INTEGER,
            PublishYear TEXT,
            SeriesID INTEGER,
            VolumeNumber INTEGER
        );
        CREATE TABLE Pages (
            PageID INTEGER PRIMARY KEY,
            PageNo INTEGER,
            Content TEXT,
            HadeesNumber INTEGER,
            AyahNumber INTEGER
        );
        CREATE TABLE Chapters (
            ChapterID INTEGER PRIMARY KEY,
            ParentChapterID INTEGER,
            Title TEXT,
            PageNo INTEGER,
            SortKey INTEGER
        );
        """
    )


def _configure_unicode_output() -> None:
    """Use UTF-8 output so real Arabic/Urdu titles/content print safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
