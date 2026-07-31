"""Command-line interface for backing up and restoring the master database."""

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.database_backup import (
    DEFAULT_BACKUP_FOLDER,
    DatabaseBackupService,
)
from islamic_research_hub.shared.logging_config import configure_logging

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_KEEP = 3


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Backup and restore the master database.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Create a timestamped backup")
    backup_parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    backup_parser.add_argument("--backup-folder", type=Path, default=DEFAULT_BACKUP_FOLDER)
    backup_parser.add_argument(
        "--keep",
        type=int,
        default=DEFAULT_KEEP,
        help=f"Backups to retain after pruning (default {DEFAULT_KEEP}); 0 disables pruning",
    )

    list_parser = subparsers.add_parser("list", help="List existing backups")
    list_parser.add_argument("--backup-folder", type=Path, default=DEFAULT_BACKUP_FOLDER)

    prune_parser = subparsers.add_parser(
        "prune", help="Delete all but the most recent backups"
    )
    prune_parser.add_argument("--backup-folder", type=Path, default=DEFAULT_BACKUP_FOLDER)
    prune_parser.add_argument("--keep", type=int, default=DEFAULT_KEEP)

    restore_parser = subparsers.add_parser(
        "restore", help="Restore a backup over the live database (destructive)"
    )
    restore_parser.add_argument("backup_file", type=Path)
    restore_parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    restore_parser.add_argument(
        "--yes",
        action="store_true",
        help="Required to confirm overwriting the live database",
    )

    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Run the requested backup subcommand."""
    _configure_unicode_output()
    configure_logging()
    args = build_parser().parse_args(arguments)

    if args.command == "backup":
        return _run_backup(args)
    if args.command == "list":
        return _run_list(args)
    if args.command == "restore":
        return _run_restore(args)
    if args.command == "prune":
        return _run_prune(args)
    return 1


def _run_backup(args: argparse.Namespace) -> int:
    """Create a backup, print its path, and prune old backups beyond --keep."""
    if not args.database.is_file():
        LOGGER.error("Database does not exist: %s", args.database)
        return 1
    service = DatabaseBackupService(args.backup_folder)
    backup_path = service.create_backup(args.database)
    print(f"Backup created: {backup_path}")
    if args.keep > 0:
        pruned = service.prune_backups(args.keep)
        for pruned_path in pruned:
            print(f"Pruned old backup: {pruned_path.name}")
    return 0


def _run_prune(args: argparse.Namespace) -> int:
    """Delete all but the most recent --keep backups."""
    service = DatabaseBackupService(args.backup_folder)
    pruned = service.prune_backups(args.keep)
    if not pruned:
        print("Nothing to prune.")
        return 0
    for pruned_path in pruned:
        print(f"Pruned old backup: {pruned_path.name}")
    return 0


def _run_list(args: argparse.Namespace) -> int:
    """List existing backups, most recent first."""
    service = DatabaseBackupService(args.backup_folder)
    backups = service.list_backups()
    if not backups:
        print("No backups found.")
        return 0
    for backup_path in backups:
        size_mb = backup_path.stat().st_size / 1_048_576
        print(f"{backup_path.name}  ({size_mb:.1f} MB)")
    return 0


def _run_restore(args: argparse.Namespace) -> int:
    """Restore a backup over the live database, requiring explicit confirmation."""
    if not args.backup_file.is_file():
        LOGGER.error("Backup file does not exist: %s", args.backup_file)
        return 1
    if not args.yes:
        LOGGER.error(
            "Restoring overwrites %s. Re-run with --yes to confirm.", args.database
        )
        return 1
    service = DatabaseBackupService()
    service.restore_backup(args.backup_file, args.database)
    print(f"Restored {args.backup_file} over {args.database}")
    return 0


def _configure_unicode_output() -> None:
    """Use UTF-8 output so any non-ASCII paths/messages print safely."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    raise SystemExit(main())
