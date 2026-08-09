"""Developer Public API Facade for Islamic Research Hub AI.

Phase 19 feature: provides a clean, typed Python API interface for external
developer tools, scripts, and third-party integrations to query search,
retrieve book metadata/pages, translate text, and resolve paragraph citations.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.text_translation import PageTranslationService
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ApiSearchResult:
    """Standard search result item returned by the public API."""

    book_id: int
    book_title: str
    author: str
    page_no: int
    snippet: str


@dataclass(frozen=True, slots=True)
class ApiBookDetails:
    """Standard book detail payload returned by the public API."""

    book_id: int
    title: str
    author: str
    publisher: str
    language: str
    category: str
    page_count: int
    chapter_count: int


class IslamicResearchHubAPI:
    """Public Programmatic API Facade for Islamic Research Hub AI (Phase 19)."""

    def __init__(
        self,
        database_path: Path | str = Path("data/books.db"),
        repository: MasterBookRepository | None = None,
        search_service: BookSearchService | None = None,
        translation_service: PageTranslationService | None = None,
    ) -> None:
        self.db_path = Path(database_path)
        self._repository = repository or MasterBookRepository(self.db_path)
        self._search_service = search_service or BookSearchService(self._repository)
        self._translation_service = translation_service

    def search(
        self, query: str, exact: bool = False, limit: int = 20
    ) -> tuple[ApiSearchResult, ...]:
        """Search the corpus by keyword/phrase with optional exact matching."""
        if not query.strip():
            return ()
        raw_results = self._search_service.search_content(
            query=query.strip(), exact_match=exact, limit=limit
        )
        results: list[ApiSearchResult] = []
        for r in raw_results:
            results.append(
                ApiSearchResult(
                    book_id=r.book_id,
                    book_title=r.book_title,
                    author=r.author,
                    page_no=r.page_no,
                    snippet=r.snippet,
                )
            )
        return tuple(results)

    def get_book_details(self, book_id: int) -> ApiBookDetails | None:
        """Retrieve complete catalog metadata for a specific book."""
        detail = self._repository.get_book_detail(book_id)
        if detail is None:
            return None
        return ApiBookDetails(
            book_id=detail.book_id,
            title=detail.title or "Untitled",
            author=detail.author or "Unknown Author",
            publisher=detail.publisher or "",
            language=detail.language or "",
            category=detail.category or "",
            page_count=detail.page_count or 0,
            chapter_count=detail.chapter_count or 0,
        )

    def get_page_content(self, book_id: int, page_no: int) -> str | None:
        """Retrieve full textual page content for a specific book and page number."""
        return self._repository.get_page_content(book_id, page_no)

    def translate_text(
        self, text: str, source_language: str = "Arabic", target_language: str = "Urdu"
    ) -> str:
        """Translate Arabic or English text into Urdu or English."""
        if not text.strip() or self._translation_service is None:
            return text.strip()
        return self._translation_service.translate(
            text=text, source_language=source_language, target_language=target_language
        )

    def format_paragraph_citation(
        self, book_id: int, page_no: int, paragraph_id: str | None = None
    ) -> str:
        """Format a standardized academic citation string."""
        details = self.get_book_details(book_id)
        title = details.title if details else f"Book #{book_id}"
        author = details.author if details else "Unknown"

        citation = f"{title} by {author}, Page {page_no}"
        if paragraph_id:
            formatted_pid = (
                paragraph_id
                if paragraph_id.startswith("P-")
                else f"P-{paragraph_id}"
            )
            citation += f" ({formatted_pid})"
        return citation
