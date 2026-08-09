"""Detect potential passage-level position variances or contrasting claims.

Phase 10 feature: compares passages by the same author or school to flag potential
textual variances for human research review (objective evidence flagging only;
never renders automated theological or authenticative verdicts).
"""

import difflib
import logging
from dataclasses import dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ContradictionFlag:
    """One flagged passage pair showing potential textual variance or contrasting claims."""

    author_name: str
    passage_a_citation: str
    passage_a_text: str
    passage_b_citation: str
    passage_b_text: str
    similarity_score: float
    variance_note: str


def detect_author_contradiction_candidates(
    author_name: str,
    passages: list[dict[str, Any]],
    similarity_threshold: float = 0.5,
) -> tuple[ContradictionFlag, ...]:
    """Compare passages by an author to detect potential position variances or textual divergence."""
    flags: list[ContradictionFlag] = []
    n = len(passages)

    for i in range(n):
        for j in range(i + 1, n):
            p_a = passages[i]
            p_b = passages[j]

            text_a = str(p_a.get("content") or p_a.get("text") or "").strip()
            text_b = str(p_b.get("content") or p_b.get("text") or "").strip()

            if not text_a or not text_b or text_a == text_b:
                continue

            cit_a = str(p_a.get("citation") or f"Book {p_a.get('book_id', '?')}, Page {p_a.get('page_no', '?')}")
            cit_b = str(p_b.get("citation") or f"Book {p_b.get('book_id', '?')}, Page {p_b.get('page_no', '?')}")

            # Compute sequence matcher similarity
            seq = difflib.SequenceMatcher(None, text_a, text_b)
            ratio = seq.ratio()

            # Flag passages that address similar subjects (moderate similarity) but differ in text
            if similarity_threshold <= ratio < 0.95:
                flags.append(
                    ContradictionFlag(
                        author_name=author_name,
                        passage_a_citation=cit_a,
                        passage_a_text=text_a,
                        passage_b_citation=cit_b,
                        passage_b_text=text_b,
                        similarity_score=round(ratio, 3),
                        variance_note=f"Moderate textual similarity ({round(ratio * 100, 1)}%) with divergent phrasing across works.",
                    )
                )

    return tuple(flags)
