"""Typed model for one semantic (embedding-based) search match."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SemanticSearchResult:
    """One matching page returned from a semantic similarity search."""

    book_id: int
    title: str | None
    author: str | None
    page_number: int | None
    excerpt: str
    similarity: float
    library: str | None = None
