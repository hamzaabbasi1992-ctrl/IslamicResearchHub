"""Domain model for Phase 14 deferred scope: a real, named saved search
that can be re-run with one click, capturing every real filter the
Search screen supports."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SavedSearch:
    """One real, named saved search - every field mirrors a real filter
    `SearchScreen._run_search()` already sends to `BookSearchService`/
    `HybridSearchService`, so re-running one reproduces the exact same
    real search, not an approximation of it."""

    saved_search_id: int
    name: str
    query: str
    library: str | None
    author: str | None
    category: str | None
    exact: bool
    scope: str
    search_target: str
    created_at: str
