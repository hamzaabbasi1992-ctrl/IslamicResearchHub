"""MCP tools for research note documents (real .docx files under the
user's Documents folder).

Wraps `LocalDocxStorage` directly rather than `ResearchNotesManager` -
the manager's only extra behavior is remembering a "current document" via
`QSettings`, a desktop-app convenience that doesn't fit a stateless,
multi-call MCP tool (the caller just names the document each time), and
skipping it keeps this server free of a PySide6 dependency.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from islamic_research_hub.research_notes.docx_writer import LocalDocxStorage, NoteFileLockedError
from islamic_research_hub.research_notes.research_notes_manager import Quotation


def register_note_tools(mcp: MCPServer) -> None:
    """Register `create_note_document`, `list_note_documents`, `save_quotation`, `find_notes_mentioning_book`."""
    storage = LocalDocxStorage()

    @mcp.tool()
    def create_note_document(name: str) -> str:
        """Create a new, empty research note document and return its file path."""
        return str(storage.create_document(name))

    @mcp.tool()
    def list_note_documents() -> list[str]:
        """Return every research note document's file path, alphabetically."""
        return [str(path) for path in storage.list_documents()]

    @mcp.tool()
    def save_quotation(
        document_path: str,
        book_title: str,
        selected_text: str,
        author: str | None = None,
        volume: int | None = None,
        chapter: str | None = None,
        page_number: int | None = None,
    ) -> dict:
        """Append one quotation (with its citation details) to an existing note document.

        Appends only - never overwrites what's already in the document.
        """
        quotation = Quotation(
            book_title=book_title,
            author=author,
            volume=volume,
            chapter=chapter,
            page_number=page_number,
            selected_text=selected_text,
        )
        try:
            storage.append_quotation(Path(document_path), quotation)
        except NoteFileLockedError as error:
            raise ValueError(str(error)) from error
        return {"document_path": document_path, "book_title": book_title, "saved": True}

    @mcp.tool()
    def find_notes_mentioning_book(book_title: str) -> list[str]:
        """Return every note document's file path that has at least one quotation saved from this book."""
        return [str(path) for path in storage.find_documents_mentioning(book_title)]
