"""Command-line interface for importing a Maktaba Shamela book collection.

Point `folder_path` at Shamela's own `Books` subfolder (e.g.
`F:\\المكتبة الشاملة\\Books`), not the library root - other top-level
folders (`PDF/`, `Files/`, `albahhet/`, app binaries) hold real `.mdb`
files too, but they are Shamela's own app internals/PDF archive, not real
books (confirmed by direct inspection - see CHANGELOG).

Real books are read in batches via `PowerShellShamelaReader` (each batch
is one 32-bit-PowerShell/ADODB subprocess call, not one process per
file). A single `.mdb` can be a genuine multi-volume work - each volume
becomes its own `Book` (see `shamela_book_reader.py`) - so after import,
`model_volumes` is re-run once to group same-work volumes into a
`Series`, the same mechanism already used for other multi-volume
libraries in this project.

Each batch is written to the database immediately (`MasterBookRepository.
import_books()` per batch), not accumulated across the whole run - a
real bug found at full-corpus scale (~30,662 files): holding every
`Book` in memory until one final write both risked a genuine
`MemoryError` (confirmed - it happened) and meant a crash at file 19,000
would have discarded all prior progress, since nothing had been written
yet. Writing per batch bounds memory to one batch's data and means
already-completed batches survive a later failure - `Books.Source`'s
existing `UNIQUE` constraint (`_is_imported()`) already makes re-running
the same command safe/resumable, skipping whatever's already imported.
The pre-import `LibraryAnalyzer`/`docs/` report other importers generate
is skipped here for the same reason (it also operates on the whole
in-memory book list) - a real, deliberate simplification for this
bulk-scale importer, not an oversight.
"""

import argparse
import logging
import sqlite3
import sys
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.book import Book
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import model_volumes
from islamic_research_hub.infrastructure.persistence.powershell_shamela_reader import (
    PowerShellShamelaReader,
    ShamelaReaderError,
)
from islamic_research_hub.infrastructure.persistence.shamela_book_reader import (
    ShamelaBookReadError,
    read_shamela_book,
)
from islamic_research_hub.infrastructure.persistence.shamela_catalog_reader import (
    ShamelaCatalogEntry,
    ShamelaCatalogReader,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_LIBRARY_NAME = "Maktaba Shamela"
CATALOG_FILE_NAME = "book_index.db"
BATCH_SIZE = 100


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Import a Maktaba Shamela book collection (a folder of real .mdb files)."
    )
    parser.add_argument("folder_path", help="Folder to scan recursively for .mdb files")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=None,
        help=f"Path to {CATALOG_FILE_NAME} (default: <folder_path's grandparent>/{CATALOG_FILE_NAME})",
    )
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
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Import at most this many real .mdb files (for a pilot run)",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Import real Shamela books, continuing past individual read failures."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    folder = Path(args.folder_path)
    if not folder.is_dir():
        LOGGER.error("Folder does not exist: %s", folder)
        return 1
    catalog_path = args.catalog or folder.parent / CATALOG_FILE_NAME
    catalog = _load_catalog(catalog_path)

    files = sorted(folder.rglob("*.mdb"))
    if args.limit is not None:
        files = files[: args.limit]

    repository = MasterBookRepository()
    reader = PowerShellShamelaReader()
    total_processed = 0
    total_read_failed = 0
    total_imported = 0
    total_skipped = 0
    total_write_failed = 0

    for batch_start in range(0, len(files), BATCH_SIZE):
        batch = tuple(files[batch_start : batch_start + BATCH_SIZE])
        try:
            raw_results = reader.read_all(batch)
        except ShamelaReaderError:
            total_read_failed += len(batch)
            LOGGER.exception("Failed to run the Shamela read batch for %d file(s).", len(batch))
            total_processed += len(batch)
            _print_progress(total_processed, len(files))
            continue

        batch_books: list[Book] = []
        batch_sources: list[Path] = []
        for raw in raw_results:
            try:
                shamela_id = int(raw.path.stem)
            except ValueError:
                shamela_id = None
            catalog_entry = catalog.get(shamela_id) if shamela_id is not None else None
            try:
                volumes = read_shamela_book(raw, catalog_entry)
            except ShamelaBookReadError:
                total_read_failed += 1
                LOGGER.exception("Failed to read Shamela file: %s", raw.path)
                continue
            batch_books.extend(volumes)
            batch_sources.extend(
                _source_for_volume(raw.path, index, len(volumes)) for index in range(len(volumes))
            )

        if batch_books:
            try:
                imported, skipped, write_failed = repository.import_books(
                    args.database,
                    tuple(batch_books),
                    tuple(batch_sources),
                    library_name=args.library,
                )
            except OSError as error:
                LOGGER.error("Failed to write a Shamela batch to the database: %s", error)
                return 1
            total_imported += imported
            total_skipped += skipped
            total_write_failed += write_failed

        total_processed += len(batch)
        _print_progress(total_processed, len(files))

    print("Import Summary")
    print(f"Real .mdb files processed: {total_processed}")
    print(f"Files failed to read: {total_read_failed}")
    print(f"Books imported: {total_imported}")
    print(f"Books skipped (already imported): {total_skipped}")
    print(f"Books failed to write: {total_write_failed}")

    with closing(sqlite3.connect(args.database)) as connection:
        model_volumes(connection)
        connection.commit()
        series_count = connection.execute("SELECT COUNT(*) FROM Series").fetchone()[0]
    print(f"Series (multi-volume works) after grouping: {series_count}")

    return 0


def _source_for_volume(mdb_path: Path, index: int, volume_count: int) -> Path:
    """Return a real, distinct `Source` value for one volume of a Shamela file.

    `Books.Source` is `UNIQUE` across the whole database (every prior
    importer's idempotency key, since every prior reader is one file ->
    one book) - a genuine multi-volume Shamela file produces several
    `Book`s from the *same* file, so each volume beyond the first needs
    its own distinct source string to import at all, while still tracing
    back to the real file (`#part2`, not an unrelated made-up path). A
    single-volume file keeps its plain path unchanged, matching every
    other importer's convention exactly.
    """
    if volume_count <= 1:
        return mdb_path
    return Path(f"{mdb_path}#part{index + 1}")


def _load_catalog(catalog_path: Path) -> dict[int, ShamelaCatalogEntry]:
    """Load the real title/author catalog, or return an empty one honestly
    if it isn't found - books still import, titled by filename instead."""
    if not catalog_path.is_file():
        LOGGER.warning("Catalog not found at %s - books will be titled by filename.", catalog_path)
        return {}
    return ShamelaCatalogReader(catalog_path).load_by_shamela_id()


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic titles print safely."""
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
