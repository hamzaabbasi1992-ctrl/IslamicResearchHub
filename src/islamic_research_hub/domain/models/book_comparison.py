"""Typed models for a real, page-level comparison between two candidate-duplicate books."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageComparisonEntry:
    """One page number present in both books, with how similar its real text is."""

    page_number: int
    similarity: float
    content_a: str
    content_b: str


@dataclass(frozen=True, slots=True)
class BookComparisonResult:
    """A real, page-level comparison between two books - not just "probably the same".

    `overall_similarity` is the average per-page similarity across every
    page number present in both books; `None` when no page numbers
    overlap at all (the two books' pagination doesn't line up, so no
    direct page-by-page comparison is possible - this is reported
    honestly rather than as a misleading 0% or 100%).
    """

    book_id_a: int
    book_id_b: int
    title_a: str | None
    title_b: str | None
    page_count_a: int
    page_count_b: int
    common_page_count: int
    overall_similarity: float | None
    differing_pages: tuple[PageComparisonEntry, ...]
