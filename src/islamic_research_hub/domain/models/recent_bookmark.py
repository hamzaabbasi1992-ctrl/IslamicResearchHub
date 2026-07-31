"""Typed model for one real bookmark, with enough context to show/open it."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecentBookmark:
    """One real bookmarked page, for a "recent bookmarks" listing."""

    book_id: int
    page_number: int
    title: str | None
