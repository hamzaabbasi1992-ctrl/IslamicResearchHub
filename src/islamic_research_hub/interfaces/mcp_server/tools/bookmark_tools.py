"""MCP tools for per-book, per-page bookmarks.

Thin wrappers over `BookmarkRepository` - no new persistence logic.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from islamic_research_hub.infrastructure.persistence.bookmark_repository import (
    BookmarkRepository,
)


def register_bookmark_tools(mcp: MCPServer, database_path: Path) -> None:
    """Register `add_bookmark`, `remove_bookmark`, `list_bookmarked_pages`, `list_recent_bookmarks`."""
    repository = BookmarkRepository(database_path)

    @mcp.tool()
    def add_bookmark(book_id: int, page_number: int) -> dict:
        """Bookmark one page of one book. Safe to call more than once for the same page."""
        repository.add_bookmark(book_id, page_number)
        return {"book_id": book_id, "page_number": page_number, "bookmarked": True}

    @mcp.tool()
    def remove_bookmark(book_id: int, page_number: int) -> dict:
        """Remove a bookmark, if it exists."""
        repository.remove_bookmark(book_id, page_number)
        return {"book_id": book_id, "page_number": page_number, "bookmarked": False}

    @mcp.tool()
    def list_bookmarked_pages(book_id: int) -> list[int]:
        """Return every bookmarked page number for one book."""
        return sorted(repository.list_bookmarked_pages(book_id))

    @mcp.tool()
    def list_recent_bookmarks(limit: int = 5) -> list[dict]:
        """Return the most recently created bookmarks across the whole library, most recent first."""
        return [
            {"book_id": bookmark.book_id, "page_number": bookmark.page_number, "title": bookmark.title}
            for bookmark in repository.list_recent_bookmarks(limit)
        ]
