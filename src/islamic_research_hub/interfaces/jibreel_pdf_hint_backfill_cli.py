"""Backfill Books.SourcePdfHint from Jibreel's own Information.PDF cross-reference.

Migration 11 added the column, additive and NULL until this runs - see its
docstring for the real numbers that motivated it (30/30 sampled unmatched
Jibreel Desktop stub books had this hint filled in; comparing it, both
sides romanized, against the real PDF archive folder resolved 24/30).

Re-decrypts each target book's original .mjbx source (batched, temp files
cleaned up after every batch so this never accumulates thousands of
decrypted files on disk), reads Information.PDF, and stores it. Resume-safe:
already-backfilled books (SourcePdfHint IS NOT NULL) are skipped, so a
re-run after new imports only processes what's new.
"""

import argparse
import logging
import sqlite3
import sys
import tempfile
from collections.abc import Sequence
from contextlib import closing
from pathlib import Path

from islamic_research_hub.application.jibreel_desktop_import import MjbxBatchDecryptor
from islamic_research_hub.infrastructure.persistence.powershell_mjbx_decryptor import (
    DEFAULT_PASSWORD,
    MjbxDecryptorError,
    PowerShellMjbxDecryptor,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_BOOKS_FOLDER = Path(r"F:\Maktaba Jibreel\Books")
DEFAULT_LIBRARY = "Maktaba Jibreel (Desktop)"
BATCH_SIZE = 200
PDF_HINT_KEY = "PDF"

# Same stub definition as PdfMatchCandidateRepository - kept in sync
# manually since importing it here would create a persistence-layer ->
# interfaces-layer dependency the other way around from the rest of the app.
STUB_MIN_PAGE_COUNT = 20
STUB_MAX_AVG_CONTENT_LENGTH = 60


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Backfill Books.SourcePdfHint from Jibreel's own PDF cross-reference."
    )
    parser.add_argument("--books-folder", type=Path, default=DEFAULT_BOOKS_FOLDER)
    parser.add_argument(
        "--sqlite-dll",
        type=Path,
        required=True,
        help="Path to the Jibreel Desktop app's own System.Data.SQLite.dll",
    )
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--library", default=DEFAULT_LIBRARY)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument(
        "--all",
        dest="stubs_only",
        action="store_false",
        default=True,
        help="Backfill every book in the library, not just heading-only stubs.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Decrypt and backfill using a real decryptor."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)
    decryptor = PowerShellMjbxDecryptor(args.sqlite_dll, args.password)
    return run(args, decryptor)


def run(args: argparse.Namespace, decryptor: MjbxBatchDecryptor) -> int:
    """Run the backfill using an injected decryptor (real or fake, for testing)."""
    targets = _load_targets(args.database, args.library, args.stubs_only)
    print(f"{len(targets)} book(s) need a PDF hint.")
    if not targets:
        return 0

    updated_count = 0
    for batch_start in range(0, len(targets), BATCH_SIZE):
        batch = targets[batch_start : batch_start + BATCH_SIZE]
        updated_count += _process_batch(args, decryptor, batch)
        print(
            f"Progress: {min(batch_start + BATCH_SIZE, len(targets))}/{len(targets)} "
            f"({updated_count} hint(s) found so far)"
        )

    print(f"Done. {updated_count}/{len(targets)} book(s) got a real PDF hint.")
    return 0


def _process_batch(
    args: argparse.Namespace,
    decryptor: MjbxBatchDecryptor,
    batch: list[tuple[int, str]],
) -> int:
    """Decrypt one batch, extract PDF hints, store them, and return how many were found."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        jobs = tuple(
            (args.books_folder / f"{source_id}.mjbx", tmp_path / f"{source_id}.mjbz")
            for _book_id, source_id in batch
        )
        try:
            results = decryptor.decrypt_all(jobs)
        except MjbxDecryptorError as error:
            LOGGER.error("Batch decryption failed: %s", error)
            return 0

        hints: list[tuple[str, int]] = []
        for (book_id, _source_id), result in zip(batch, results, strict=True):
            if not result.succeeded:
                continue
            hint = _read_pdf_hint(result.destination)
            if hint:
                hints.append((hint, book_id))

        if hints:
            with closing(sqlite3.connect(args.database)) as connection:
                connection.executemany(
                    "UPDATE Books SET SourcePdfHint = ? WHERE BookID = ?", hints
                )
                connection.commit()
        return len(hints)


def _load_targets(database_path: Path, library: str, stubs_only: bool) -> list[tuple[int, str]]:
    """Return (BookID, SourceBookID) pairs still missing a PDF hint."""
    with closing(sqlite3.connect(database_path)) as connection:
        if stubs_only:
            rows = connection.execute(
                """
                SELECT b.BookID, b.SourceBookID FROM Books b
                JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE l.Name = ? AND b.SourceBookID IS NOT NULL AND b.SourcePdfHint IS NULL
                AND b.PageCount > ?
                AND b.BookID IN (
                    SELECT BookID FROM Pages GROUP BY BookID
                    HAVING AVG(LENGTH(Content)) < ?
                )
                """,
                (library, STUB_MIN_PAGE_COUNT, STUB_MAX_AVG_CONTENT_LENGTH),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT b.BookID, b.SourceBookID FROM Books b
                JOIN Libraries l ON l.LibraryID = b.LibraryID
                WHERE l.Name = ? AND b.SourceBookID IS NOT NULL AND b.SourcePdfHint IS NULL
                """,
                (library,),
            ).fetchall()
    return [(row[0], row[1]) for row in rows]


def _read_pdf_hint(mjbz_path: Path) -> str | None:
    """Return the decrypted book's own PDF cross-reference, or None if it has none."""
    if not mjbz_path.is_file():
        return None
    try:
        with closing(
            sqlite3.connect(f"{mjbz_path.resolve().as_uri()}?mode=ro", uri=True)
        ) as connection:
            row = connection.execute(
                'SELECT "Value" FROM "Information" WHERE "Key" = ?', (PDF_HINT_KEY,)
            ).fetchone()
    except sqlite3.Error:
        LOGGER.warning("Could not read Information from %s", mjbz_path)
        return None
    if row is None or row[0] is None:
        return None
    value = str(row[0]).strip()
    return value or None


def _configure_unicode_output() -> None:
    """Use UTF-8 output so Arabic and Urdu text prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
