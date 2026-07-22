"""Tests for the SemanticBookSearchService application layer."""

import pytest

from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult


class FakeEmbedder:
    """Embedder returning a fixed vector, recording the text it was asked to embed."""

    def __init__(self) -> None:
        self.last_texts: tuple[str, ...] | None = None

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Record the input and return one fixed vector per text."""
        self.last_texts = texts
        return tuple((1.0, 0.0) for _ in texts)


class FakeIndex:
    """Controlled semantic index used to test request validation."""

    def __init__(self) -> None:
        self.last_embedding: tuple[float, ...] | None = None
        self.last_limit: int | None = None

    def search(
        self, embedding: tuple[float, ...], limit: int
    ) -> tuple[SemanticSearchResult, ...]:
        """Record the request and return one fixed result."""
        self.last_embedding = embedding
        self.last_limit = limit
        return (
            SemanticSearchResult(
                book_id=1, title="Title", author="Author", page_number=1,
                excerpt="...", similarity=0.9,
            ),
        )


def test_search_embeds_normalized_query_and_delegates() -> None:
    """A surrounding-whitespace query is trimmed, embedded, then searched."""
    embedder = FakeEmbedder()
    index = FakeIndex()

    results = SemanticBookSearchService(embedder, index).search("  mercy  ", limit=5)

    assert embedder.last_texts == ("mercy",)
    assert index.last_embedding == (1.0, 0.0)
    assert index.last_limit == 5
    assert len(results) == 1


def test_search_rejects_blank_query() -> None:
    """A blank or whitespace-only query is rejected before embedding."""
    with pytest.raises(ValueError):
        SemanticBookSearchService(FakeEmbedder(), FakeIndex()).search("   ")


def test_search_rejects_non_positive_limit() -> None:
    """A limit below one is rejected before embedding."""
    with pytest.raises(ValueError):
        SemanticBookSearchService(FakeEmbedder(), FakeIndex()).search("query", limit=0)
