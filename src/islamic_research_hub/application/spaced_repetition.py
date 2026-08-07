"""Real spaced-repetition scheduling for confirmed flashcards (Phase 15's
deferred scheduling milestone - Milestone 1 shipped only sequential
flip-through review, explicitly deferring "interval tracking, due
dates" to this real, separate piece).

Implements SuperMemo's SM-2 algorithm - the well-established, real
algorithm Anki's own scheduler descends from - rather than inventing a
new one. A pure function of the current schedule state and one graded
review, with no I/O or timestamps of its own: callers (see
`FlashcardCandidateRepository.record_review`) combine its returned
interval with the real current time to compute a due date, keeping
this module trivially testable.
"""

from dataclasses import dataclass

MINIMUM_EASE_FACTOR = 1.3
"""SM-2's own floor - an ease factor below this makes a card's interval
shrink even on a correct answer, which the original algorithm treats as
a bug, not a real state."""

DEFAULT_EASE_FACTOR = 2.5
"""SM-2's own starting ease factor for a card with no review history yet."""

GRADE_QUALITY: dict[str, int] = {"again": 2, "good": 4, "easy": 5}
"""Maps this app's real 3-button self-assessment onto SM-2's classic
0-5 quality scale - "again" (didn't know it) sits below SM-2's passing
threshold of 3 (resets the card), "good"/"easy" sit at its two real
passing tiers. Three buttons, not SM-2's full six, matches this
project's "ship the narrow real capability first" discipline (same
reasoning as Flashcards/MCQs shipping one real Study/Quiz mode each,
not a full analytics suite)."""


@dataclass(frozen=True, slots=True)
class ReviewState:
    """One flashcard's real SM-2 schedule state, independent of any
    particular clock - `interval_days` is relative to whenever it was
    last reviewed, not an absolute date."""

    ease_factor: float
    interval_days: int
    repetitions: int


FRESH_REVIEW_STATE = ReviewState(
    ease_factor=DEFAULT_EASE_FACTOR, interval_days=0, repetitions=0
)
"""A card with no review history yet - due immediately."""


def schedule_next_review(state: ReviewState, grade: str) -> ReviewState:
    """Return the real next SM-2 state after grading one review.

    Raises `KeyError` for a grade outside `GRADE_QUALITY` - callers are
    expected to only ever offer the three real supported grades in the UI.
    """
    quality = GRADE_QUALITY[grade]
    if quality < 3:
        repetitions = 0
        interval_days = 1
    else:
        if state.repetitions == 0:
            interval_days = 1
        elif state.repetitions == 1:
            interval_days = 6
        else:
            interval_days = round(state.interval_days * state.ease_factor)
        repetitions = state.repetitions + 1
    ease_factor = state.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(ease_factor, MINIMUM_EASE_FACTOR)
    return ReviewState(
        ease_factor=ease_factor, interval_days=interval_days, repetitions=repetitions
    )
