"""Command-line interface for importing real, Google-Vision-OCR'd text files."""

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
from islamic_research_hub.infrastructure.persistence.ocr_text_book_reader import (
    read_ocr_text_book_file,
)
from islamic_research_hub.infrastructure.reporting.book_library_exporter import (
    BookLibraryExporter,
)
from islamic_research_hub.infrastructure.reporting.library_report_exporter import (
    LibraryReportExporter,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_LIBRARY_NAME = "Tib o Hikmat"
DEFAULT_DATABASE_PATH = Path("data/books.db")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Import real, Google-Vision-OCR'd .txt book files (searched "
            "recursively) into the master database."
        )
    )
    parser.add_argument("folder_path", help="Folder containing OCR'd .txt files, any depth")
    parser.add_argument("--library", default=DEFAULT_LIBRARY_NAME)
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Read every .txt file under the folder (any depth), skip blank
    ones, and import the rest."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    folder = Path(args.folder_path)
    if not folder.is_dir():
        LOGGER.error("Folder does not exist: %s", folder)
        return 1

    files = sorted(folder.rglob("*.txt"))
    books = []
    sources = []
    blank_skipped_count = 0
    failed_count = 0
    for completed_count, file_path in enumerate(files, start=1):
        try:
            book = read_ocr_text_book_file(file_path)
        except OSError:
            failed_count += 1
            LOGGER.exception("Failed to read OCR text file: %s", file_path)
        else:
            if book is None:
                blank_skipped_count += 1
            else:
                books.append(book)
                sources.append(file_path.resolve())
        _print_progress(completed_count, len(files))

    result = FolderScanResult(
        books=tuple(books),
        processed_count=len(files),
        failed_count=blank_skipped_count + failed_count,
        sources=tuple(sources),
    )
    print("OCR Text Import Summary")
    print(f"Files scanned: {result.processed_count}")
    print(f"Books with usable text: {result.succeeded_count}")
    print(f"Blank (skipped): {blank_skipped_count}")
    print(f"Failed to read (corrupted/inaccessible): {failed_count}")
    print(f"Total pages: {result.total_pages}")

    report = LibraryAnalyzer().analyze(result)
    try:
        LibraryReportExporter().export(report, Path("docs") / "ocr_text")
        library_export_result = BookLibraryExporter().export(result, Path("library"))
        database_result = MasterDatabaseBuilder(MasterBookRepository()).build(
            result,
            database_path=args.database,
            library_name=args.library,
            progress=_print_progress,
        )
    except OSError as error:
        LOGGER.error("OCR text import failed: %s", error)
        return 1

    print(
        f"Book files written: {library_export_result.exported_count} "
        f"({library_export_result.skipped_count} skipped)"
    )
    print("Master Database Summary")
    print(f"Books imported: {database_result.imported_count}")
    print(f"Books skipped: {database_result.skipped_count}")
    print(f"Books failed: {database_result.failed_count}")

    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Urdu text prints safely."""
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
