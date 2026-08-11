"""MCP tools for named research collections (reading lists).

Thin wrappers over `CollectionRepository` - no new persistence logic.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from islamic_research_hub.infrastructure.persistence.collection_repository import (
    CollectionNameTakenError,
    CollectionRepository,
)


def register_collection_tools(mcp: MCPServer, database_path: Path) -> None:
    """Register collection create/rename/delete/list and item add/remove/list tools."""
    repository = CollectionRepository(database_path)

    @mcp.tool()
    def create_collection(name: str) -> dict:
        """Create a new, empty named collection and return its id."""
        try:
            collection_id = repository.create_collection(name)
        except (ValueError, CollectionNameTakenError) as error:
            raise ValueError(str(error)) from error
        return {"collection_id": collection_id, "name": name}

    @mcp.tool()
    def rename_collection(collection_id: int, new_name: str) -> dict:
        """Rename an existing collection."""
        try:
            repository.rename_collection(collection_id, new_name)
        except (ValueError, CollectionNameTakenError) as error:
            raise ValueError(str(error)) from error
        return {"collection_id": collection_id, "name": new_name}

    @mcp.tool()
    def delete_collection(collection_id: int) -> dict:
        """Delete a collection and every item in it."""
        repository.delete_collection(collection_id)
        return {"collection_id": collection_id, "deleted": True}

    @mcp.tool()
    def list_collections() -> list[dict]:
        """Return every collection, most recently created first, with its item count."""
        return [
            {
                "collection_id": collection.collection_id,
                "name": collection.name,
                "created_at": collection.created_at,
                "item_count": collection.item_count,
            }
            for collection in repository.list_collections()
        ]

    @mcp.tool()
    def add_to_collection(collection_id: int, book_id: int, page_number: int) -> dict:
        """Add one book/page to a collection. Safe to call more than once for the same page."""
        repository.add_item(collection_id, book_id, page_number)
        return {"collection_id": collection_id, "book_id": book_id, "page_number": page_number}

    @mcp.tool()
    def remove_from_collection(collection_id: int, book_id: int, page_number: int) -> dict:
        """Remove one book/page from a collection."""
        repository.remove_item(collection_id, book_id, page_number)
        return {"collection_id": collection_id, "book_id": book_id, "page_number": page_number}

    @mcp.tool()
    def list_collection_items(collection_id: int) -> list[dict]:
        """Return every item in one collection, in the order they were added."""
        return [
            {
                "book_id": item.book_id,
                "page_number": item.page_number,
                "book_title": item.book_title,
                "added_at": item.added_at,
            }
            for item in repository.list_items(collection_id)
        ]
