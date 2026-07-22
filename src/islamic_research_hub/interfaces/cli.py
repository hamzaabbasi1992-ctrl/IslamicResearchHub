"""Command-line interface for recursive in-memory MJBZ folder scanning."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.application.mjbz_book_extraction import (
    MjbzBookExtractionService,
)
from islamic_research_hub.application.mjbz_folder_scanner import (
    FolderScanResult,
    MjbzFolderScanner,
)
from islamic_research_hub.application.library_analyzer import LibraryAnalyzer
from islamic_research_hub.application.master_database_builder import (
    MasterDatabaseBuilder,
)
from islamic_research_hub.infrastructure.persistence.mjbz_book_reader import (
    MjbzBookReadError,
    SqliteMjbzBookReader,
)
from islamic_research_hub.infrastructure.persistence.mjbz_sqlite_inspector import (
    MjbzInspectionError,
    SqliteMjbzInspector,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    DEFAULT_LIBRARY_NAME,
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.reporting.book_library_exporter import (
    BookLibraryExporter,
)
from islamic_research_hub.infrastructure.reporting.library_report_exporter import (
    LibraryReportExporter,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract verified Jibreel Mobile .mjbz books from one folder."
    )
    parser.add_argument("folder_path", help="Folder to scan recursively for .mjbz files")
    parser.add_argument(
        "--library",
        default=DEFAULT_LIBRARY_NAME,
        help=f"Library name to tag imported books with (default: {DEFAULT_LIBRARY_NAME})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Scan one folder, analyze books, export book files, and build the master database."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)
    service = MjbzBookExtractionService(
        inspector=SqliteMjbzInspector(),
        reader=SqliteMjbzBookReader(),
    )

    scanner = MjbzFolderScanner(service)
    try:
        result = scanner.scan(args.folder_path, progress=_print_progress)
    except (
        NotADirectoryError,
        ValueError,
        MjbzInspectionError,
        MjbzBookReadError,
    ) as error:
        LOGGER.error("Folder scan failed: %s", error)
        return 1

    _print_scan_summary(result)
    report = LibraryAnalyzer().analyze(result)
    try:
        LibraryReportExporter().export(report, Path("docs"))
    except OSError as error:
        LOGGER.error("Unable to write library reports: %s", error)
        return 1
    print("Reports written: docs/library_report.json, docs/library_report.md")

    try:
        library_export_result = BookLibraryExporter().export(result, Path("library"))
    except OSError as error:
        LOGGER.error("Unable to export book library: %s", error)
        return 1
    print(
        f"Book files written: {library_export_result.exported_count} "
        f"({library_export_result.skipped_count} skipped)"
    )
    print("Library written: library/<subject>/<title>.md")

    try:
        database_result = MasterDatabaseBuilder(MasterBookRepository()).build(
            result,
            library_name=args.library,
            progress=_print_progress,
        )
    except (OSError, ValueError) as error:
        LOGGER.error("Master database build failed: %s", error)
        return 1
    print("Master Database Summary")
    print(f"Books imported: {database_result.imported_count}")
    print(f"Books skipped: {database_result.skipped_count}")
    print(f"Books failed: {database_result.failed_count}")
    print("Database written: data/books.db")

    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Persian book text prints safely."""
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


def _print_scan_summary(result: FolderScanResult) -> None:
    """Print final aggregate results without persisting any data."""
    print("Folder Scan Summary")
    print(f"Books processed: {result.processed_count}")
    print(f"Books succeeded: {result.succeeded_count}")
    print(f"Books failed: {result.failed_count}")
    print(f"Total pages: {result.total_pages}")
    print(f"Total chapters: {result.total_chapters}")
