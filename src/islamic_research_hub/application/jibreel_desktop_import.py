"""Application service for importing Jibreel Desktop's encrypted .mjbx books.

.mjbx files are the same verified schema as .mjbz, wrapped in
System.Data.SQLite's built-in encryption. Filenames are the app's own
catalog id (e.g. "2584.mjbx" is book id 2584), which lets new files be
identified without decrypting anything first.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DecryptResult:
    """Outcome of attempting to decrypt one .mjbx file."""

    source: Path
    destination: Path
    succeeded: bool


class MjbxBatchDecryptor(Protocol):
    """Contract for decrypting a batch of .mjbx files to plain .mjbz files."""

    def decrypt_all(self, jobs: tuple[tuple[Path, Path], ...]) -> tuple[DecryptResult, ...]:
        """Attempt to decrypt every (source, destination) pair, continuing past failures."""


def find_new_files(
    app_books_folder: Path, existing_source_book_ids: frozenset[str]
) -> tuple[Path, ...]:
    """Return .mjbx files whose filename (the app's own book id) is not already imported."""
    return tuple(
        sorted(
            (
                path
                for path in app_books_folder.glob("*.mjbx")
                if path.stem not in existing_source_book_ids
            ),
            key=lambda path: path.name,
        )
    )


class JibreelDesktopImportPlanner:
    """Plan a decryption batch: which files are new, and where they should land."""

    def __init__(self, staging_folder: Path) -> None:
        self._staging_folder = staging_folder

    def plan(
        self, app_books_folder: Path, existing_source_book_ids: frozenset[str]
    ) -> tuple[tuple[Path, Path], ...]:
        """Return (source, destination) pairs for every not-yet-imported .mjbx file."""
        new_files = find_new_files(app_books_folder, existing_source_book_ids)
        return tuple(
            (source, self._staging_folder / f"{source.stem}.mjbz") for source in new_files
        )
