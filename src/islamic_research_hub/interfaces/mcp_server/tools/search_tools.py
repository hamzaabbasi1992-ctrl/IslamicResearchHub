"""MCP tools for full-text search and citation lookup.

Thin wrappers over `BookSearchService`/`SqliteBookSearchRepository`/
`BookBrowserRepository`/`format_citation` - the exact code the desktop
Search screen already uses, no new search or citation logic.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
    BookSearchError,
    SqliteBookSearchRepository,
)
from islamic_research_hub.shared.citation_formatting import format_citation
from islamic_research_hub.shared.maktaba_link import build_maktaba_link


def register_search_tools(mcp: MCPServer, database_path: Path) -> None:
    """Register `search_text`, `get_citation`, `get_open_link`, and `health_check`."""
    search_service = BookSearchService(SqliteBookSearchRepository(database_path))
    browser_repository = BookBrowserRepository(database_path)

    @mcp.tool()
    def search_text(
        query: str,
        limit: int = 20,
        library: str | None = None,
        author: str | None = None,
        category: str | None = None,
        exact: bool = False,
        scope: str = "content",
    ) -> list[dict]:
        """Search the library's full text and return ranked matching pages.

        `scope` is "content" (main page text, default), "footnotes", or
        "both". `exact=True` requires literal spelling; the default is
        tolerant of real spelling/keyboard variants.
        """
        try:
            results = search_service.search(
                query, limit, library, author, category, exact, scope
            )
        except (ValueError, BookSearchError) as error:
            raise ValueError(str(error)) from error
        return [
            {
                "book_id": result.book_id,
                "title": result.title,
                "author": result.author,
                "page_number": result.page_number,
                "excerpt": result.excerpt,
                "library": result.library,
                "source": result.source,
            }
            for result in results
        ]

    @mcp.tool()
    def get_citation(book_id: int, page_number: int, paragraph_index: int) -> str:
        """Return a formatted citation string for one paragraph of one book."""
        metadata = browser_repository.get_book_metadata(book_id)
        if metadata is None:
            raise ValueError(f"No book found with book_id={book_id}.")
        return format_citation(
            metadata.title or "(untitled)",
            page_number,
            paragraph_index,
            metadata.volume_number,
        )

    @mcp.tool()
    def get_open_link(book_id: int, page_number: int) -> str:
        """Return a maktaba:// link that opens this book at this page in
        the desktop app's reader, for cross-checking a quoted/extracted
        passage against its real source. Requires the maktaba:// protocol
        handler to be registered on the user's machine (a one-time local
        setup step, not something this tool does) - if links don't open,
        that registration is what to check.
        """
        return build_maktaba_link(book_id, page_number)

    @mcp.tool()
    def health_check() -> dict:
        """Confirm the configured database path exists and is readable."""
        return {"database_path": str(database_path), "reachable": database_path.is_file()}
