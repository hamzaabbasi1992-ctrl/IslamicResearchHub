"""Application service for hybrid (keyword + semantic) search over pages."""

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.domain.models.hybrid_search_result import HybridSearchResult

RRF_K = 60
DEFAULT_POOL_SIZE = 50

ResultKey = tuple[int, int | None]


class HybridSearchService:
    """Fuse keyword and semantic search results with Reciprocal Rank Fusion.

    Semantic search is optional: when no semantic service is configured, or
    the embedding index simply does not cover the matched pages (it may only
    be built for part of the corpus), results fall back to keyword-only
    ranking rather than failing. When a page is found by both, its scores
    combine and its keyword excerpt (highlighted) is preferred over the
    semantic one.
    """

    def __init__(
        self,
        keyword_service: BookSearchService,
        semantic_service: SemanticBookSearchService | None = None,
    ) -> None:
        self._keyword_service = keyword_service
        self._semantic_service = semantic_service

    def search(
        self,
        query: str,
        limit: int = 20,
        library: str | None = None,
        pool_size: int = DEFAULT_POOL_SIZE,
    ) -> tuple[HybridSearchResult, ...]:
        """Search both indexes and return one fused, ranked result list."""
        effective_pool_size = max(pool_size, limit)
        keyword_results = self._keyword_service.search(query, effective_pool_size, library)
        semantic_results = (
            self._semantic_service.search(query, effective_pool_size, library)
            if self._semantic_service is not None
            else ()
        )

        scores: dict[ResultKey, float] = {}
        matched_by: dict[ResultKey, set[str]] = {}
        details: dict[ResultKey, dict[str, object]] = {}

        for rank, result in enumerate(keyword_results, start=1):
            key = (result.book_id, result.page_number)
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
            matched_by.setdefault(key, set()).add("keyword")
            details[key] = {
                "title": result.title,
                "author": result.author,
                "library": result.library,
                "excerpt": result.excerpt,
            }

        for rank, result in enumerate(semantic_results, start=1):
            key = (result.book_id, result.page_number)
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
            matched_by.setdefault(key, set()).add("semantic")
            details.setdefault(
                key,
                {
                    "title": result.title,
                    "author": result.author,
                    "library": result.library,
                    "excerpt": result.excerpt,
                },
            )

        ranked_keys = sorted(scores, key=lambda key: scores[key], reverse=True)[:limit]
        return tuple(
            HybridSearchResult(
                book_id=key[0],
                title=details[key]["title"],
                author=details[key]["author"],
                page_number=key[1],
                library=details[key]["library"],
                excerpt=details[key]["excerpt"],
                score=scores[key],
                matched_by=tuple(sorted(matched_by[key])),
            )
            for key in ranked_keys
        )
