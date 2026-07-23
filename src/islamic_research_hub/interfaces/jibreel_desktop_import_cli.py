"""Command-line interface for importing Jibreel Desktop's encrypted .mjbx library."""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.application.jibreel_desktop_import import (
    JibreelDesktopImportPlanner,
    MjbxBatchDecryptor,
)
from islamic_research_hub.application.library_analyzer import LibraryAnalyzer
from islamic_research_hub.application.master_database_builder import MasterDatabaseBuilder
from islamic_research_hub.application.mjbz_book_extraction import MjbzBookExtractionService
from islamic_research_hub.application.mjbz_folder_scanner import MjbzFolderScanner
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.mjbz_book_reader import (
    SqliteMjbzBookReader,
)
from islamic_research_hub.infrastructure.persistence.mjbz_sqlite_inspector import (
    SqliteMjbzInspector,
)
from islamic_research_hub.infrastructure.persistence.powershell_mjbx_decryptor import (
    DEFAULT_PASSWORD,
    MjbxDecryptorError,
    PowerShellMjbxDecryptor,
)
from islamic_research_hub.infrastructure.reporting.book_library_exporter import (
    BookLibraryExporter,
)
from islamic_research_hub.infrastructure.reporting.library_report_exporter import (
    LibraryReportExporter,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_LIBRARY_NAME = "Maktaba Jibreel (Desktop)"
DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_STAGING_FOLDER = Path("data/staging/jibreel_desktop")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Decrypt and import Jibreel Desktop's .mjbx book library."
    )
    parser.add_argument("app_books_folder", type=Path, help="Folder containing .mjbx files")
    parser.add_argument(
        "--sqlite-dll",
        type=Path,
        required=True,
        help="Path to the Jibreel Desktop app's own System.Data.SQLite.dll",
    )
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING_FOLDER)
    parser.add_argument("--library", default=DEFAULT_LIBRARY_NAME)
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help=f"Path to the master database (default: {DEFAULT_DATABASE_PATH})",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Decrypt new .mjbx files and import them through the existing scan/import pipeline."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)
    decryptor = PowerShellMjbxDecryptor(args.sqlite_dll, args.password)
    return run(args, decryptor)


def run(args: argparse.Namespace, decryptor: MjbxBatchDecryptor) -> int:
    """Run the import using an injected decryptor (real or fake, for testing)."""
    if not args.app_books_folder.is_dir():
        LOGGER.error("Folder does not exist: %s", args.app_books_folder)
        return 1

    existing_ids = _load_existing_source_book_ids(args.database)
    jobs = JibreelDesktopImportPlanner(args.staging).plan(args.app_books_folder, existing_ids)

    if not jobs:
        print("No new .mjbx files to decrypt.")
        return 0
    print(f"Found {len(jobs)} new .mjbx file(s) to decrypt.")

    try:
        results = decryptor.decrypt_all(jobs)
    except MjbxDecryptorError as error:
        LOGGER.error("Decryption failed: %s", error)
        return 1

    succeeded_count = sum(1 for result in results if result.succeeded)
    failed_count = sum(1 for result in results if not result.succeeded)
    print(f"Decrypted: {succeeded_count}, failed (wrong/unknown password): {failed_count}")

    if succeeded_count == 0:
        print("Nothing decrypted successfully; skipping import.")
        return 0

    service = MjbzBookExtractionService(
        inspector=SqliteMjbzInspector(), reader=SqliteMjbzBookReader()
    )
    scan_result = MjbzFolderScanner(service).scan(args.staging, progress=_print_progress)
    print("Folder Scan Summary")
    print(f"Books succeeded: {scan_result.succeeded_count}")
    print(f"Books failed: {scan_result.failed_count}")

    report = LibraryAnalyzer().analyze(scan_result)
    try:
        LibraryReportExporter().export(report, Path("docs") / "jibreel_desktop")
        library_export_result = BookLibraryExporter().export(scan_result, Path("library"))
        database_result = MasterDatabaseBuilder(MasterBookRepository()).build(
            scan_result,
            database_path=args.database,
            library_name=args.library,
            progress=_print_progress,
        )
    except OSError as error:
        LOGGER.error("Import failed: %s", error)
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


def _load_existing_source_book_ids(database_path: Path) -> frozenset[str]:
    """Return every SourceBookID already present in the master database."""
    if not database_path.is_file():
        return frozenset()
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT SourceBookID FROM Books WHERE SourceBookID IS NOT NULL"
        ).fetchall()
    return frozenset(row[0] for row in rows)


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
