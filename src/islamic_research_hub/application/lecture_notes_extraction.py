"""Parse an LLM's raw JSON response into typed lecture-notes content.

`AiAgentService.generate_lecture_notes()` returns the model's raw text
response (expected to be a JSON array per its own system prompt) - this
module turns that into typed `ExtractedLectureSection` records,
defensively, since a model's real-world output doesn't always match its
instructions exactly. Mirrors `slide_deck_extraction.py`'s parsing
discipline exactly.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ExtractedLectureSection:
    """One real lecture-notes section, generated from real book text."""

    heading: str
    content: str


def parse_extracted_lecture_sections(raw_text: str) -> tuple[ExtractedLectureSection, ...]:
    """Parse the model's response into typed lecture-notes sections.

    Strips a ` ```json ... ``` ` fence if present - a real, known LLM
    quirk despite the system prompt explicitly asking for raw JSON only.
    A malformed individual entry is skipped and logged, not fatal to the
    whole response - matches this project's existing partial-failure
    discipline (`event_extraction.py`, `slide_deck_extraction.py`).
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Lecture notes response was not valid JSON; skipping.")
        return ()
    if not isinstance(parsed, list):
        LOGGER.warning("Lecture notes response was not a JSON array; skipping.")
        return ()

    sections: list[ExtractedLectureSection] = []
    for entry in parsed:
        section = _parse_one_section(entry)
        if section is not None:
            sections.append(section)
    return tuple(sections)


def _parse_one_section(entry: object) -> ExtractedLectureSection | None:
    if not isinstance(entry, dict):
        LOGGER.warning("Skipping a non-object entry in the lecture notes array.")
        return None
    heading = entry.get("heading")
    content = entry.get("content")
    if not isinstance(heading, str) or not heading.strip():
        LOGGER.warning("Skipping a malformed lecture notes section: missing or blank heading.")
        return None
    if not isinstance(content, str) or not content.strip():
        LOGGER.warning("Skipping a malformed lecture notes section: missing or blank content.")
        return None
    return ExtractedLectureSection(heading=heading, content=content)
