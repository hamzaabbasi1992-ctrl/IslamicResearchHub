"""Typed model for one confirmed flashcard's real SM-2 review schedule
(Phase 15's deferred spaced-repetition scheduling milestone)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FlashcardReviewState:
    """One flashcard's real, persisted spaced-repetition schedule -
    absent entirely until its first real review (see
    `FlashcardCandidateRepository.record_review`), at which point it's
    due immediately."""

    flashcard_candidate_id: int
    ease_factor: float
    interval_days: int
    repetitions: int
    due_at: str
    last_reviewed_at: str
