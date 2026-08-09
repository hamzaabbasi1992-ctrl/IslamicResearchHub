"""Parse an LLM's raw JSON response into typed Khutbah outline content.

`AiAgentService` returns the model's raw text response (expected to be a JSON
object containing topic and a list of sections) - this module turns that
into typed `ExtractedKhutbahOutline` and `ExtractedKhutbahSection` records,
defensively, handling markdown fences and malformed structures gracefully.
Mirrors `lecture_notes_extraction.py` and `slide_deck_extraction.py`'s parsing
discipline.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ExtractedKhutbahSection:
    """One section of a Khutbah (e.g. Khutbah 1, Jalsa/Sitting, Khutbah 2, Dua)."""

    section_type: str
    title: str
    arabic_content: str
    translation_content: str
    citations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractedKhutbahOutline:
    """A complete structured Friday Sermon (Khutbah) outline."""

    topic: str
    sections: tuple[ExtractedKhutbahSection, ...]


def parse_extracted_khutbah(raw_text: str) -> ExtractedKhutbahOutline | None:
    """Parse the model's response into a typed Khutbah outline.

    Strips a ` ```json ... ``` ` fence if present. Returns None if the overall
    JSON is invalid or missing required top-level fields. Malformed individual
    sections are skipped and logged.
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Khutbah response was not valid JSON; skipping.")
        return None

    if not isinstance(parsed, dict):
        LOGGER.warning("Khutbah response was not a JSON object; skipping.")
        return None

    topic = parsed.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        LOGGER.warning("Khutbah outline missing valid topic string.")
        return None

    raw_sections = parsed.get("sections")
    if not isinstance(raw_sections, list):
        LOGGER.warning("Khutbah outline missing sections array.")
        return None

    sections: list[ExtractedKhutbahSection] = []
    for entry in raw_sections:
        sec = _parse_one_section(entry)
        if sec is not None:
            sections.append(sec)

    return ExtractedKhutbahOutline(topic=topic.strip(), sections=tuple(sections))


def _parse_one_section(entry: object) -> ExtractedKhutbahSection | None:
    if not isinstance(entry, dict):
        LOGGER.warning("Skipping non-dict Khutbah section entry.")
        return None

    section_type = entry.get("section_type")
    title = entry.get("title")
    arabic_content = entry.get("arabic_content", "")
    translation_content = entry.get("translation_content", "")
    raw_citations = entry.get("citations", [])

    if not isinstance(section_type, str) or not section_type.strip():
        LOGGER.warning("Skipping Khutbah section missing section_type.")
        return None
    if not isinstance(title, str) or not title.strip():
        LOGGER.warning("Skipping Khutbah section missing title.")
        return None

    citations: list[str] = []
    if isinstance(raw_citations, list):
        for item in raw_citations:
            if isinstance(item, str) and item.strip():
                citations.append(item.strip())

    return ExtractedKhutbahSection(
        section_type=section_type.strip(),
        title=title.strip(),
        arabic_content=str(arabic_content).strip() if arabic_content else "",
        translation_content=str(translation_content).strip() if translation_content else "",
        citations=tuple(citations),
    )
