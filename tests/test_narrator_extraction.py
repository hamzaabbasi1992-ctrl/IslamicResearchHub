"""Tests for parsing an LLM's raw narrator-extraction response."""

import json

from islamic_research_hub.application.narrator_extraction import parse_extracted_narrators

_VALID_NARRATOR = {
    "name": "Abu Hurayrah",
    "alternate_names": ["Abd al-Rahman ibn Sakhr"],
    "kunya_nasab": "Abu Hurayrah al-Dawsi",
    "generation": "Companion",
    "hadith_reference": "Hadith 12, Chapter of Faith",
    "quoted_excerpt": "A real verbatim excerpt naming this narrator.",
    "citation": "Book of Hadith, Page 5, Paragraph 1",
}


def test_parses_a_well_formed_json_array() -> None:
    narrators = parse_extracted_narrators(json.dumps([_VALID_NARRATOR]))

    assert len(narrators) == 1
    assert narrators[0].name == "Abu Hurayrah"
    assert narrators[0].alternate_names == ("Abd al-Rahman ibn Sakhr",)
    assert narrators[0].hadith_reference == "Hadith 12, Chapter of Faith"


def test_strips_a_markdown_json_fence_the_model_added_despite_instructions() -> None:
    fenced = f"```json\n{json.dumps([_VALID_NARRATOR])}\n```"

    narrators = parse_extracted_narrators(fenced)

    assert len(narrators) == 1
    assert narrators[0].name == "Abu Hurayrah"


def test_empty_array_returns_no_narrators() -> None:
    assert parse_extracted_narrators("[]") == ()


def test_optional_fields_can_be_null() -> None:
    narrator = {**_VALID_NARRATOR, "kunya_nasab": None, "generation": None}

    narrators = parse_extracted_narrators(json.dumps([narrator]))

    assert narrators[0].kunya_nasab is None
    assert narrators[0].generation is None


def test_missing_required_field_is_skipped_not_fatal() -> None:
    bad_narrator = {**_VALID_NARRATOR}
    del bad_narrator["hadith_reference"]
    good_narrator = _VALID_NARRATOR

    narrators = parse_extracted_narrators(json.dumps([bad_narrator, good_narrator]))

    assert len(narrators) == 1
    assert narrators[0].name == "Abu Hurayrah"


def test_non_json_response_returns_no_narrators_without_crashing() -> None:
    assert parse_extracted_narrators("I couldn't find any narrators.") == ()


def test_json_object_instead_of_array_returns_no_narrators() -> None:
    assert parse_extracted_narrators(json.dumps(_VALID_NARRATOR)) == ()


def test_non_dict_entry_in_array_is_skipped() -> None:
    narrators = parse_extracted_narrators(json.dumps(["not an object", _VALID_NARRATOR]))

    assert len(narrators) == 1


def test_list_field_with_wrong_type_is_skipped() -> None:
    bad_narrator = {**_VALID_NARRATOR, "alternate_names": "not a list"}

    assert parse_extracted_narrators(json.dumps([bad_narrator])) == ()
