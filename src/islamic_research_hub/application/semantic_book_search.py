"""Application service for semantic (embedding-based) search over pages."""

from typing import Protocol

from islamic_research_hub.application.page_embedding import TextEmbedder
from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult


class SemanticSearchIndex(Protocol):
    """Contract for a nearest-neighbor search backend over page embeddings."""

    def search(
        self, embedding: tuple[float, ...], limit: int
    ) -> tuple[SemanticSearchResult, ...]:
        """Return the top matching pages for a query embedding."""


class SemanticBookSearchService:
    """Validate semantic search requests and delegate to the embedding index."""

    def __init__(self, embedder: TextEmbedder, index: SemanticSearchIndex) -> None:
        self._embedder = embedder
        self._index = index

    def search(self, query: str, limit: int = 20) -> tuple[SemanticSearchResult, ...]:
        """Embed the query and return the top semantically similar pages."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be empty.")
        if limit < 1:
            raise ValueError("Search limit must be at least 1.")
        (embedding,) = self._embedder.embed((normalized_query,))
        return self._index.search(embedding, limit)
