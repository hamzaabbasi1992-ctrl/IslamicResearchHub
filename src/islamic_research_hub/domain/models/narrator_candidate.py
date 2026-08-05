"""Typed model for one extracted (but unverified) narrator mention."""

from dataclasses import dataclass

from islamic_research_hub.application.narrator_extraction import ExtractedNarrator


@dataclass(frozen=True, slots=True)
class NarratorCandidate:
    """One real narrator mention extracted from one book's real text,
    pending human review before it's ever trusted as fact."""

    id: int
    book_id: int
    chunk_start_page: int
    chunk_end_page: int
    narrator: ExtractedNarrator
    status: str = "pending"
    """"pending" (awaiting review), "confirmed" (a human verified this is
    accurate), or "dismissed" (a human rejected it - hallucinated or
    wrong). Same 3-state discipline as EventCandidate: a narrator mention
    asserts a real fact (this name appears at this hadith reference) an
    LLM could hallucinate - it needs an explicit "yes, this is accurate"
    step, not just an absence of dismissal."""
