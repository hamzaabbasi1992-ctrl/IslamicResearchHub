"""Typed model for one book listed by browsing (category/author/library/title), not search."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BookSummary:
    """Enough to show and open one book without a search match/excerpt."""

    book_id: int
    title: str | None
    author: str | None
    library: str | None
