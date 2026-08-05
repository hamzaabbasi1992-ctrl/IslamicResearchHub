"""Typed model for one detected (but unverified) citation between two owned books."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CitationCandidate:
    """A real, literal-phrase match of one book's title inside another
    book's page text - a candidate link pending human review, not an
    asserted fact."""

    citing_book_id: int
    citing_page_no: int
    cited_book_id: int
    matched_title_text: str
    match_type: str
    """"unique_title" (the matched title identifies exactly one book,
    excluding same-series siblings) or "ambiguous_title" (2+ unrelated
    books share the matched title - less certain by construction)."""
    citing_paragraph_id: int | None = None
    """The specific Paragraphs row the phrase was found in, when
    resolvable - None when the phrase spans a paragraph boundary or the
    citing book's Paragraphs were never backfilled; CitingPageNo is
    still a real, useful location either way."""
    status: str = "pending"
    """"pending" (awaiting review) or "dismissed" (a human already
    confirmed this isn't a real citation) - stays dismissed across
    future detect_and_store() rescans."""
