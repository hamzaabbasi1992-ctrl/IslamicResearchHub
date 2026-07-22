"""Application service for full-text search across the master book database."""

from typing import Protocol

from islamic_research_hub.domain.models.search_result import SearchResult


class SearchIndex(Protocol):
    """Contract for a full-text search backend over imported book pages."""

    def search(self, query: str, limit: int) -> tuple[SearchResult, ...]:
        """Return the top matching pages for a free-text query."""


class BookSearchService:
    """Validate search requests and delegate to the configured search index."""

    def __init__(self, index: SearchIndex) -> None:
        self._index = index

    def search(self, query: str, limit: int = 20) -> tuple[SearchResult, ...]:
        """Search the library, rejecting blank queries and non-positive limits."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be empty.")
        if limit < 1:
            raise ValueError("Search limit must be at least 1.")
        return self._index.search(normalized_query, limit)
