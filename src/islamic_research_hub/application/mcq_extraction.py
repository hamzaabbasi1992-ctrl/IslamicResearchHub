"""Parse an LLM's raw JSON response into typed, real multiple-choice
study questions.

`AiAgentService.generate_mcqs()` returns the model's raw text response
(expected to be a JSON array per its own system prompt) - this module
turns that into typed `ExtractedMcq` records, defensively, mirroring
`event_extraction.py`'s/`flashcard_extraction.py`'s exact shape.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

_REQUIRED_STRING_FIELDS = ("question", "quoted_excerpt", "citation")
_OPTION_COUNT = 4


@dataclass(frozen=True, slots=True)
class ExtractedMcq:
    """One real multiple-choice question extracted from real book text,
    pending human review before it's ever trusted or studied."""

    question: str
    options: tuple[str, str, str, str]
    correct_index: int
    quoted_excerpt: str
    citation: str


def parse_extracted_mcqs(raw_text: str) -> tuple[ExtractedMcq, ...]:
    """Parse the model's response into typed multiple-choice questions.

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
        LOGGER.warning("MCQ generation response was not valid JSON; skipping.")
        return ()
    if not isinstance(parsed, list):
        LOGGER.warning("MCQ generation response was not a JSON array; skipping.")
        return ()

    mcqs: list[ExtractedMcq] = []
    for entry in parsed:
        mcq = _parse_one_mcq(entry)
        if mcq is not None:
            mcqs.append(mcq)
    return tuple(mcqs)


def _parse_one_mcq(entry: object) -> ExtractedMcq | None:
    if not isinstance(entry, dict):
        LOGGER.warning("Skipping a non-object entry in the extracted MCQs array.")
        return None
    try:
        for field in _REQUIRED_STRING_FIELDS:
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                raise ValueError(f"Missing or blank required field: {field}")
        options = entry.get("options")
        if (
            not isinstance(options, list)
            or len(options) != _OPTION_COUNT
            or not all(isinstance(option, str) and option.strip() for option in options)
        ):
            raise ValueError(f"options must be a list of exactly {_OPTION_COUNT} real strings")
        correct_index = entry.get("correct_index")
        if not isinstance(correct_index, int) or not (0 <= correct_index < _OPTION_COUNT):
            raise ValueError(f"correct_index must be an integer in range 0-{_OPTION_COUNT - 1}")
        return ExtractedMcq(
            question=entry["question"],
            options=tuple(options),
            correct_index=correct_index,
            quoted_excerpt=entry["quoted_excerpt"],
            citation=entry["citation"],
        )
    except (ValueError, KeyError) as error:
        LOGGER.warning("Skipping a malformed extracted MCQ: %s", error)
        return None
