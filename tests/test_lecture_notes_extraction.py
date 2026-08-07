"""Tests for parsing an LLM's raw lecture-notes-generation response."""

import json

from islamic_research_hub.application.lecture_notes_extraction import (
    parse_extracted_lecture_sections,
)

_VALID_SECTION = {
    "heading": "The Battle of Badr",
    "content": "Fought in 2 AH, this was the first major battle between Mecca and Medina.",
}


def test_parses_a_well_formed_json_array() -> None:
    sections = parse_extracted_lecture_sections(json.dumps([_VALID_SECTION]))

    assert len(sections) == 1
    assert sections[0].heading == "The Battle of Badr"
    assert sections[0].content == _VALID_SECTION["content"]


def test_strips_a_markdown_json_fence_the_model_added_despite_instructions() -> None:
    fenced = f"```json\n{json.dumps([_VALID_SECTION])}\n```"

    sections = parse_extracted_lecture_sections(fenced)

    assert len(sections) == 1
    assert sections[0].heading == "The Battle of Badr"


def test_empty_array_returns_no_sections() -> None:
    assert parse_extracted_lecture_sections("[]") == ()


def test_missing_heading_is_skipped_not_fatal() -> None:
    bad_section = {"content": "Some real content."}

    sections = parse_extracted_lecture_sections(json.dumps([bad_section, _VALID_SECTION]))

    assert len(sections) == 1
    assert sections[0].heading == "The Battle of Badr"


def test_blank_heading_is_skipped() -> None:
    bad_section = {**_VALID_SECTION, "heading": "   "}

    assert parse_extracted_lecture_sections(json.dumps([bad_section])) == ()


def test_missing_content_is_skipped() -> None:
    bad_section = {"heading": "A heading"}

    assert parse_extracted_lecture_sections(json.dumps([bad_section])) == ()


def test_blank_content_is_skipped() -> None:
    bad_section = {**_VALID_SECTION, "content": "   "}

    assert parse_extracted_lecture_sections(json.dumps([bad_section])) == ()


def test_non_string_content_is_skipped() -> None:
    bad_section = {**_VALID_SECTION, "content": 5}

    assert parse_extracted_lecture_sections(json.dumps([bad_section])) == ()


def test_non_json_response_returns_no_sections_without_crashing() -> None:
    assert parse_extracted_lecture_sections("I couldn't find any lecture-worthy content.") == ()


def test_json_object_instead_of_array_returns_no_sections() -> None:
    assert parse_extracted_lecture_sections(json.dumps(_VALID_SECTION)) == ()


def test_non_dict_entry_in_array_is_skipped() -> None:
    sections = parse_extracted_lecture_sections(json.dumps(["not an object", _VALID_SECTION]))

    assert len(sections) == 1
