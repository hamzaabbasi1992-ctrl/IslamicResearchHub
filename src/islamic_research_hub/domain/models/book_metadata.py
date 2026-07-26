"""Typed model for one book's full catalog metadata (for a details view)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BookMetadata:
    """Everything catalogued about one book, for display purposes."""

    book_id: int
    title: str | None
    author: str | None
    publisher: str | None
    language: str | None
    category: str | None
    library: str | None
    page_count: int
    chapter_count: int
    series_title: str | None
    volume_number: int | None
