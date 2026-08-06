"""Tests for parsing an LLM's raw MCQ-generation response."""

import json

from islamic_research_hub.application.mcq_extraction import parse_extracted_mcqs

_VALID_MCQ = {
    "question": "What is the ruling on zakat for gold below the nisab threshold?",
    "options": ["It is obligatory", "No zakat is due", "It is recommended", "It is forbidden"],
    "correct_index": 1,
    "quoted_excerpt": "A real verbatim excerpt from the source text.",
    "citation": "Book of Fiqh, Page 12, Paragraph 1",
}


def test_parses_a_well_formed_json_array() -> None:
    mcqs = parse_extracted_mcqs(json.dumps([_VALID_MCQ]))

    assert len(mcqs) == 1
    assert mcqs[0].question == _VALID_MCQ["question"]
    assert mcqs[0].options == tuple(_VALID_MCQ["options"])
    assert mcqs[0].correct_index == 1


def test_strips_a_markdown_json_fence_the_model_added_despite_instructions() -> None:
    fenced = f"```json\n{json.dumps([_VALID_MCQ])}\n```"

    mcqs = parse_extracted_mcqs(fenced)

    assert len(mcqs) == 1


def test_empty_array_returns_no_mcqs() -> None:
    assert parse_extracted_mcqs("[]") == ()


def test_missing_required_field_is_skipped_not_fatal() -> None:
    bad_mcq = {**_VALID_MCQ}
    del bad_mcq["citation"]

    mcqs = parse_extracted_mcqs(json.dumps([bad_mcq, _VALID_MCQ]))

    assert len(mcqs) == 1
    assert mcqs[0].question == _VALID_MCQ["question"]


def test_blank_required_field_is_skipped() -> None:
    bad_mcq = {**_VALID_MCQ, "citation": "   "}

    assert parse_extracted_mcqs(json.dumps([bad_mcq])) == ()


def test_options_with_wrong_count_is_skipped() -> None:
    bad_mcq = {**_VALID_MCQ, "options": ["Only", "Three", "Options"]}

    assert parse_extracted_mcqs(json.dumps([bad_mcq])) == ()


def test_options_with_a_blank_entry_is_skipped() -> None:
    bad_mcq = {**_VALID_MCQ, "options": ["Real", "   ", "Real", "Real"]}

    assert parse_extracted_mcqs(json.dumps([bad_mcq])) == ()


def test_options_with_wrong_type_is_skipped() -> None:
    bad_mcq = {**_VALID_MCQ, "options": "not a list"}

    assert parse_extracted_mcqs(json.dumps([bad_mcq])) == ()


def test_correct_index_out_of_range_is_skipped() -> None:
    bad_mcq = {**_VALID_MCQ, "correct_index": 4}

    assert parse_extracted_mcqs(json.dumps([bad_mcq])) == ()


def test_correct_index_negative_is_skipped() -> None:
    bad_mcq = {**_VALID_MCQ, "correct_index": -1}

    assert parse_extracted_mcqs(json.dumps([bad_mcq])) == ()


def test_correct_index_wrong_type_is_skipped() -> None:
    bad_mcq = {**_VALID_MCQ, "correct_index": "1"}

    assert parse_extracted_mcqs(json.dumps([bad_mcq])) == ()


def test_non_json_response_returns_no_mcqs_without_crashing() -> None:
    assert parse_extracted_mcqs("I couldn't find anything to test.") == ()


def test_json_object_instead_of_array_returns_no_mcqs() -> None:
    assert parse_extracted_mcqs(json.dumps(_VALID_MCQ)) == ()


def test_non_dict_entry_in_array_is_skipped() -> None:
    mcqs = parse_extracted_mcqs(json.dumps(["not an object", _VALID_MCQ]))

    assert len(mcqs) == 1
