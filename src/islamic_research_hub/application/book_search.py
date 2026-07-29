"""Application service for full-text search across the master book database."""

from typing import Protocol

from islamic_research_hub.domain.models.search_result import SearchResult


class SearchIndex(Protocol):
    """Contract for a full-text search backend over imported book pages."""

    def search(
        self,
        query: str,
        limit: int,
        library: str | None = None,
        author: str | None = None,
        category: str | None = None,
        exact: bool = False,
        scope: str = "content",
    ) -> tuple[SearchResult, ...]:
        """Return the top matching pages for a free-text query.

        `exact=True` requires literal spelling (no diacritic/letter-form/
        cross-keyboard normalization); `exact=False` (the default) is
        tolerant of real spelling variants, as before. `scope` is
        `"content"` (main page text, default), `"footnotes"`, or `"both"`.
        """


class BookSearchService:
    """Validate search requests and delegate to the configured search index."""

    def __init__(self, index: SearchIndex) -> None:
        self._index = index

    def search(
        self,
        query: str,
        limit: int = 20,
        library: str | None = None,
        author: str | None = None,
        category: str | None = None,
        exact: bool = False,
        scope: str = "content",
    ) -> tuple[SearchResult, ...]:
        """Search the library, rejecting blank queries and non-positive limits.

        `library`, `author`, and `category` each restrict results when given.
        `exact=True` requires literal spelling; the default (`False`) is
        tolerant of real spelling/keyboard variants (see
        `shared/arabic_text_normalization.py`). `scope` restricts a search
        to main page text (`"content"`, the default), footnotes/commentary
        (`"footnotes"`), or both (`"both"`).
        """
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Search query must not be empty.")
        if limit < 1:
            raise ValueError("Search limit must be at least 1.")
        if scope not in ("content", "footnotes", "both"):
            raise ValueError('scope must be "content", "footnotes", or "both".')
        return self._index.search(normalized_query, limit, library, author, category, exact, scope)
