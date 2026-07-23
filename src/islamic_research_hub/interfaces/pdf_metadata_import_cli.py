"""Command-line interface for cataloging a PDF collection as metadata-only entries.

Used when a PDF collection has no pre-extracted text available and full
OCR/PDF text extraction is out of scope. Each PDF becomes a Book record
with a title (from its filename) but no page content, so the corpus at
least has a record that the book exists.
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
from islamic_research_hub.infrastructure.persistence.pdf_metadata_reader import (
    read_pdf_metadata,
)
from islamic_research_hub.infrastructure.reporting.library_report_exporter import (
    LibraryReportExporter,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Catalog a folder of PDFs as metadata-only book entries."
    )
    parser.add_argument("folder_path", help="Folder to scan recursively for .pdf files")
    parser.add_argument("--library", required=True, help="Library name to tag books with")
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Catalog every PDF in a folder as a metadata-only Book."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    folder = Path(args.folder_path)
    if not folder.is_dir():
        LOGGER.error("Folder does not exist: %s", folder)
        return 1

    files = sorted(folder.rglob("*.pdf"))
    books = tuple(read_pdf_metadata(file_path) for file_path in files)
    sources = tuple(file_path.resolve() for file_path in files)

    result = FolderScanResult(
        books=books,
        processed_count=len(files),
        failed_count=0,
        sources=sources,
    )
    print("PDF Metadata Catalog Summary")
    print(f"PDF files found: {result.processed_count}")

    report = LibraryAnalyzer().analyze(result)
    try:
        LibraryReportExporter().export(report, Path("docs") / "pdf_catalog")
        database_result = MasterDatabaseBuilder(MasterBookRepository()).build(
            result,
            library_name=args.library,
            progress=_print_progress,
        )
    except OSError as error:
        LOGGER.error("PDF metadata import failed: %s", error)
        return 1

    print("Master Database Summary")
    print(f"Books imported: {database_result.imported_count}")
    print(f"Books skipped: {database_result.skipped_count}")
    print(f"Books failed: {database_result.failed_count}")

    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Urdu titles print safely."""
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
