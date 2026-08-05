"""Tests for the rough extraction cost estimate shown before a paid API call."""

from islamic_research_hub.application.extraction_cost_estimate import estimate_extraction_cost


def test_zero_characters_costs_nothing() -> None:
    assert estimate_extraction_cost(0, chunk_count=1, provider="anthropic") == 0.0


def test_zero_chunks_costs_nothing() -> None:
    assert estimate_extraction_cost(10_000, chunk_count=0, provider="anthropic") == 0.0


def test_cost_scales_up_with_more_characters() -> None:
    small = estimate_extraction_cost(10_000, chunk_count=1, provider="anthropic")
    large = estimate_extraction_cost(100_000, chunk_count=1, provider="anthropic")

    assert large > small


def test_cost_scales_up_with_more_chunks_for_the_same_total_text() -> None:
    """More chunks means more repeated per-call overhead for the same
    underlying text."""
    few_chunks = estimate_extraction_cost(100_000, chunk_count=1, provider="anthropic")
    many_chunks = estimate_extraction_cost(100_000, chunk_count=20, provider="anthropic")

    assert many_chunks > few_chunks


def test_gemini_is_cheaper_than_anthropic_and_openai_for_the_same_input() -> None:
    anthropic_cost = estimate_extraction_cost(100_000, chunk_count=5, provider="anthropic")
    openai_cost = estimate_extraction_cost(100_000, chunk_count=5, provider="openai")
    gemini_cost = estimate_extraction_cost(100_000, chunk_count=5, provider="gemini")

    assert gemini_cost < anthropic_cost
    assert gemini_cost < openai_cost


def test_unknown_provider_falls_back_to_a_conservative_estimate_not_zero() -> None:
    cost = estimate_extraction_cost(100_000, chunk_count=5, provider="some_future_provider")

    assert cost > 0


def test_real_median_book_size_produces_a_sane_estimate() -> None:
    """~108K real characters (this corpus's real median book size,
    measured directly) should land in the tens-of-cents range, not
    dollars or fractions of a cent - a sanity bound, not an exact figure."""
    cost = estimate_extraction_cost(108_000, chunk_count=6, provider="anthropic")

    assert 0.05 < cost < 2.0
