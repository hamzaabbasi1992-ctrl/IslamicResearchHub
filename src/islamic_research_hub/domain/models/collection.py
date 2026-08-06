"""Domain models for Phase 14 Milestone 1: named research collections
that group real bookmarked pages together."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Collection:
    """One real, named collection."""

    collection_id: int
    name: str
    created_at: str
    item_count: int


@dataclass(frozen=True, slots=True)
class CollectionItem:
    """One real book/page reference inside a collection."""

    book_id: int
    page_number: int
    book_title: str
    added_at: str
