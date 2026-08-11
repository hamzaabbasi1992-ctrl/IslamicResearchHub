"""Tests for building/parsing the maktaba:// custom link scheme."""

from islamic_research_hub.shared.maktaba_link import build_maktaba_link, parse_maktaba_link


def test_build_then_parse_round_trips() -> None:
    link = build_maktaba_link(book_id=123, page_number=45)

    assert link == "maktaba://open?book=123&page=45"
    assert parse_maktaba_link(link) == (123, 45)


def test_parse_rejects_a_non_maktaba_scheme() -> None:
    assert parse_maktaba_link("https://open?book=123&page=45") is None


def test_parse_rejects_missing_query_params() -> None:
    assert parse_maktaba_link("maktaba://open?book=123") is None
    assert parse_maktaba_link("maktaba://open") is None


def test_parse_rejects_non_numeric_values() -> None:
    assert parse_maktaba_link("maktaba://open?book=abc&page=45") is None


def test_parse_rejects_garbage_input_without_raising() -> None:
    assert parse_maktaba_link("not a link at all") is None
    assert parse_maktaba_link("") is None
