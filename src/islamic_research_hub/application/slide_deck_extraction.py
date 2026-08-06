"""Parse an LLM's raw JSON response into typed slide-deck content.

`AiAgentService.generate_slide_deck()` returns the model's raw text
response (expected to be a JSON array per its own system prompt) - this
module turns that into typed `ExtractedSlide` records, defensively,
since a model's real-world output doesn't always match its instructions
exactly. Mirrors `event_extraction.py`'s parsing discipline exactly.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ExtractedSlide:
    """One real slide's content, generated from real book text."""

    title: str
    bullets: tuple[str, ...]


def parse_extracted_slides(raw_text: str) -> tuple[ExtractedSlide, ...]:
    """Parse the model's response into typed slides.

    Strips a ` ```json ... ``` ` fence if present - a real, known LLM
    quirk despite the system prompt explicitly asking for raw JSON only.
    A malformed individual entry is skipped and logged, not fatal to the
    whole response - matches this project's existing partial-failure
    discipline (`event_extraction.py`, `flashcard_extraction.py`).
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Slide deck response was not valid JSON; skipping.")
        return ()
    if not isinstance(parsed, list):
        LOGGER.warning("Slide deck response was not a JSON array; skipping.")
        return ()

    slides: list[ExtractedSlide] = []
    for entry in parsed:
        slide = _parse_one_slide(entry)
        if slide is not None:
            slides.append(slide)
    return tuple(slides)


def _parse_one_slide(entry: object) -> ExtractedSlide | None:
    if not isinstance(entry, dict):
        LOGGER.warning("Skipping a non-object entry in the slide deck array.")
        return None
    title = entry.get("title")
    bullets = entry.get("bullets")
    if not isinstance(title, str) or not title.strip():
        LOGGER.warning("Skipping a malformed slide: missing or blank title.")
        return None
    if not isinstance(bullets, list) or not all(isinstance(item, str) for item in bullets):
        LOGGER.warning("Skipping a malformed slide: bullets must be a list of strings.")
        return None
    real_bullets = tuple(bullet for bullet in bullets if bullet.strip())
    if not real_bullets:
        LOGGER.warning("Skipping a malformed slide: no real bullet content.")
        return None
    return ExtractedSlide(title=title, bullets=real_bullets)
