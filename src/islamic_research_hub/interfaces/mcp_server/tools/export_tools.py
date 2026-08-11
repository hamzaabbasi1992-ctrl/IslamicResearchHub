"""MCP tools that save real .docx documents: a Q&A answer, a saved
collection, or an already-composed article/chapter.

Each wraps an existing pure `build_*()`/`export_*_to_docx()` pair from
`research_notes/` - this module only hydrates the inputs those functions
need from the repositories (for the collection export) and adapts
MCP-friendly (JSON) argument shapes into the real dataclasses those
functions expect. No new document-formatting logic.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.collection_repository import (
    CollectionRepository,
)
from islamic_research_hub.research_notes.ai_answer_export import (
    export_answer_to_docx as save_answer_docx,
)
from islamic_research_hub.research_notes.article_export import ArticleSection
from islamic_research_hub.research_notes.article_export import (
    export_article_to_docx as save_article_docx,
)
from islamic_research_hub.research_notes.collection_export import CollectionExportItem
from islamic_research_hub.research_notes.collection_export import (
    export_collection_to_docx as save_collection_docx,
)


def register_export_tools(mcp: MCPServer, database_path: Path) -> None:
    """Register `export_answer_to_docx`, `export_collection_to_docx`, `export_article_to_docx`."""
    collection_repository = CollectionRepository(database_path)
    browser_repository = BookBrowserRepository(database_path)

    @mcp.tool()
    def export_answer_to_docx(question: str, answer: str, output_path: str) -> dict:
        """Save a question and its answer (with its own inline citations) as a .docx document."""
        save_answer_docx(question, answer, Path(output_path))
        return {"output_path": output_path}

    @mcp.tool()
    def export_collection_to_docx(collection_id: int, output_path: str) -> dict:
        """Save one saved collection's items - each with its real citation and page content - as a .docx document."""
        collection = next(
            (c for c in collection_repository.list_collections() if c.collection_id == collection_id),
            None,
        )
        if collection is None:
            raise ValueError(f"No collection found with collection_id={collection_id}.")

        book_details_cache: dict[int, tuple[str | None, str | None, tuple] | None] = {}
        export_items: list[CollectionExportItem] = []
        for item in collection_repository.list_items(collection_id):
            if item.book_id not in book_details_cache:
                book_details_cache[item.book_id] = browser_repository.get_book_detail(item.book_id)
            detail = book_details_cache[item.book_id]
            if detail is None:
                continue
            title, author, pages = detail
            page_content = next(
                (page.content_f or "" for page in pages if page.page_number == item.page_number), ""
            )
            metadata = browser_repository.get_book_metadata(item.book_id)
            export_items.append(
                CollectionExportItem(
                    book_title=title or item.book_title,
                    author=author,
                    volume_number=metadata.volume_number if metadata else None,
                    page_number=item.page_number,
                    content=page_content,
                )
            )

        save_collection_docx(collection.name, tuple(export_items), Path(output_path))
        return {"collection_id": collection_id, "output_path": output_path, "item_count": len(export_items)}

    @mcp.tool()
    def export_article_to_docx(
        title: str, sections: list[dict], sources: list[str], output_path: str
    ) -> dict:
        """Save an already-composed article/chapter as a .docx document.

        `sections` is a list of {"heading": str, "body": str}, in order.
        `sources` is a list of already-formatted citation strings (e.g.
        from `get_citation`), appended as a Works Cited list. This tool
        does not research or write the article itself - compose it first
        using `search_text`/`get_citation`, then call this to save it.
        """
        article_sections = tuple(
            ArticleSection(heading=section.get("heading", ""), body=section["body"])
            for section in sections
        )
        save_article_docx(title, article_sections, tuple(sources), Path(output_path))
        return {"title": title, "output_path": output_path, "section_count": len(article_sections)}
