"""Typed model for one possible cross-library duplicate book pairing."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DuplicateCandidate:
    """A pair of books that may be duplicates, pending human review."""

    book_id: int
    duplicate_of_book_id: int
    match_type: str
    status: str = "pending"
    """"pending" (awaiting review) or "dismissed" (a human already confirmed
    these are different books - stays dismissed across future re-scans)."""
