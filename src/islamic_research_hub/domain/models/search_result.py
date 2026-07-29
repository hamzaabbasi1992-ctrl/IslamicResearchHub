"""Typed model for one full-text search match."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One matching page returned from a full-text library search.

    `source` is "content" (main page text) or "footnote" (`Footnotes`).
    """

    book_id: int
    title: str | None
    author: str | None
    page_number: int | None
    excerpt: str
    library: str | None = None
    source: str = "content"
