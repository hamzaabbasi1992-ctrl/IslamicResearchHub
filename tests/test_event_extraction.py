"""Tests for parsing an LLM's raw event-extraction response."""

import json

from islamic_research_hub.application.event_extraction import parse_extracted_events

_VALID_EVENT = {
    "title": "Battle of Badr",
    "alternate_names": ["Ghazwa Badr"],
    "subject": "battle",
    "date_hijri": "17 Ramadan, 2 AH",
    "date_gregorian": "624 CE",
    "location": "Badr",
    "background": "Tensions between Mecca and Medina.",
    "summary": "The first major battle.",
    "key_figures": ["Prophet Muhammad"],
    "quoted_excerpt": "A real verbatim excerpt from the source text.",
    "citation": "Book of Seerah, Page 12, Paragraph 1",
}


def test_parses_a_well_formed_json_array() -> None:
    events = parse_extracted_events(json.dumps([_VALID_EVENT]))

    assert len(events) == 1
    assert events[0].title == "Battle of Badr"
    assert events[0].alternate_names == ("Ghazwa Badr",)
    assert events[0].key_figures == ("Prophet Muhammad",)


def test_strips_a_markdown_json_fence_the_model_added_despite_instructions() -> None:
    fenced = f"```json\n{json.dumps([_VALID_EVENT])}\n```"

    events = parse_extracted_events(fenced)

    assert len(events) == 1
    assert events[0].title == "Battle of Badr"


def test_empty_array_returns_no_events() -> None:
    assert parse_extracted_events("[]") == ()


def test_optional_fields_can_be_null() -> None:
    event = {**_VALID_EVENT, "date_hijri": None, "date_gregorian": None, "location": None}

    events = parse_extracted_events(json.dumps([event]))

    assert events[0].date_hijri is None
    assert events[0].location is None


def test_missing_required_field_is_skipped_not_fatal() -> None:
    bad_event = {**_VALID_EVENT}
    del bad_event["summary"]
    good_event = _VALID_EVENT

    events = parse_extracted_events(json.dumps([bad_event, good_event]))

    assert len(events) == 1
    assert events[0].title == "Battle of Badr"


def test_non_json_response_returns_no_events_without_crashing() -> None:
    assert parse_extracted_events("I couldn't find any events.") == ()


def test_json_object_instead_of_array_returns_no_events() -> None:
    assert parse_extracted_events(json.dumps(_VALID_EVENT)) == ()


def test_non_dict_entry_in_array_is_skipped() -> None:
    events = parse_extracted_events(json.dumps(["not an object", _VALID_EVENT]))

    assert len(events) == 1


def test_list_field_with_wrong_type_is_skipped() -> None:
    bad_event = {**_VALID_EVENT, "key_figures": "not a list"}

    assert parse_extracted_events(json.dumps([bad_event])) == ()
