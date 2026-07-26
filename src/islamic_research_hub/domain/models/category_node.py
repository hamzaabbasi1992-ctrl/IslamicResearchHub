"""Typed model for one node in the category browsing tree."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CategoryNode:
    """One category, its real book count, and its child categories."""

    mjcn: int
    name: str
    book_count: int
    children: tuple["CategoryNode", ...] = ()
