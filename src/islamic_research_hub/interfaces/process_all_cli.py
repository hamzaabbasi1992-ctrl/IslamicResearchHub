"""Run every real post-import processing step in the right order, in one command.

Importing a new library is still format-specific (each source needs its
own reader/decryptor and its own real arguments - `jibreel_desktop_import_cli.py`,
`maknoon_import_cli.py`, `shamila_urdu_import_cli.py`, `pdf_metadata_import_cli.py`
- there is no way to unify that step honestly). Everything *after* import
is generic, though, and until now had to be run as five to seven separate
commands, in a specific order, from memory. This chains them:

1. Apply pending schema migrations (`migrate_database_cli`).
2. Jibreel PDF-hint backfill, if `--jibreel-books-folder`/`--jibreel-sqlite-dll`
   are given - optional, since it needs real decryption credentials this
   CLI can't assume (`jibreel_pdf_hint_backfill_cli`).
3. Shamila Urdu Publish Year backfill (`shamila_urdu_publish_year_backfill_cli`).
4. Shamila Urdu structure-preservation backfill (`shamila_urdu_structure_backfill_cli`).
5. PDF match candidate detection for heading-only stub books
   (`PdfMatchCandidateRepository.detect_and_store()` - no dedicated CLI
   exists for this one step, so it's called directly).
6. Taxonomy population (`taxonomy_population_cli`).
7. Semantic embedding indexing, only if `--run-semantic-index` is passed -
   opt-in, since a full run can take hours; otherwise this prints a clear
   reminder to run it separately (it's resume-safe and safe to background).

Every step but the first is independent of the others' success - one step
failing does not stop the rest, matching the same resilience pattern
`jibreel_desktop_import_cli.py` already uses for individual file failures.
Steps 3-4 (Shamila Urdu-specific) and 5-6 (corpus-wide) are all real
no-ops on a database with none of that content yet, so running this after
*any* library's import is always safe, not just Shamila Urdu's.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.pdf_match_candidate_repository import (
    PdfMatchCandidateRepository,
)
from islamic_research_hub.interfaces import (
    jibreel_pdf_hint_backfill_cli,
    migrate_database_cli,
    shamila_urdu_publish_year_backfill_cli,
    shamila_urdu_structure_backfill_cli,
    taxonomy_population_cli,
)
from islamic_research_hub.shared.logging_config import configure_logging

# semantic_index_cli is imported lazily, only when --run-semantic-index is
# passed - it pulls in sentence-transformers/torch at module level, a real
# ~20s one-time cost that every other step (and every test of this module)
# would otherwise pay unconditionally just for importing this file.

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Run every post-import processing step against the master database, in order."
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument(
        "--jibreel-books-folder",
        type=Path,
        default=None,
        help="Enables the Jibreel PDF-hint backfill step, if given together with --jibreel-sqlite-dll.",
    )
    parser.add_argument(
        "--jibreel-sqlite-dll",
        type=Path,
        default=None,
        help="Path to the Jibreel Desktop app's own System.Data.SQLite.dll.",
    )
    parser.add_argument(
        "--run-semantic-index",
        action="store_true",
        help="Also run the (potentially hours-long) semantic embedding indexer at the end.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run every step against the real database."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1

    _run_step("1/7 Schema migrations", lambda: migrate_database_cli.main(
        ["--database", str(args.database)]
    ))

    if args.jibreel_books_folder is not None and args.jibreel_sqlite_dll is not None:
        _run_step("2/7 Jibreel PDF-hint backfill", lambda: jibreel_pdf_hint_backfill_cli.main(
            [
                "--database", str(args.database),
                "--books-folder", str(args.jibreel_books_folder),
                "--sqlite-dll", str(args.jibreel_sqlite_dll),
            ]
        ))
    else:
        print("2/7 Jibreel PDF-hint backfill: skipped (pass --jibreel-books-folder "
              "and --jibreel-sqlite-dll to enable)")

    _run_step("3/7 Shamila Urdu Publish Year backfill", lambda: shamila_urdu_publish_year_backfill_cli.main(
        ["--database", str(args.database)]
    ))
    _run_step("4/7 Shamila Urdu structure backfill", lambda: shamila_urdu_structure_backfill_cli.main(
        ["--database", str(args.database)]
    ))
    _run_step("5/7 PDF match candidate detection", lambda: _run_pdf_match_detection(args.database))
    _run_step("6/7 Taxonomy population", lambda: taxonomy_population_cli.main(
        ["--database", str(args.database)]
    ))

    if args.run_semantic_index:
        from islamic_research_hub.interfaces import semantic_index_cli

        _run_step("7/7 Semantic embedding indexing", lambda: semantic_index_cli.main(
            ["--database", str(args.database)]
        ))
    else:
        print("7/7 Semantic embedding indexing: skipped (pass --run-semantic-index to "
              "include it here, or run semantic_index_cli separately/in the background - "
              "it's resume-safe)")

    return 0


def _run_step(label: str, step: "callable[[], int]") -> None:
    """Run one processing step, printing a header and continuing past failures."""
    print(f"\n=== {label} ===")
    try:
        exit_code = step()
        if exit_code != 0:
            LOGGER.error("%s exited with code %d", label, exit_code)
    except Exception:
        LOGGER.exception("%s failed", label)


def _run_pdf_match_detection(database_path: Path) -> int:
    """Fuzzy-match heading-only stub books against PDF archive titles, and print the count."""
    count = PdfMatchCandidateRepository(database_path).detect_and_store()
    print(f"PDF match candidates found: {count}")
    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so any non-ASCII content in messages prints safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
