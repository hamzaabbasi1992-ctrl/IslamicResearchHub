"""Real tools the AI Agent can call - thin JSON wrappers around this
project's already-existing, already-tested search and retrieval services.

No new retrieval logic lives here: every tool delegates directly to
`BookSearchService`, `SemanticBookSearchService`, or `BookBrowserRepository`.
This module's only real job is translation (Python objects <-> the small
JSON shape a tool-calling model expects) and the two safety limits that
keep an agentic loop from running away: a hard page cap on
`get_book_pages` and (for the tool-calling loop itself) a hard iteration
cap enforced in `ai_agent_service.py`, not here.
"""

import json
from collections.abc import Callable

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.llm_provider import ToolDefinition
from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.domain.models.book import Chapter
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.shared.citation_formatting import format_citation
from islamic_research_hub.shared.html_text_extraction import strip_html_to_text

MAX_PAGES_PER_CALL = 20
"""A real, enforced ceiling on `get_book_pages` - the one tool that could
otherwise pull an entire multi-hundred-page book into context in one call.
A caller wanting more must page through with successive calls."""

SEARCH_BOOKS_TOOL = ToolDefinition(
    name="search_books",
    description=(
        "Full-text keyword search across the library's real page content. "
        "Best for exact terms/phrases. Tolerant of common spelling/keyboard "
        "variants unless exact=true."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
            "library": {"type": "string"},
            "author": {"type": "string"},
            "category": {"type": "string"},
            "exact": {"type": "boolean", "default": False},
            "scope": {
                "type": "string",
                "enum": ["content", "footnotes", "both"],
                "default": "content",
            },
        },
        "required": ["query"],
    },
)

SEMANTIC_SEARCH_BOOKS_TOOL = ToolDefinition(
    name="semantic_search_books",
    description=(
        "Meaning-based search across the library's real page content. Best "
        "for conceptual or paraphrased questions where the exact wording is "
        "unknown - finds pages about the same idea, not just matching words."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 10},
            "library": {"type": "string"},
        },
        "required": ["query"],
    },
)

GET_BOOK_METADATA_TOOL = ToolDefinition(
    name="get_book_metadata",
    description="Real catalog details for one book: title, author, publisher, language, category, library, page/chapter counts, series/volume.",
    input_schema={
        "type": "object",
        "properties": {"book_id": {"type": "integer"}},
        "required": ["book_id"],
    },
)

LIST_CHAPTERS_TOOL = ToolDefinition(
    name="list_chapters",
    description="Real table-of-contents tree for one book - chapter titles and the page each one starts on. Use this to find a real page range before calling get_book_pages for a specific chapter.",
    input_schema={
        "type": "object",
        "properties": {"book_id": {"type": "integer"}},
        "required": ["book_id"],
    },
)

GET_BOOK_PAGES_TOOL = ToolDefinition(
    name="get_book_pages",
    description=(
        f"Real page text for one book, in a page-number range (inclusive). "
        f"Capped at {MAX_PAGES_PER_CALL} pages per call - a truncated "
        "response says so explicitly; call again with a later start_page "
        "to continue."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "book_id": {"type": "integer"},
            "start_page": {"type": "integer"},
            "end_page": {"type": "integer"},
        },
        "required": ["book_id", "start_page", "end_page"],
    },
)

ALL_TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    SEARCH_BOOKS_TOOL,
    SEMANTIC_SEARCH_BOOKS_TOOL,
    GET_BOOK_METADATA_TOOL,
    LIST_CHAPTERS_TOOL,
    GET_BOOK_PAGES_TOOL,
)


class AgentToolExecutor:
    """Expose this project's real search/retrieval services as agent tools."""

    def __init__(
        self,
        book_search: BookSearchService,
        semantic_search: SemanticBookSearchService | None,
        browser: BookBrowserRepository,
    ) -> None:
        self._book_search = book_search
        self._semantic_search = semantic_search
        self._browser = browser
        self._dispatch: dict[str, Callable[[dict], str]] = {
            "search_books": self._search_books,
            "semantic_search_books": self._semantic_search_books,
            "get_book_metadata": self._get_book_metadata,
            "list_chapters": self._list_chapters,
            "get_book_pages": self._get_book_pages,
        }

    def tool_definitions(self) -> tuple[ToolDefinition, ...]:
        """Every real tool available right now - `semantic_search_books`
        is left out entirely (not declared-but-erroring) when semantic
        search isn't available."""
        if self._semantic_search is not None:
            return ALL_TOOL_DEFINITIONS
        return tuple(
            tool for tool in ALL_TOOL_DEFINITIONS if tool.name != "semantic_search_books"
        )

    def execute(self, tool_name: str, tool_input: dict) -> tuple[str, bool]:
        """Run one real tool call. Returns (content, is_error) - an unknown
        tool name or any raised exception both become a real, catchable
        error result fed back to the model, never a crash of the loop."""
        handler = self._dispatch.get(tool_name)
        if handler is None:
            return f'Unknown tool: "{tool_name}".', True
        try:
            return handler(tool_input), False
        except Exception as error:
            return str(error) or f"{tool_name} failed.", True

    def _search_books(self, tool_input: dict) -> str:
        results = self._book_search.search(
            query=tool_input["query"],
            limit=int(tool_input.get("limit", 10)),
            library=tool_input.get("library"),
            author=tool_input.get("author"),
            category=tool_input.get("category"),
            exact=bool(tool_input.get("exact", False)),
            scope=tool_input.get("scope", "content"),
        )
        return json.dumps([_search_result_json(result) for result in results])

    def _semantic_search_books(self, tool_input: dict) -> str:
        if self._semantic_search is None:
            return json.dumps({"error": "Semantic search is not available."})
        results = self._semantic_search.search(
            query=tool_input["query"],
            limit=int(tool_input.get("limit", 10)),
            library=tool_input.get("library"),
        )
        return json.dumps(
            [
                {**_search_result_json(result), "similarity": result.similarity}
                for result in results
            ]
        )

    def _get_book_metadata(self, tool_input: dict) -> str:
        metadata = self._browser.get_book_metadata(int(tool_input["book_id"]))
        if metadata is None:
            return json.dumps({"error": "No book found with that book_id."})
        return json.dumps(
            {
                "book_id": metadata.book_id,
                "title": metadata.title,
                "author": metadata.author,
                "publisher": metadata.publisher,
                "language": metadata.language,
                "category": metadata.category,
                "library": metadata.library,
                "page_count": metadata.page_count,
                "chapter_count": metadata.chapter_count,
                "series_title": metadata.series_title,
                "volume_number": metadata.volume_number,
            }
        )

    def _list_chapters(self, tool_input: dict) -> str:
        chapters = self._browser.list_chapters(int(tool_input["book_id"]))
        return json.dumps([_chapter_json(chapter) for chapter in chapters])

    def _get_book_pages(self, tool_input: dict) -> str:
        book_id = int(tool_input["book_id"])
        start_page = int(tool_input["start_page"])
        end_page = int(tool_input["end_page"])
        detail = self._browser.get_book_detail(book_id)
        if detail is None:
            return json.dumps({"error": "No book found with that book_id."})
        title, _author, pages = detail
        in_range = sorted(
            (page for page in pages if page.page_number is not None
             and start_page <= page.page_number <= end_page),
            key=lambda page: page.page_number,
        )
        truncated = len(in_range) > MAX_PAGES_PER_CALL
        shown = in_range[:MAX_PAGES_PER_CALL]
        result = {
            "book_id": book_id,
            "title": title,
            "pages": [
                {
                    "page_number": page.page_number,
                    "text": strip_html_to_text(page.content_f) or "",
                    "citation": format_citation(title or "(untitled)", page.page_number, paragraph_index=1),
                }
                for page in shown
            ],
            "truncated": truncated,
        }
        if truncated:
            result["truncation_note"] = (
                f"Showing {len(shown)} of {len(in_range)} requested pages "
                f"(book_id={book_id}, pages {start_page}-{end_page}). Call "
                f"again with start_page={shown[-1].page_number + 1} to continue."
            )
        return json.dumps(result)


def _search_result_json(result) -> dict:
    return {
        "book_id": result.book_id,
        "title": result.title,
        "author": result.author,
        "page_number": result.page_number,
        "excerpt": result.excerpt,
        "library": result.library,
        "citation": (
            format_citation(result.title or "(untitled)", result.page_number, paragraph_index=1)
            if result.page_number is not None
            else None
        ),
    }


def _chapter_json(chapter: Chapter) -> dict:
    return {
        "title": chapter.title,
        "page_number": chapter.page_number,
        "children": [_chapter_json(child) for child in chapter.children],
    }
