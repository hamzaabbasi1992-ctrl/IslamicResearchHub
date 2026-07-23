"""Tests for the HybridSearchService Reciprocal Rank Fusion logic."""

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.hybrid_search import HybridSearchService
from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult


class FakeKeywordIndex:
    """Returns a fixed, ordered list of keyword results."""

    def __init__(self, results: tuple[SearchResult, ...]) -> None:
        self._results = results

    def search(self, query, limit, library=None):
        return self._results[:limit]


class FakeEmbedder:
    """Embedder stub; the fake semantic index ignores the actual vector."""

    def embed(self, texts):
        return tuple((0.0,) for _ in texts)


class FakeSemanticIndex:
    """Returns a fixed, ordered list of semantic results."""

    def __init__(self, results: tuple[SemanticSearchResult, ...]) -> None:
        self._results = results

    def search(self, embedding, limit, library=None):
        return self._results[:limit]


def _search_result(book_id: int, page: int, excerpt: str = "kw excerpt") -> SearchResult:
    return SearchResult(
        book_id=book_id, title=f"Book {book_id}", author="Author", page_number=page,
        excerpt=excerpt, library="Lib A",
    )


def _semantic_result(book_id: int, page: int, similarity: float = 0.9) -> SemanticSearchResult:
    return SemanticSearchResult(
        book_id=book_id, title=f"Book {book_id}", author="Author", page_number=page,
        excerpt="semantic excerpt", similarity=similarity, library="Lib A",
    )


def test_falls_back_to_keyword_only_when_no_semantic_service() -> None:
    """With no semantic service configured, results come from keyword search alone."""
    keyword_service = BookSearchService(FakeKeywordIndex((_search_result(1, 1),)))

    results = HybridSearchService(keyword_service).search("query")

    assert len(results) == 1
    assert results[0].matched_by == ("keyword",)


def test_page_found_by_both_combines_scores_and_prefers_keyword_excerpt() -> None:
    """A page appearing in both result sets gets a combined score and the keyword excerpt."""
    keyword_service = BookSearchService(
        FakeKeywordIndex((_search_result(1, 1, excerpt="highlighted **term**"),))
    )
    semantic_service = SemanticBookSearchService(
        FakeEmbedder(), FakeSemanticIndex((_semantic_result(1, 1),))
    )

    results = HybridSearchService(keyword_service, semantic_service).search("query")

    assert len(results) == 1
    assert results[0].matched_by == ("keyword", "semantic")
    assert results[0].excerpt == "highlighted **term**"


def test_keyword_only_and_semantic_only_hits_both_appear() -> None:
    """Pages found by only one ranker still appear, ranked below combined hits."""
    keyword_service = BookSearchService(FakeKeywordIndex((_search_result(1, 1),)))
    semantic_service = SemanticBookSearchService(
        FakeEmbedder(), FakeSemanticIndex((_semantic_result(2, 1),))
    )

    results = HybridSearchService(keyword_service, semantic_service).search("query")

    book_ids = {r.book_id for r in results}
    assert book_ids == {1, 2}
    matched_by_book = {r.book_id: r.matched_by for r in results}
    assert matched_by_book[1] == ("keyword",)
    assert matched_by_book[2] == ("semantic",)


def test_combined_match_ranks_above_single_source_match() -> None:
    """A page found by both rankers outranks one found by only a single ranker."""
    keyword_service = BookSearchService(
        FakeKeywordIndex((_search_result(1, 1), _search_result(2, 1)))
    )
    semantic_service = SemanticBookSearchService(
        FakeEmbedder(), FakeSemanticIndex((_semantic_result(2, 1),))
    )

    results = HybridSearchService(keyword_service, semantic_service).search("query")

    assert results[0].book_id == 2
    assert results[0].matched_by == ("keyword", "semantic")


def test_respects_limit() -> None:
    """No more than `limit` results are returned even with a larger pool."""
    keyword_service = BookSearchService(
        FakeKeywordIndex(tuple(_search_result(i, 1) for i in range(10)))
    )

    results = HybridSearchService(keyword_service).search("query", limit=3, pool_size=10)

    assert len(results) == 3
