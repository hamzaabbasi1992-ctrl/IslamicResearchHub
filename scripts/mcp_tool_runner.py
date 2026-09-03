"""CLI runner for Islamic Research Hub tools (MCP tool interface).

Provides a direct CLI entry point for Antigravity/Gemini to execute any of the
24 research tools without needing a persistent stdio server process.
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is on Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from islamic_research_hub.infrastructure.persistence.book_browser_repository import BookBrowserRepository
from islamic_research_hub.infrastructure.persistence.bookmark_repository import BookmarkRepository
from islamic_research_hub.infrastructure.persistence.citation_candidate_repository import CitationCandidateRepository
from islamic_research_hub.infrastructure.persistence.collection_repository import CollectionRepository
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import SqliteBookSearchRepository
from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.shared.citation_formatting import format_citation
from islamic_research_hub.shared.maktaba_link import build_maktaba_link
from islamic_research_hub.research_notes.docx_writer import LocalDocxStorage
from islamic_research_hub.research_notes.ai_answer_export import export_answer_to_docx
from islamic_research_hub.research_notes.article_export import ArticleSection, export_article_to_docx
from islamic_research_hub.research_notes.collection_export import CollectionExportItem, export_collection_to_docx
from islamic_research_hub.research_notes.research_notes_manager import Quotation

DEFAULT_DB = PROJECT_ROOT / "data" / "books.db"

def main():
    parser = argparse.ArgumentParser(description="Run Islamic Research Hub tools from CLI.")
    parser.add_argument("tool", help="Name of the tool to execute")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="Path to database")
    parser.add_argument("--kwargs", type=str, default="{}", help="JSON string of tool keyword arguments")

    args = parser.parse_args()
    kwargs = json.loads(args.kwargs)
    db_path = args.db if args.db.is_file() else DEFAULT_DB

    result = execute_tool(args.tool, db_path, kwargs)
    print(json.dumps(result, ensure_ascii=False, indent=2))

def execute_tool(tool_name: str, db_path: Path, kwargs: dict):
    if tool_name == "health_check":
        return {"database_path": str(db_path), "reachable": db_path.is_file()}

    elif tool_name == "search_text":
        service = BookSearchService(SqliteBookSearchRepository(db_path))
        results = service.search(
            query=kwargs.get("query", ""),
            limit=kwargs.get("limit", 20),
            library=kwargs.get("library"),
            author=kwargs.get("author"),
            category=kwargs.get("category"),
            exact=kwargs.get("exact", False),
            scope=kwargs.get("scope", "content"),
        )
        return [
            {
                "book_id": r.book_id,
                "title": r.title,
                "author": r.author,
                "page_number": r.page_number,
                "excerpt": r.excerpt,
                "library": r.library,
                "source": r.source,
            }
            for r in results
        ]

    elif tool_name == "get_citation":
        repo = BookBrowserRepository(db_path)
        meta = repo.get_book_metadata(kwargs["book_id"])
        if not meta:
            raise ValueError(f"Book id {kwargs['book_id']} not found")
        return format_citation(meta.title or "(untitled)", kwargs["page_number"], kwargs["paragraph_index"], meta.volume_number)

    elif tool_name == "get_open_link":
        return build_maktaba_link(kwargs["book_id"], kwargs["page_number"])

    elif tool_name == "add_bookmark":
        repo = BookmarkRepository(db_path)
        repo.add_bookmark(kwargs["book_id"], kwargs["page_number"])
        return {"book_id": kwargs["book_id"], "page_number": kwargs["page_number"], "bookmarked": True}

    elif tool_name == "remove_bookmark":
        repo = BookmarkRepository(db_path)
        repo.remove_bookmark(kwargs["book_id"], kwargs["page_number"])
        return {"book_id": kwargs["book_id"], "page_number": kwargs["page_number"], "bookmarked": False}

    elif tool_name == "list_bookmarked_pages":
        repo = BookmarkRepository(db_path)
        return sorted(repo.list_bookmarked_pages(kwargs["book_id"]))

    elif tool_name == "list_recent_bookmarks":
        repo = BookmarkRepository(db_path)
        return [
            {"book_id": b.book_id, "page_number": b.page_number, "title": b.title}
            for b in repo.list_recent_bookmarks(kwargs.get("limit", 5))
        ]

    elif tool_name == "create_collection":
        repo = CollectionRepository(db_path)
        col_id = repo.create_collection(kwargs["name"])
        return {"collection_id": col_id, "name": kwargs["name"]}

    elif tool_name == "list_collections":
        repo = CollectionRepository(db_path)
        return [
            {"collection_id": c.collection_id, "name": c.name, "created_at": c.created_at, "item_count": c.item_count}
            for c in repo.list_collections()
        ]

    elif tool_name == "add_to_collection":
        repo = CollectionRepository(db_path)
        repo.add_item(kwargs["collection_id"], kwargs["book_id"], kwargs["page_number"])
        return {"collection_id": kwargs["collection_id"], "book_id": kwargs["book_id"], "page_number": kwargs["page_number"]}

    elif tool_name == "list_collection_items":
        repo = CollectionRepository(db_path)
        return [
            {"book_id": i.book_id, "page_number": i.page_number, "book_title": i.book_title, "added_at": i.added_at}
            for i in repo.list_items(kwargs["collection_id"])
        ]

    elif tool_name == "create_note_document":
        storage = LocalDocxStorage()
        return str(storage.create_document(kwargs["name"]))

    elif tool_name == "list_note_documents":
        storage = LocalDocxStorage()
        return [str(p) for p in storage.list_documents()]

    elif tool_name == "save_quotation":
        storage = LocalDocxStorage()
        q = Quotation(
            book_title=kwargs["book_title"],
            author=kwargs.get("author"),
            volume=kwargs.get("volume"),
            chapter=kwargs.get("chapter"),
            page_number=kwargs.get("page_number"),
            selected_text=kwargs["selected_text"],
        )
        storage.append_quotation(Path(kwargs["document_path"]), q)
        return {"document_path": kwargs["document_path"], "saved": True}

    elif tool_name == "export_answer_to_docx":
        export_answer_to_docx(kwargs["question"], kwargs["answer"], Path(kwargs["output_path"]))
        return {"output_path": kwargs["output_path"]}

    else:
        raise ValueError(f"Unknown or unsupported tool: {tool_name}")

if __name__ == "__main__":
    main()
