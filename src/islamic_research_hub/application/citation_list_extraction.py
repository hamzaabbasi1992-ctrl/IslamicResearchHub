"""Parse an LLM's raw JSON response into a typed bibliography / citation list.

Turns raw LLM outputs into typed `ExtractedCitationEntry` records, handling
markdown JSON fences and skipping invalid individual entries defensively.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ExtractedCitationEntry:
    """One citation entry in a research bibliography or reference list."""

    source_title: str
    author: str
    volume_or_page: str | None
    excerpt: str
    relevance: str


def parse_extracted_citation_list(raw_text: str) -> tuple[ExtractedCitationEntry, ...]:
    """Parse the model's response into typed citation list entries.

    Strips a ` ```json ... ``` ` fence if present. Returns an empty tuple if JSON
    is invalid or not a list. Skips malformed entries defensively.
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Citation list response was not valid JSON; skipping.")
        return ()

    if not isinstance(parsed, list):
        LOGGER.warning("Citation list response was not a JSON array; skipping.")
        return ()

    entries: list[ExtractedCitationEntry] = []
    for raw_entry in parsed:
        entry = _parse_one_entry(raw_entry)
        if entry is not None:
            entries.append(entry)

    return tuple(entries)


def _parse_one_entry(raw_entry: object) -> ExtractedCitationEntry | None:
    if not isinstance(raw_entry, dict):
        LOGGER.warning("Skipping non-dict citation entry.")
        return None

    title = raw_entry.get("source_title")
    author = raw_entry.get("author")
    vol_page = raw_entry.get("volume_or_page")
    excerpt = raw_entry.get("excerpt", "")
    relevance = raw_entry.get("relevance", "")

    if not isinstance(title, str) or not title.strip():
        LOGGER.warning("Skipping citation entry missing source_title.")
        return None
    if not isinstance(author, str) or not author.strip():
        LOGGER.warning("Skipping citation entry missing author.")
        return None

    return ExtractedCitationEntry(
        source_title=title.strip(),
        author=author.strip(),
        volume_or_page=str(vol_page).strip() if vol_page else None,
        excerpt=str(excerpt).strip() if excerpt else "",
        relevance=str(relevance).strip() if relevance else "",
    )
