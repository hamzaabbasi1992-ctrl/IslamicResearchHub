"""Typed model for one generated (but unverified) study flashcard."""

from dataclasses import dataclass

from islamic_research_hub.application.flashcard_extraction import ExtractedFlashcard


@dataclass(frozen=True, slots=True)
class FlashcardCandidate:
    """One real flashcard generated from one book's real text, pending
    human review before it's ever trusted or studied."""

    id: int
    book_id: int
    chunk_start_page: int
    chunk_end_page: int
    flashcard: ExtractedFlashcard
    status: str = "pending"
    """"pending" (awaiting review), "confirmed" (a human verified this is
    accurate and study-worthy), or "dismissed" (a human rejected it -
    hallucinated, wrong, or not worth studying). Three states, mirroring
    EventCandidate/NarratorCandidate exactly - a generated flashcard
    asserts a real fact an LLM could hallucinate, so it needs an
    explicit "yes, this is accurate" step before Study mode ever shows
    it, not just an absence of dismissal."""
