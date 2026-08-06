"""Domain model for Phase 14's other deferred piece: a real, named saved
AI conversation - one question/answer pair from the AI panel, kept for
later reference without needing to ask the same question again."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SavedConversation:
    """One real, named saved AI conversation - the exact question asked
    and the exact answer the AI Agent returned, so reopening it shows
    the real original exchange, not a re-run that could answer
    differently."""

    saved_conversation_id: int
    name: str
    question: str
    answer: str
    created_at: str
