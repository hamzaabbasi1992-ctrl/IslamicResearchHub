"""Auto-assemble structured encyclopedia entry pages from taxonomy and citation data.

Phase 10 feature: bundles taxonomy terms (Subjects, Authors, Eras, Publishers) with
linked books, paragraph citations (`P-XXXXX`), and related concepts into typed
`EncyclopediaEntry` and `LinkedSourceReference` records.
"""

import logging
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LinkedSourceReference:
    """One primary source reference linked to an encyclopedia term."""

    book_id: int
    book_title: str
    author: str
    page_no: int
    paragraph_id: str | None
    snippet: str


@dataclass(frozen=True, slots=True)
class EncyclopediaEntry:
    """A complete auto-assembled encyclopedia page for a taxonomy term or subject."""

    term_id: int
    term_name: str
    dimension: str
    description: str
    total_sources: int
    sources: tuple[LinkedSourceReference, ...]
    related_terms: tuple[str, ...]


def build_encyclopedia_entry(
    term_id: int,
    term_name: str,
    dimension: str = "Subject",
    linked_books: list[dict[str, Any]] | None = None,
    paragraphs: list[dict[str, Any]] | None = None,
    related_terms: list[str] | None = None,
) -> EncyclopediaEntry:
    """Assemble a typed EncyclopediaEntry from linked book records and paragraph citations."""
    sources: list[LinkedSourceReference] = []

    if linked_books:
        for b in linked_books:
            b_id = b.get("book_id") or b.get("BookID") or 0
            title = str(b.get("title") or b.get("Title") or "Untitled")
            author = str(b.get("author") or b.get("Author") or "Unknown Author")
            page_no = b.get("page_no") or b.get("PageNo") or 1
            pid = b.get("paragraph_id") or b.get("ParagraphID")
            snippet = str(b.get("snippet") or b.get("Snippet") or b.get("category") or "")

            sources.append(
                LinkedSourceReference(
                    book_id=int(b_id),
                    book_title=title,
                    author=author,
                    page_no=int(page_no),
                    paragraph_id=str(pid) if pid else None,
                    snippet=snippet,
                )
            )

    if paragraphs:
        for p in paragraphs:
            b_id = p.get("book_id") or p.get("BookID") or 0
            title = str(p.get("book_title") or p.get("Title") or "Untitled")
            author = str(p.get("author") or p.get("Author") or "Unknown Author")
            page_no = p.get("page_no") or p.get("PageNo") or 1
            pid = p.get("paragraph_id") or p.get("ParagraphID")
            text = str(p.get("content") or p.get("Snippet") or "")

            formatted_pid = str(pid) if pid else None
            if formatted_pid and not formatted_pid.startswith("P-"):
                formatted_pid = f"P-{formatted_pid}"

            sources.append(
                LinkedSourceReference(
                    book_id=int(b_id),
                    book_title=title,
                    author=author,
                    page_no=int(page_no),
                    paragraph_id=formatted_pid,
                    snippet=text[:200] if len(text) > 200 else text,
                )
            )

    rel_tuple = tuple(r.strip() for r in related_terms if isinstance(r, str) and r.strip()) if related_terms else ()

    desc = f"Auto-assembled encyclopedia overview for {dimension.lower()} '{term_name}', referencing {len(sources)} primary sources."

    return EncyclopediaEntry(
        term_id=term_id,
        term_name=term_name.strip(),
        dimension=dimension.strip(),
        description=desc,
        total_sources=len(sources),
        sources=tuple(sources),
        related_terms=rel_tuple,
    )
