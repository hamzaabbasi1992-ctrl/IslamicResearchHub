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

MOBILE_ROOM_SCHEMA_VERSION = 1
"""Must match `@Database(version = ...)` on the Android side
(`BookPackageDatabase.kt`/`CatalogDatabase.kt`). Room's `SQLiteOpenHelper`
decides onCreate vs onUpgrade by comparing the copied file's own
`PRAGMA user_version` against this declared version; a plain `sqlite3`-
written file defaults to `user_version = 0`, which Room reads as "never
initialized" and tries to CREATE TABLEs that already exist here - a real,
confirmed crash on first launch (2026-08-12), not a hypothetical one.
Stamping this after `_create_schema()` is the fix: Room sees the version
already matches and opens the file as-is, no migration attempted."""


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


def export_book_package_to_file(
    database_path: Path, book_id: int, output_path: Path
) -> tuple[str, int, int, float]:
    """Export one book's full page and chapter content directly to output_path."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    with closing(sqlite3.connect(database_path)) as source:
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
                (book_id,),
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
                (book_id,),
            ).fetchone()
        if book_row is None:
            raise KeyError(f"No book found with BookID={book_id}")

        pages = source.execute(
            "SELECT ROW_NUMBER() OVER (ORDER BY PageNo) AS PageID, "
            "PageNo, Content, HadeesNumber, AyahNumber FROM Pages "
            "WHERE BookID = ? ORDER BY PageNo",
            (book_id,),
        ).fetchall()
        chapters = source.execute(
            "SELECT ChapterID, ParentChapterID, Title, PageNo, SortKey FROM Chapters "
            "WHERE BookID = ? ORDER BY SortKey, ChapterID",
            (book_id,),
        ).fetchall()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.unlink(missing_ok=True)

    with closing(sqlite3.connect(output_path)) as destination:
        _create_schema(destination)
        destination.execute(f"PRAGMA user_version = {MOBILE_ROOM_SCHEMA_VERSION}")
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
    return str(book_row["Title"]), len(pages), len(chapters), output_size_mb


def export_category_books_to_folder(
    database_path: Path,
    category_name: str | None,
    output_folder: Path,
    progress_callback=None,
) -> tuple[int, float]:
    """Export all books (or all books matching category_name) as book_<id>.db packages into output_folder."""
    if not database_path.is_file():
        raise FileNotFoundError(f"Database file not found: {database_path}")

    output_folder.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as source:
        if category_name and category_name != "All Categories":
            rows = source.execute(
                "SELECT BookID FROM Books WHERE Category = ? ORDER BY BookID",
                (category_name,),
            ).fetchall()
        else:
            rows = source.execute("SELECT BookID FROM Books ORDER BY BookID").fetchall()

    exported_count = 0
    total_size_mb = 0.0
    total_books = len(rows)

    for index, (book_id,) in enumerate(rows, start=1):
        out_file = output_folder / f"book_{book_id}.db"
        try:
            _title, _pages, _chapters, size_mb = export_book_package_to_file(
                database_path, book_id, out_file
            )
            exported_count += 1
            total_size_mb += size_mb
        except Exception:
            pass
        if progress_callback is not None:
            progress_callback(index, total_books)

    return exported_count, total_size_mb


def main(arguments: Sequence[str] | None = None) -> int:
    """Export one real book's full content and print a real summary."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    output_path = args.output or (DEFAULT_OUTPUT_FOLDER / f"book_{args.book_id}.db")

    try:
        title, num_pages, num_chapters, size_mb = export_book_package_to_file(
            args.database, args.book_id, output_path
        )
    except KeyError:
        LOGGER.error("No book found with BookID=%d", args.book_id)
        return 1
    except Exception as err:
        LOGGER.error("Book package export failed: %s", err)
        return 1

    print("Book Package Export Summary")
    print(f"Book: {title} (BookID={args.book_id})")
    print(f"Pages: {num_pages}")
    print(f"Chapters: {num_chapters}")
    print(f"Output: {output_path} ({size_mb:.2f} MB)")
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
            LibraryID INTEGER NOT NULL PRIMARY KEY,
            Name TEXT NOT NULL
        );
        CREATE TABLE Books (
            BookID INTEGER NOT NULL PRIMARY KEY,
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
            PageID INTEGER NOT NULL PRIMARY KEY,
            PageNo INTEGER,
            Content TEXT,
            HadeesNumber INTEGER,
            AyahNumber INTEGER
        );
        CREATE TABLE Chapters (
            ChapterID INTEGER NOT NULL PRIMARY KEY,
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
