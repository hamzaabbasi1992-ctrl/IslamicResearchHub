"""Parse an LLM's raw JSON response into typed, real study flashcards.

`AiAgentService.generate_flashcards()` returns the model's raw text
response (expected to be a JSON array per its own system prompt) - this
module turns that into typed `ExtractedFlashcard` records, defensively,
mirroring `event_extraction.py`'s exact shape.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_REQUIRED_STRING_FIELDS = ("front", "back", "quoted_excerpt", "citation")


@dataclass(frozen=True, slots=True)
class ExtractedFlashcard:
    """One real study flashcard extracted from real book text, pending
    human review before it's ever trusted."""

    front: str
    back: str
    quoted_excerpt: str
    citation: str


def parse_extracted_flashcards(raw_text: str) -> tuple[ExtractedFlashcard, ...]:
    """Parse the model's response into typed flashcards.

    Strips a ` ```json ... ``` ` fence if present - a real, known LLM
    quirk despite the system prompt explicitly asking for raw JSON only.
    A malformed individual entry is skipped and logged, not fatal to the
    whole response - matches `event_extraction.py`'s partial-failure
    discipline.
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Flashcard generation response was not valid JSON; skipping.")
        return ()
    if not isinstance(parsed, list):
        LOGGER.warning("Flashcard generation response was not a JSON array; skipping.")
        return ()

    flashcards: list[ExtractedFlashcard] = []
    for entry in parsed:
        flashcard = _parse_one_flashcard(entry)
        if flashcard is not None:
            flashcards.append(flashcard)
    return tuple(flashcards)


def _parse_one_flashcard(entry: object) -> ExtractedFlashcard | None:
    if not isinstance(entry, dict):
        LOGGER.warning("Skipping a non-object entry in the extracted flashcards array.")
        return None
    try:
        for field in _REQUIRED_STRING_FIELDS:
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"Missing or blank required field: {field}")
        return ExtractedFlashcard(
            front=entry["front"],
            back=entry["back"],
            quoted_excerpt=entry["quoted_excerpt"],
            citation=entry["citation"],
        )
    except (ValueError, KeyError) as error:
        LOGGER.warning("Skipping a malformed extracted flashcard: %s", error)
        return None
