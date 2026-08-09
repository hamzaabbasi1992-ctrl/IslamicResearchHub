"""Parse an LLM's raw JSON response into typed book review content.

`AiAgentService` returns the model's raw text response (expected to be a JSON
object containing review components) - this module turns that into typed
`ExtractedBookReview` records defensively.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ExtractedBookReview:
    """A complete structured scholarly book review."""

    title: str
    summary: str
    key_themes: tuple[str, ...]
    methodology_analysis: str
    strengths: tuple[str, ...]
    notable_quotes: tuple[str, ...]


def parse_extracted_book_review(raw_text: str) -> ExtractedBookReview | None:
    """Parse the model's response into a typed book review record.

    Strips a ` ```json ... ``` ` fence if present. Returns None if the response
    is not valid JSON or missing core fields.
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Book review response was not valid JSON; skipping.")
        return None

    if not isinstance(parsed, dict):
        LOGGER.warning("Book review response was not a JSON object; skipping.")
        return None

    title = parsed.get("title")
    summary = parsed.get("summary")
    methodology = parsed.get("methodology_analysis", "")

    if not isinstance(title, str) or not title.strip():
        LOGGER.warning("Book review missing title.")
        return None
    if not isinstance(summary, str) or not summary.strip():
        LOGGER.warning("Book review missing summary.")
        return None

    key_themes = _parse_string_tuple(parsed.get("key_themes"))
    strengths = _parse_string_tuple(parsed.get("strengths"))
    notable_quotes = _parse_string_tuple(parsed.get("notable_quotes"))

    return ExtractedBookReview(
        title=title.strip(),
        summary=summary.strip(),
        key_themes=key_themes,
        methodology_analysis=str(methodology).strip() if methodology else "",
        strengths=strengths,
        notable_quotes=notable_quotes,
    )


def _parse_string_tuple(raw_items: object) -> tuple[str, ...]:
    if not isinstance(raw_items, list):
        return ()
    results: list[str] = []
    for item in raw_items:
        if isinstance(item, str) and item.strip():
            results.append(item.strip())
    return tuple(results)
