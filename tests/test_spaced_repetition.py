"""Tests for the real SM-2 spaced-repetition scheduling algorithm."""

import pytest

from islamic_research_hub.application.spaced_repetition import (
    DEFAULT_EASE_FACTOR,
    FRESH_REVIEW_STATE,
    MINIMUM_EASE_FACTOR,
    ReviewState,
    schedule_next_review,
)


def test_fresh_state_starts_at_the_default_ease_and_zero_interval() -> None:
    assert FRESH_REVIEW_STATE == ReviewState(
        ease_factor=DEFAULT_EASE_FACTOR, interval_days=0, repetitions=0
    )


def test_first_good_review_sets_a_one_day_interval() -> None:
    result = schedule_next_review(FRESH_REVIEW_STATE, "good")

    assert result.interval_days == 1
    assert result.repetitions == 1
    assert result.ease_factor == pytest.approx(2.5)


def test_second_good_review_sets_a_six_day_interval() -> None:
    after_first = schedule_next_review(FRESH_REVIEW_STATE, "good")

    after_second = schedule_next_review(after_first, "good")

    assert after_second.interval_days == 6
    assert after_second.repetitions == 2


def test_third_good_review_multiplies_the_interval_by_ease_factor() -> None:
    state = schedule_next_review(FRESH_REVIEW_STATE, "good")
    state = schedule_next_review(state, "good")

    state = schedule_next_review(state, "good")

    assert state.interval_days == round(6 * 2.5)
    assert state.repetitions == 3


def test_easy_grade_grows_the_ease_factor_more_than_good() -> None:
    good_result = schedule_next_review(FRESH_REVIEW_STATE, "good")
    easy_result = schedule_next_review(FRESH_REVIEW_STATE, "easy")

    assert easy_result.ease_factor > good_result.ease_factor
    assert easy_result.interval_days == 1
    assert easy_result.repetitions == 1


def test_again_grade_resets_repetitions_and_shrinks_the_interval() -> None:
    state = schedule_next_review(FRESH_REVIEW_STATE, "good")
    state = schedule_next_review(state, "good")  # now repetitions=2, interval=6

    result = schedule_next_review(state, "again")

    assert result.repetitions == 0
    assert result.interval_days == 1
    assert result.ease_factor < state.ease_factor


def test_ease_factor_never_drops_below_the_real_sm2_floor() -> None:
    state = FRESH_REVIEW_STATE
    for _ in range(20):
        state = schedule_next_review(state, "again")

    assert state.ease_factor == pytest.approx(MINIMUM_EASE_FACTOR)


def test_an_unsupported_grade_raises() -> None:
    with pytest.raises(KeyError):
        schedule_next_review(FRESH_REVIEW_STATE, "not-a-real-grade")
