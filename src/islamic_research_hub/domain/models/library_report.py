"""Typed, serializable models for an in-memory library analysis."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class BookSize:
    """Size metrics for one extracted book."""

    title: str | None
    pages: int
    chapters: int


@dataclass(frozen=True, slots=True)
class DuplicateMetadataValue:
    """A repeated non-empty metadata value across extracted books."""

    value: str
    count: int


@dataclass(frozen=True, slots=True)
class LibraryReport:
    """Aggregate quality and size data derived from in-memory Book objects."""

    total_books: int
    total_pages: int
    total_toc_entries: int
    total_categories: int
    metadata_quality: dict[str, int]
    content_quality: dict[str, int]
    largest_book: BookSize | None
    smallest_book: BookSize | None
    average_pages: float
    average_chapters: float
    duplicate_titles: tuple[DuplicateMetadataValue, ...]
    duplicate_authors: tuple[DuplicateMetadataValue, ...]

    def to_dict(self) -> dict[str, object]:
        """Convert the report into JSON-ready built-in types."""
        return {
            "totals": {
                "books": self.total_books,
                "pages": self.total_pages,
                "toc_entries": self.total_toc_entries,
                "categories": self.total_categories,
            },
            "metadata_quality": self.metadata_quality,
            "content_quality": self.content_quality,
            "statistics": {
                "largest_book": asdict(self.largest_book)
                if self.largest_book is not None
                else None,
                "smallest_book": asdict(self.smallest_book)
                if self.smallest_book is not None
                else None,
                "average_pages": self.average_pages,
                "average_chapters": self.average_chapters,
            },
            "duplicates": {
                "titles": [asdict(item) for item in self.duplicate_titles],
                "authors": [asdict(item) for item in self.duplicate_authors],
            },
        }
