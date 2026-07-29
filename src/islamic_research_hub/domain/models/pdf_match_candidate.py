"""Typed model for one possible stub-book-to-PDF title match."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PdfMatchCandidate:
    """A book whose title fuzzy-matched a PDF archive title, pending human review."""

    book_id: int
    pdf_book_id: int
    confidence: float
