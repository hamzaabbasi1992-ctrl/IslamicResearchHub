"""Application service for semantic (embedding-based) search over pages."""

from typing import Protocol

from islamic_research_hub.application.page_embedding import TextEmbedder
from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult
from islamic_research_hub.shared.language_names import detect_language_from_text


class SemanticSearchIndex(Protocol):
    """Contract for a nearest-neighbor search backend over page embeddings."""

    def search(
        self,
        embedding: tuple[float, ...],
        limit: int,
        library: str | None = None,
        query_language: str | None = None,
    ) -> tuple[SemanticSearchResult, ...]:
        """Return the top matching pages for a query embedding.

        `query_language`, when given, lets the index correct for a real,
        confirmed corpus-imbalance/cross-lingual-alignment problem (a
        query's own language systematically under-ranking real matches
        in that same language) - see `SqlitePageEmbeddingRepository`'s
        own docstring for the measured evidence.
        """


class SemanticBookSearchService:
    """Validate semantic search requests and delegate to the embedding index."""

    def __init__(self, embedder: TextEmbedder, index: SemanticSearchIndex) -> None:
        self._embedder = embedder
        self._index = index

    def search(
        self, query: str, limit: int = 20, library: str | None = None
    ) -> tuple[SemanticSearchResult, ...]:
        """Embed the query and return the top semantically similar pages.

        Detects the query's own language (the same heuristic already
        used for narration/translation language resolution) and passes
        it to the index so real same-language matches aren't
        systematically buried under a numerically larger other-language
        pool - see `SqlitePageEmbeddingRepository.search()`.
        """
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be empty.")
        if limit < 1:
            raise ValueError("Search limit must be at least 1.")
        (embedding,) = self._embedder.embed((normalized_query,))
        query_language = detect_language_from_text(normalized_query)
        return self._index.search(embedding, limit, library, query_language=query_language)
