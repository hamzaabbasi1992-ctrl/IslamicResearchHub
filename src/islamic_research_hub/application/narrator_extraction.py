"""Parse an LLM's raw JSON response into typed, real narrator mentions.

`AiAgentService.extract_narrators()` returns the model's raw text response
(expected to be a JSON array per its own system prompt) - this module turns
that into typed `ExtractedNarrator` records, defensively, since a model's
real-world output doesn't always match its instructions exactly.

Deliberately structural, not evaluative: a narrator record captures *who
is named where*, never a reliability/authentication judgment - the system
prompt that produces this data explicitly forbids that, and no field here
has room for one either.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_REQUIRED_STRING_FIELDS = ("name", "hadith_reference", "quoted_excerpt", "citation")
_OPTIONAL_STRING_FIELDS = ("kunya_nasab", "generation")
_LIST_FIELDS = ("alternate_names",)


@dataclass(frozen=True, slots=True)
class ExtractedNarrator:
    """One real narrator mention extracted from real book text, pending
    human review before it's ever trusted - structural presence data only
    (who is named where), never an authentication/reliability judgment."""

    name: str
    alternate_names: tuple[str, ...]
    kunya_nasab: str | None
    generation: str | None
    hadith_reference: str
    quoted_excerpt: str
    citation: str


def parse_extracted_narrators(raw_text: str) -> tuple[ExtractedNarrator, ...]:
    """Parse the model's response into typed narrator mentions.

    Strips a ` ```json ... ``` ` fence if present - a real, known LLM
    quirk despite the system prompt explicitly asking for raw JSON only.
    A malformed individual entry is skipped and logged, not fatal to the
    whole response - matches this project's existing partial-failure
    discipline (`TtsWorker`, `CitationCandidateRepository`,
    `event_extraction.py`).
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Narrator extraction response was not valid JSON; skipping.")
        return ()
    if not isinstance(parsed, list):
        LOGGER.warning("Narrator extraction response was not a JSON array; skipping.")
        return ()

    narrators: list[ExtractedNarrator] = []
    for entry in parsed:
        narrator = _parse_one_narrator(entry)
        if narrator is not None:
            narrators.append(narrator)
    return tuple(narrators)


def _parse_one_narrator(entry: object) -> ExtractedNarrator | None:
    if not isinstance(entry, dict):
        LOGGER.warning("Skipping a non-object entry in the extracted narrators array.")
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
        return ExtractedNarrator(
            name=entry["name"],
            alternate_names=tuple(entry.get("alternate_names", [])),
            kunya_nasab=entry.get("kunya_nasab"),
            generation=entry.get("generation"),
            hadith_reference=entry["hadith_reference"],
            quoted_excerpt=entry["quoted_excerpt"],
            citation=entry["citation"],
        )
    except (ValueError, KeyError) as error:
        LOGGER.warning("Skipping a malformed extracted narrator: %s", error)
        return None
