"""Tests for the BookSearchService application layer."""

import pytest

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.domain.models.search_result import SearchResult


class FakeIndex:
    """Controlled search index used to test request validation."""

    def __init__(self) -> None:
        self.last_query: str | None = None
        self.last_limit: int | None = None

    def search(self, query: str, limit: int) -> tuple[SearchResult, ...]:
        """Record the request and return one fixed result."""
        self.last_query = query
        self.last_limit = limit
        return (SearchResult(book_id=1, title="Title", author="Author", page_number=1, excerpt="..."),)


def test_search_delegates_normalized_query_and_limit() -> None:
    """A surrounding-whitespace query is trimmed before reaching the index."""
    index = FakeIndex()

    results = BookSearchService(index).search("  jurisprudence  ", limit=5)

    assert index.last_query == "jurisprudence"
    assert index.last_limit == 5
    assert len(results) == 1


def test_search_rejects_blank_query() -> None:
    """A blank or whitespace-only query is rejected before hitting the index."""
    with pytest.raises(ValueError):
        BookSearchService(FakeIndex()).search("   ")


def test_search_rejects_non_positive_limit() -> None:
    """A limit below one is rejected before hitting the index."""
    with pytest.raises(ValueError):
        BookSearchService(FakeIndex()).search("query", limit=0)
