"""Parse an LLM's raw JSON response into typed, real historical events.

`AiAgentService.extract_events()` returns the model's raw text response
(expected to be a JSON array per its own system prompt) - this module
turns that into typed `ExtractedEvent` records, defensively, since a
model's real-world output doesn't always match its instructions exactly.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_REQUIRED_STRING_FIELDS = ("title", "subject", "background", "summary", "quoted_excerpt", "citation")
_OPTIONAL_STRING_FIELDS = ("date_hijri", "date_gregorian", "location")
_LIST_FIELDS = ("alternate_names", "key_figures")


@dataclass(frozen=True, slots=True)
class ExtractedEvent:
    """One real historical event extracted from real book text, pending
    human review before it's ever trusted."""

    title: str
    alternate_names: tuple[str, ...]
    subject: str
    date_hijri: str | None
    date_gregorian: str | None
    location: str | None
    background: str
    summary: str
    key_figures: tuple[str, ...]
    quoted_excerpt: str
    citation: str


def parse_extracted_events(raw_text: str) -> tuple[ExtractedEvent, ...]:
    """Parse the model's response into typed events.

    Strips a ` ```json ... ``` ` fence if present - a real, known LLM
    quirk despite the system prompt explicitly asking for raw JSON only.
    A malformed individual entry is skipped and logged, not fatal to the
    whole response - matches this project's existing partial-failure
    discipline (`TtsWorker`, `CitationCandidateRepository`).
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Event extraction response was not valid JSON; skipping.")
        return ()
    if not isinstance(parsed, list):
        LOGGER.warning("Event extraction response was not a JSON array; skipping.")
        return ()

    events: list[ExtractedEvent] = []
    for entry in parsed:
        event = _parse_one_event(entry)
        if event is not None:
            events.append(event)
    return tuple(events)


def _parse_one_event(entry: object) -> ExtractedEvent | None:
    if not isinstance(entry, dict):
        LOGGER.warning("Skipping a non-object entry in the extracted events array.")
        return None
    try:
        for field in _REQUIRED_STRING_FIELDS:
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"Missing or blank required field: {field}")
        for field in _OPTIONAL_STRING_FIELDS:
            value = entry.get(field)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Field {field} must be a string or null")
        for field in _LIST_FIELDS:
            value = entry.get(field, [])
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"Field {field} must be a list of strings")
        return ExtractedEvent(
            title=entry["title"],
            alternate_names=tuple(entry.get("alternate_names", [])),
            subject=entry["subject"],
            date_hijri=entry.get("date_hijri"),
            date_gregorian=entry.get("date_gregorian"),
            location=entry.get("location"),
            background=entry["background"],
            summary=entry["summary"],
            key_figures=tuple(entry.get("key_figures", [])),
            quoted_excerpt=entry["quoted_excerpt"],
            citation=entry["citation"],
        )
    except (ValueError, KeyError) as error:
        LOGGER.warning("Skipping a malformed extracted event: %s", error)
        return None
