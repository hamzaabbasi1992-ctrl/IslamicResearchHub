"""Parse an LLM's raw JSON response into a typed comparison table.

Used for comparative religion and cross-madhhab research analysis - converts
the model's response into typed `ExtractedComparisonTable`, `ExtractedComparisonRow`,
and `ExtractedComparisonPosition` records defensively.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ExtractedComparisonPosition:
    """One scholar or school's position on a specific topic."""

    scholar_or_school: str
    position_summary: str
    primary_evidence: str


@dataclass(frozen=True, slots=True)
class ExtractedComparisonRow:
    """One topic row in a multi-position comparison matrix."""

    topic: str
    positions: tuple[ExtractedComparisonPosition, ...]


@dataclass(frozen=True, slots=True)
class ExtractedComparisonTable:
    """A complete comparative research table."""

    title: str
    rows: tuple[ExtractedComparisonRow, ...]


def parse_extracted_comparison_table(raw_text: str) -> ExtractedComparisonTable | None:
    """Parse the model's response into a typed comparison table.

    Strips markdown JSON fences and handles malformed rows or positions gracefully.
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Comparison table response was not valid JSON; skipping.")
        return None

    if not isinstance(parsed, dict):
        LOGGER.warning("Comparison table response was not a JSON object; skipping.")
        return None

    title = parsed.get("title")
    if not isinstance(title, str) or not title.strip():
        LOGGER.warning("Comparison table missing title.")
        return None

    raw_rows = parsed.get("rows")
    if not isinstance(raw_rows, list):
        LOGGER.warning("Comparison table missing rows array.")
        return None

    rows: list[ExtractedComparisonRow] = []
    for raw_row in raw_rows:
        row = _parse_one_row(raw_row)
        if row is not None:
            rows.append(row)

    return ExtractedComparisonTable(title=title.strip(), rows=tuple(rows))


def _parse_one_row(raw_row: object) -> ExtractedComparisonRow | None:
    if not isinstance(raw_row, dict):
        LOGGER.warning("Skipping non-dict comparison row.")
        return None

    topic = raw_row.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        LOGGER.warning("Skipping comparison row missing topic.")
        return None

    raw_positions = raw_row.get("positions")
    if not isinstance(raw_positions, list):
        LOGGER.warning("Skipping comparison row missing positions array.")
        return None

    positions: list[ExtractedComparisonPosition] = []
    for pos_entry in raw_positions:
        pos = _parse_one_position(pos_entry)
        if pos is not None:
            positions.append(pos)

    return ExtractedComparisonRow(topic=topic.strip(), positions=tuple(positions))


def _parse_one_position(pos_entry: object) -> ExtractedComparisonPosition | None:
    if not isinstance(pos_entry, dict):
        return None

    scholar = pos_entry.get("scholar_or_school")
    summary = pos_entry.get("position_summary")
    evidence = pos_entry.get("primary_evidence", "")

    if not isinstance(scholar, str) or not scholar.strip():
        return None
    if not isinstance(summary, str) or not summary.strip():
        return None

    return ExtractedComparisonPosition(
        scholar_or_school=scholar.strip(),
        position_summary=summary.strip(),
        primary_evidence=str(evidence).strip() if evidence else "",
    )
