"""Tests for the BookSearchService application layer."""

import pytest

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.domain.models.search_result import SearchResult


class FakeIndex:
    """Controlled search index used to test request validation."""

    def __init__(self) -> None:
        self.last_query: str | None = None
        self.last_limit: int | None = None
        self.last_library: str | None = None
        self.last_author: str | None = None
        self.last_category: str | None = None

    def search(
        self,
        query: str,
        limit: int,
        library: str | None = None,
        author: str | None = None,
        category: str | None = None,
    ) -> tuple[SearchResult, ...]:
        """Record the request and return one fixed result."""
        self.last_query = query
        self.last_limit = limit
        self.last_library = library
        self.last_author = author
        self.last_category = category
        return (SearchResult(book_id=1, title="Title", author="Author", page_number=1, excerpt="..."),)


def test_search_delegates_normalized_query_and_limit() -> None:
    """A surrounding-whitespace query is trimmed before reaching the index."""
    index = FakeIndex()

    results = BookSearchService(index).search("  jurisprudence  ", limit=5)

    assert index.last_query == "jurisprudence"
    assert index.last_limit == 5
    assert len(results) == 1


def test_search_passes_through_library_filter() -> None:
    """An optional library filter reaches the index unchanged."""
    index = FakeIndex()

    BookSearchService(index).search("query", library="Maktaba Al-Maknoon")

    assert index.last_library == "Maktaba Al-Maknoon"


def test_search_passes_through_author_and_category_filters() -> None:
    """Optional author and category filters reach the index unchanged."""
    index = FakeIndex()

    BookSearchService(index).search("query", author="Ibn Kathir", category="Fiqh")

    assert index.last_author == "Ibn Kathir"
    assert index.last_category == "Fiqh"


def test_search_rejects_blank_query() -> None:
    """A blank or whitespace-only query is rejected before hitting the index."""
    with pytest.raises(ValueError):
        BookSearchService(FakeIndex()).search("   ")


def test_search_rejects_non_positive_limit() -> None:
    """A limit below one is rejected before hitting the index."""
    with pytest.raises(ValueError):
        BookSearchService(FakeIndex()).search("query", limit=0)
