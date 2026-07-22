"""Application service for importing a scanned library into books.db."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from islamic_research_hub.application.mjbz_folder_scanner import FolderScanResult
from islamic_research_hub.domain.models.book import Book

ProgressCallback = Callable[[int, int], None]

DEFAULT_LIBRARY_NAME = "Maktaba Jibreel (Mobile)"


class MasterDatabaseWriter(Protocol):
    """Contract for transactional persistence of scanned books."""

    def import_books(
        self,
        database_path: Path,
        books: tuple[Book, ...],
        sources: tuple[Path, ...],
        library_name: str = DEFAULT_LIBRARY_NAME,
        progress: ProgressCallback | None = None,
    ) -> tuple[int, int, int]:
        """Import books and return imported, skipped, failed counts."""


@dataclass(frozen=True, slots=True)
class MasterDatabaseBuildResult:
    """Summary of one master database import run."""

    imported_count: int
    skipped_count: int
    failed_count: int


class MasterDatabaseBuilder:
    """Coordinate a master database import from an existing scan result."""

    def __init__(self, writer: MasterDatabaseWriter) -> None:
        self._writer = writer

    def build(
        self,
        scan_result: FolderScanResult,
        database_path: Path = Path("data/books.db"),
        library_name: str = DEFAULT_LIBRARY_NAME,
        progress: ProgressCallback | None = None,
    ) -> MasterDatabaseBuildResult:
        """Create or update books.db using successful scanner results."""
        imported, skipped, failed = self._writer.import_books(
            database_path=database_path,
            books=scan_result.books,
            sources=scan_result.sources,
            library_name=library_name,
            progress=progress,
        )
        return MasterDatabaseBuildResult(
            imported_count=imported,
            skipped_count=skipped,
            failed_count=failed,
        )
