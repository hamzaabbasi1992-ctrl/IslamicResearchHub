"""Tests for parsing an LLM's raw flashcard-generation response."""

import json

from islamic_research_hub.application.flashcard_extraction import parse_extracted_flashcards

_VALID_FLASHCARD = {
    "front": "What is the ruling on zakat for gold below the nisab threshold?",
    "back": "No zakat is due until the nisab threshold is reached.",
    "quoted_excerpt": "A real verbatim excerpt from the source text.",
    "citation": "Book of Fiqh, Page 12, Paragraph 1",
}


def test_parses_a_well_formed_json_array() -> None:
    flashcards = parse_extracted_flashcards(json.dumps([_VALID_FLASHCARD]))

    assert len(flashcards) == 1
    assert flashcards[0].front == _VALID_FLASHCARD["front"]
    assert flashcards[0].back == _VALID_FLASHCARD["back"]


def test_strips_a_markdown_json_fence_the_model_added_despite_instructions() -> None:
    fenced = f"```json\n{json.dumps([_VALID_FLASHCARD])}\n```"

    flashcards = parse_extracted_flashcards(fenced)

    assert len(flashcards) == 1


def test_empty_array_returns_no_flashcards() -> None:
    assert parse_extracted_flashcards("[]") == ()


def test_missing_required_field_is_skipped_not_fatal() -> None:
    bad_flashcard = {**_VALID_FLASHCARD}
    del bad_flashcard["back"]

    flashcards = parse_extracted_flashcards(json.dumps([bad_flashcard, _VALID_FLASHCARD]))

    assert len(flashcards) == 1
    assert flashcards[0].front == _VALID_FLASHCARD["front"]


def test_blank_required_field_is_skipped() -> None:
    bad_flashcard = {**_VALID_FLASHCARD, "back": "   "}

    assert parse_extracted_flashcards(json.dumps([bad_flashcard])) == ()


def test_non_json_response_returns_no_flashcards_without_crashing() -> None:
    assert parse_extracted_flashcards("I couldn't find anything to test.") == ()


def test_json_object_instead_of_array_returns_no_flashcards() -> None:
    assert parse_extracted_flashcards(json.dumps(_VALID_FLASHCARD)) == ()


def test_non_dict_entry_in_array_is_skipped() -> None:
    flashcards = parse_extracted_flashcards(json.dumps(["not an object", _VALID_FLASHCARD]))

    assert len(flashcards) == 1
