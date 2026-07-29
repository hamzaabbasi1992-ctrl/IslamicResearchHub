"""Background worker: run semantic search off the GUI thread.

Loading the local embedding model has a real, measured one-time Python
import cost (~20+ seconds for `sentence_transformers`/`torch`, confirmed
directly - see CHANGELOG), and even a warm search scans the whole
embedding table (a few seconds today, growing with corpus size). Neither
cost may block the GUI thread, or even delay the fast keyword-search
results that should appear immediately regardless of whether semantic
search is enabled at all.
"""

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService


class SemanticSearchWorker(QThread):
    """Build (if needed, once) and query the semantic search service, off the GUI thread."""

    search_succeeded = Signal(str, object)  # query, tuple[SemanticSearchResult, ...]
    search_failed = Signal(str)  # query

    def __init__(
        self,
        get_service: Callable[[], SemanticBookSearchService | None],
        query: str,
        limit: int,
        library: str | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._query = query
        self._limit = limit
        self._library = library

    def run(self) -> None:
        try:
            service = self._get_service()
            if service is None:
                self.search_failed.emit(self._query)
                return
            results = service.search(self._query, self._limit, self._library)
        except Exception:
            self.search_failed.emit(self._query)
            return
        self.search_succeeded.emit(self._query, results)
