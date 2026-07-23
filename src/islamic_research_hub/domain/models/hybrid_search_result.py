"""Typed model for one match from a fused keyword + semantic search."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HybridSearchResult:
    """One matching page, possibly found by keyword search, semantic search, or both."""

    book_id: int
    title: str | None
    author: str | None
    page_number: int | None
    library: str | None
    excerpt: str
    score: float
    matched_by: tuple[str, ...]
