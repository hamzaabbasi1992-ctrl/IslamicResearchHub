"""Typed model for one extracted (but unverified) historical event."""

from dataclasses import dataclass

from islamic_research_hub.application.event_extraction import ExtractedEvent


@dataclass(frozen=True, slots=True)
class EventCandidate:
    """One real event extracted from one book's real text, pending human
    review before it's ever trusted as fact."""

    id: int
    book_id: int
    chunk_start_page: int
    chunk_end_page: int
    event: ExtractedEvent
    status: str = "pending"
    """"pending" (awaiting review), "confirmed" (a human verified this is
    accurate), or "dismissed" (a human rejected it - hallucinated or
    wrong). Three states, not the two used by DuplicateCandidates/
    CitationCandidates: those assert a link between two things this
    library already verifiably holds, while an extracted event asserts
    real historical facts (dates, participants, places) an LLM could
    hallucinate - it needs an explicit "yes, this is accurate" step, not
    just an absence of dismissal."""
