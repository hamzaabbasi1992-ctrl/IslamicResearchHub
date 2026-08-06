"""Typed model for one generated (but unverified) multiple-choice study question."""

from dataclasses import dataclass

from islamic_research_hub.application.mcq_extraction import ExtractedMcq


@dataclass(frozen=True, slots=True)
class McqCandidate:
    """One real multiple-choice question generated from one book's real
    text, pending human review before it's ever trusted or studied."""

    id: int
    book_id: int
    chunk_start_page: int
    chunk_end_page: int
    mcq: ExtractedMcq
    status: str = "pending"
    """"pending" (awaiting review), "confirmed" (a human verified this is
    accurate and study-worthy), or "dismissed" (a human rejected it -
    hallucinated, wrong, or not worth studying). Three states, mirroring
    FlashcardCandidate exactly - a generated question asserts a real
    fact an LLM could hallucinate, so it needs an explicit "yes, this is
    accurate" step before Quiz mode ever shows it, not just an absence
    of dismissal."""
