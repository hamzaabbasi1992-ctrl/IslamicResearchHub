"""In-memory recursive scanner for verified Jibreel Mobile book files."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from islamic_research_hub.domain.models.book import Book, Chapter

LOGGER = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


class BookExtractor(Protocol):
    """Contract for extracting one .mjbz file into memory."""

    def extract_file(self, file_path: str | Path) -> Book:
        """Extract one book without persisting it."""


@dataclass(frozen=True, slots=True)
class ScannedBook:
    """One successfully extracted book paired with its source file path."""

    source: Path
    book: Book


@dataclass(frozen=True, slots=True)
class FolderScanResult:
    """In-memory outcome of scanning a folder for MJBZ books."""

    books: tuple[Book, ...]
    processed_count: int
    failed_count: int
    sources: tuple[Path, ...] = ()

    @property
    def succeeded_count(self) -> int:
        """Return the number of successfully extracted books."""
        return len(self.books)

    @property
    def total_pages(self) -> int:
        """Return the total number of extracted page records."""
        return sum(len(book.pages) for book in self.books)

    @property
    def total_chapters(self) -> int:
        """Return the total number of TOC records across all books."""
        return sum(
            _count_chapters(book.table_of_contents) for book in self.books
        )


class MjbzFolderScanner:
    """Scan a folder recursively and retain successful Book objects in memory."""

    def __init__(self, extractor: BookExtractor) -> None:
        self._extractor = extractor

    def scan(
        self,
        folder_path: str | Path,
        progress: ProgressCallback | None = None,
    ) -> FolderScanResult:
        """Extract every .mjbz file below a folder, continuing after failures."""
        folder = Path(folder_path).expanduser()
        if not folder.is_dir():
            raise NotADirectoryError(f"Folder does not exist: {folder}")

        files = tuple(
            sorted(
                (
                    path
                    for path in folder.rglob("*")
                    if path.is_file() and path.suffix.lower() == ".mjbz"
                ),
                key=lambda path: str(path).casefold(),
            )
        )
        total_files = len(files)
        if progress is not None:
            progress(0, total_files)

        books: list[Book] = []
        sources: list[Path] = []
        failed_count = 0
        for processed_count, database_path in enumerate(files, start=1):
            try:
                books.append(self._extractor.extract_file(database_path))
                sources.append(database_path.resolve())
            except Exception:
                failed_count += 1
                LOGGER.exception("Failed to extract MJBZ file: %s", database_path)
            finally:
                if progress is not None:
                    progress(processed_count, total_files)

        return FolderScanResult(
            books=tuple(books),
            processed_count=total_files,
            failed_count=failed_count,
            sources=tuple(sources),
        )


def _count_chapters(chapters: tuple[Chapter, ...]) -> int:
    """Count all TOC nodes without retaining any additional book data."""
    return sum(1 + _count_chapters(chapter.children) for chapter in chapters)
