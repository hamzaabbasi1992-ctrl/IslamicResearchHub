"""Tests for the pure knowledge-gap-detection logic."""

from islamic_research_hub.application.knowledge_gap_analysis import (
    TermCoverage,
    find_low_coverage_terms,
)


def test_filters_out_terms_at_or_above_the_threshold() -> None:
    coverages = (
        TermCoverage(term_id=1, name="Sparse Topic", book_count=1),
        TermCoverage(term_id=2, name="Well Covered Topic", book_count=10),
        TermCoverage(term_id=3, name="Borderline Topic", book_count=3),
    )

    low = find_low_coverage_terms(coverages, threshold=3)

    assert [coverage.term_id for coverage in low] == [1]  # 3 is not < 3, so excluded


def test_excludes_zero_book_terms() -> None:
    """A zero-book term is a different, murkier case (unlinked/import
    artifact) than "the library is genuinely thin on this topic"."""
    coverages = (
        TermCoverage(term_id=1, name="Unlinked Topic", book_count=0),
        TermCoverage(term_id=2, name="Real Gap", book_count=1),
    )

    low = find_low_coverage_terms(coverages, threshold=5)

    assert [coverage.term_id for coverage in low] == [2]


def test_sorts_by_book_count_ascending_then_name() -> None:
    coverages = (
        TermCoverage(term_id=1, name="B Topic", book_count=2),
        TermCoverage(term_id=2, name="A Topic", book_count=2),
        TermCoverage(term_id=3, name="C Topic", book_count=1),
    )

    low = find_low_coverage_terms(coverages, threshold=5)

    assert [coverage.term_id for coverage in low] == [3, 2, 1]


def test_default_threshold_is_three() -> None:
    coverages = (
        TermCoverage(term_id=1, name="Two Books", book_count=2),
        TermCoverage(term_id=2, name="Three Books", book_count=3),
    )

    low = find_low_coverage_terms(coverages)

    assert [coverage.term_id for coverage in low] == [1]


def test_empty_input_returns_empty() -> None:
    assert find_low_coverage_terms(()) == ()
