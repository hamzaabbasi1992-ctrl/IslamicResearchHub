"""Unit tests for scholarly_review.py (Phase 20)."""

from islamic_research_hub.application.scholarly_review import (
    ScholarlyReviewResult,
    evaluate_scholarly_constraints,
)


def test_evaluate_scholarly_constraints_approved() -> None:
    text = "Imam Bukhari records this in Sahih Bukhari (P-10045)."
    res = evaluate_scholarly_constraints(output_text=text, cited_paragraph_ids=["P-10045"])

    assert isinstance(res, ScholarlyReviewResult)
    assert res.status == "APPROVED"
    assert res.confidence_score >= 0.75
    assert len(res.violations) == 0


def test_evaluate_scholarly_constraints_unsupported_claim() -> None:
    text = "This hadith is Sahih according to all scholars."
    res = evaluate_scholarly_constraints(
        output_text=text,
        requires_hadith_verification=True,
    )

    assert res.status in ("NEEDS_REVIEW", "REJECTED")
    assert len(res.violations) >= 1
    assert "P-XXXXX" in res.missing_citations[0]


def test_evaluate_scholarly_constraints_empty() -> None:
    res = evaluate_scholarly_constraints(output_text="")
    assert res.status == "REJECTED"
    assert res.confidence_score == 0.0
