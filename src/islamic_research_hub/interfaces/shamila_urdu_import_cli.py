"""Command-line interface for importing a Maktaba Shamila Urdu book collection.

Each book is its own self-contained SQLite file under `Books/<category>/`;
`library.db` at the collection root is a separate catalog index, not a
book, and is skipped.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.application.library_analyzer import LibraryAnalyzer
from islamic_research_hub.application.master_database_builder import MasterDatabaseBuilder
from islamic_research_hub.application.mjbz_folder_scanner import FolderScanResult
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.shamila_urdu_book_reader import (
    ShamilaUrduBookReadError,
    ShamilaUrduBookReader,
)
from islamic_research_hub.infrastructure.reporting.library_report_exporter import (
    LibraryReportExporter,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_LIBRARY_NAME = "Maktaba Shamila Urdu"
CATALOG_FILE_NAME = "library.db"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Import a Maktaba Shamila Urdu book collection (Books/<category>/*.db)."
    )
    parser.add_argument("folder_path", help="The collection's 'data' folder (contains Books/)")
    parser.add_argument(
        "--library",
        default=DEFAULT_LIBRARY_NAME,
        help=f"Library name to tag books with (default: {DEFAULT_LIBRARY_NAME})",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Import every real book, skipping the catalog file and unreadable books."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    folder = Path(args.folder_path)
    if not folder.is_dir():
        LOGGER.error("Folder does not exist: %s", folder)
        return 1

    files = sorted(
        path
        for path in folder.rglob("*.db")
        if path.is_file() and path.name != CATALOG_FILE_NAME
    )

    reader = ShamilaUrduBookReader()
    books = []
    sources = []
    failed_count = 0
    for completed_count, file_path in enumerate(files, start=1):
        try:
            book = reader.read(file_path, category_name=file_path.parent.name)
        except ShamilaUrduBookReadError:
            failed_count += 1
            LOGGER.exception("Failed to read Shamila Urdu book: %s", file_path)
        else:
            books.append(book)
            sources.append(file_path.resolve())
        _print_progress(completed_count, len(files))

    result = FolderScanResult(
        books=tuple(books),
        processed_count=len(files),
        failed_count=failed_count,
        sources=tuple(sources),
    )
    print("Folder Scan Summary")
    print(f"Books processed: {result.processed_count}")
    print(f"Books succeeded: {result.succeeded_count}")
    print(f"Books failed: {result.failed_count}")

    report = LibraryAnalyzer().analyze(result)
    try:
        LibraryReportExporter().export(report, Path("docs") / "shamila_urdu")
        database_result = MasterDatabaseBuilder(MasterBookRepository()).build(
            result,
            database_path=args.database,
            library_name=args.library,
            progress=_print_progress,
        )
    except OSError as error:
        LOGGER.error("Shamila Urdu import failed: %s", error)
        return 1

    print("Master Database Summary")
    print(f"Books imported: {database_result.imported_count}")
    print(f"Books skipped: {database_result.skipped_count}")
    print(f"Books failed: {database_result.failed_count}")

    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Urdu titles print safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _print_progress(completed: int, total: int) -> None:
    """Render a lightweight terminal progress bar."""
    width = 30
    filled = width if total == 0 else int(width * completed / total)
    bar = f"{'#' * filled}{'.' * (width - filled)}"
    print(f"\rProgress: [{bar}] {completed}/{total}", end="", flush=True)
    if completed == total:
        print()


if __name__ == "__main__":
    raise SystemExit(main())
