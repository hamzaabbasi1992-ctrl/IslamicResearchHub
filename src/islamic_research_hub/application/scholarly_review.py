"""Phase 20: Advanced Scholarly Review & Hard Constraint Validation Framework.

Evaluates AI-generated research outputs (narration chains, literature reviews,
passage analyses) against strict scholarly grounding constraints, citation
requirements, and verification thresholds before release or UI display.
"""

import logging
import re
from dataclasses import dataclass
from typing import Sequence

LOGGER = logging.getLogger(__name__)

PARAGRAPH_CITATION_REGEX = re.compile(r"P-\d{4,8}")


@dataclass(frozen=True, slots=True)
class ScholarlyReviewResult:
    """Standardized validation verdict returned by the scholarly review engine."""

    status: str  # "APPROVED", "NEEDS_REVIEW", "REJECTED"
    confidence_score: float  # 0.0 to 1.0
    missing_citations: tuple[str, ...]
    violations: tuple[str, ...]
    disclaimer: str


def evaluate_scholarly_constraints(
    output_text: str,
    cited_paragraph_ids: Sequence[str] | None = None,
    requires_hadith_verification: bool = False,
    min_confidence_threshold: float = 0.75,
) -> ScholarlyReviewResult:
    """Audit output text against strict scholarly grounding and citation constraints."""
    if not output_text.strip():
        return ScholarlyReviewResult(
            status="REJECTED",
            confidence_score=0.0,
            missing_citations=(),
            violations=("Output text is empty.",),
            disclaimer="Empty content rejected by scholarly review engine.",
        )

    violations: list[str] = []
    missing_citations: list[str] = []

    # Check for paragraph citation grounding in text or parameters
    text_pids = set(PARAGRAPH_CITATION_REGEX.findall(output_text))
    passed_pids = set(cited_paragraph_ids) if cited_paragraph_ids else set()
    total_citations = text_pids.union(passed_pids)

    if not total_citations:
        violations.append("No primary paragraph citations (P-XXXXX) found to support research claims.")
        missing_citations.append("P-XXXXX citation ground required for scholarly assertions.")

    # High-risk Hadith authentication constraints
    confidence = 0.95
    if requires_hadith_verification:
        confidence -= 0.20
        if "authentic" in output_text.lower() or "sahih" in output_text.lower():
            if len(total_citations) < 2:
                violations.append("Hadith authentication claims require at least 2 primary source citations.")

    if violations:
        confidence -= 0.15 * len(violations)

    confidence = max(0.0, min(1.0, confidence))

    if confidence < min_confidence_threshold or len(violations) >= 2:
        status = "REJECTED"
    elif violations:
        status = "NEEDS_REVIEW"
    else:
        status = "APPROVED"

    disclaimer = (
        "Scholarly Review Notice: All AI-generated research outputs must be independently "
        "verified against primary sources by qualified human scholars."
    )

    return ScholarlyReviewResult(
        status=status,
        confidence_score=round(confidence, 2),
        missing_citations=tuple(missing_citations),
        violations=tuple(violations),
        disclaimer=disclaimer,
    )
