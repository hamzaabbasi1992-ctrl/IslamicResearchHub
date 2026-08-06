"""Tests for parsing an LLM's raw slide-deck-generation response."""

import json

from islamic_research_hub.application.slide_deck_extraction import parse_extracted_slides

_VALID_SLIDE = {
    "title": "The Battle of Badr",
    "bullets": ["Fought in 2 AH.", "The first major battle between Mecca and Medina."],
}


def test_parses_a_well_formed_json_array() -> None:
    slides = parse_extracted_slides(json.dumps([_VALID_SLIDE]))

    assert len(slides) == 1
    assert slides[0].title == "The Battle of Badr"
    assert slides[0].bullets == (
        "Fought in 2 AH.",
        "The first major battle between Mecca and Medina.",
    )


def test_strips_a_markdown_json_fence_the_model_added_despite_instructions() -> None:
    fenced = f"```json\n{json.dumps([_VALID_SLIDE])}\n```"

    slides = parse_extracted_slides(fenced)

    assert len(slides) == 1
    assert slides[0].title == "The Battle of Badr"


def test_empty_array_returns_no_slides() -> None:
    assert parse_extracted_slides("[]") == ()


def test_missing_title_is_skipped_not_fatal() -> None:
    bad_slide = {"bullets": ["A real point."]}

    slides = parse_extracted_slides(json.dumps([bad_slide, _VALID_SLIDE]))

    assert len(slides) == 1
    assert slides[0].title == "The Battle of Badr"


def test_blank_title_is_skipped() -> None:
    bad_slide = {**_VALID_SLIDE, "title": "   "}

    assert parse_extracted_slides(json.dumps([bad_slide])) == ()


def test_bullets_with_wrong_type_is_skipped() -> None:
    bad_slide = {**_VALID_SLIDE, "bullets": "not a list"}

    assert parse_extracted_slides(json.dumps([bad_slide])) == ()


def test_non_string_bullet_item_is_skipped() -> None:
    bad_slide = {**_VALID_SLIDE, "bullets": ["A real point.", 5]}

    assert parse_extracted_slides(json.dumps([bad_slide])) == ()


def test_empty_bullets_list_is_skipped() -> None:
    bad_slide = {**_VALID_SLIDE, "bullets": []}

    assert parse_extracted_slides(json.dumps([bad_slide])) == ()


def test_blank_only_bullets_are_skipped_as_no_real_content() -> None:
    bad_slide = {**_VALID_SLIDE, "bullets": ["   ", ""]}

    assert parse_extracted_slides(json.dumps([bad_slide])) == ()


def test_non_json_response_returns_no_slides_without_crashing() -> None:
    assert parse_extracted_slides("I couldn't find any slide-worthy content.") == ()


def test_json_object_instead_of_array_returns_no_slides() -> None:
    assert parse_extracted_slides(json.dumps(_VALID_SLIDE)) == ()


def test_non_dict_entry_in_array_is_skipped() -> None:
    slides = parse_extracted_slides(json.dumps(["not an object", _VALID_SLIDE]))

    assert len(slides) == 1
