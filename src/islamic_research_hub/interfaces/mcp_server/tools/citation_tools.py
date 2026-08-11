"""MCP tools for curating already-detected citation candidates.

Thin wrappers over `CitationCandidateRepository`'s read/curate methods
only. Deliberately does NOT expose `detect_and_store()` - that's a
corpus-wide detection rebuild (minutes to hours against the full corpus),
closer to an admin/maintenance operation than a research action, so it's
left as the existing CLI, not something an AI can trigger.
"""

from pathlib import Path

from mcp.server.mcpserver import MCPServer

from islamic_research_hub.infrastructure.persistence.citation_candidate_repository import (
    CitationCandidateRepository,
)


def register_citation_tools(mcp: MCPServer, database_path: Path) -> None:
    """Register `list_citation_candidates`, `count_citation_candidates`, `dismiss_citation_candidate`."""
    repository = CitationCandidateRepository(database_path)

    @mcp.tool()
    def list_citation_candidates(
        include_dismissed: bool = False, limit: int | None = None, offset: int = 0
    ) -> list[dict]:
        """Return already-detected candidate citations between owned books (one book's text naming another book's title)."""
        return [
            {
                "citing_book_id": candidate.citing_book_id,
                "citing_page_no": candidate.citing_page_no,
                "cited_book_id": candidate.cited_book_id,
                "matched_title_text": candidate.matched_title_text,
                "match_type": candidate.match_type,
                "status": candidate.status,
            }
            for candidate in repository.list_candidates(
                include_dismissed=include_dismissed, limit=limit, offset=offset
            )
        ]

    @mcp.tool()
    def count_citation_candidates(include_dismissed: bool = False) -> int:
        """Return the total count of stored citation candidates."""
        return repository.count_candidates(include_dismissed=include_dismissed)

    @mcp.tool()
    def dismiss_citation_candidate(citing_book_id: int, citing_page_no: int, cited_book_id: int) -> dict:
        """Mark one citation candidate as reviewed and not a real citation."""
        repository.dismiss(citing_book_id, citing_page_no, cited_book_id)
        return {
            "citing_book_id": citing_book_id,
            "citing_page_no": citing_page_no,
            "cited_book_id": cited_book_id,
            "status": "dismissed",
        }
