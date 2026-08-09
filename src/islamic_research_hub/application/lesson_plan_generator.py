"""Parse an LLM's raw JSON response into a typed educational lesson plan.

Phase 15 feature: turns raw LLM text outputs into typed `ExtractedLessonPlan`,
`ExtractedLessonObjective`, and `ExtractedLessonActivity` records defensively.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ExtractedLessonObjective:
    """One learning objective for a lesson plan."""

    objective: str
    target_audience: str


@dataclass(frozen=True, slots=True)
class ExtractedLessonActivity:
    """One timed activity in a lesson plan."""

    timing_minutes: int
    activity_title: str
    description: str
    primary_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExtractedLessonPlan:
    """A complete structured educational lesson plan."""

    title: str
    duration_minutes: int
    objectives: tuple[ExtractedLessonObjective, ...]
    activities: tuple[ExtractedLessonActivity, ...]
    assessment_questions: tuple[str, ...]


def parse_extracted_lesson_plan(raw_text: str) -> ExtractedLessonPlan | None:
    """Parse the model's response into a typed lesson plan.

    Strips markdown JSON fences and handles missing or malformed fields defensively.
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Lesson plan response was not valid JSON; skipping.")
        return None

    if not isinstance(parsed, dict):
        LOGGER.warning("Lesson plan response was not a JSON object; skipping.")
        return None

    title = parsed.get("title")
    duration = parsed.get("duration_minutes", 60)

    if not isinstance(title, str) or not title.strip():
        LOGGER.warning("Lesson plan missing valid title.")
        return None

    raw_objectives = parsed.get("objectives", [])
    objectives: list[ExtractedLessonObjective] = []
    if isinstance(raw_objectives, list):
        for entry in raw_objectives:
            obj = _parse_one_objective(entry)
            if obj is not None:
                objectives.append(obj)

    raw_activities = parsed.get("activities", [])
    activities: list[ExtractedLessonActivity] = []
    if isinstance(raw_activities, list):
        for entry in raw_activities:
            act = _parse_one_activity(entry)
            if act is not None:
                activities.append(act)

    raw_assessments = parsed.get("assessment_questions", [])
    assessments: list[str] = []
    if isinstance(raw_assessments, list):
        for item in raw_assessments:
            if isinstance(item, str) and item.strip():
                assessments.append(item.strip())

    return ExtractedLessonPlan(
        title=title.strip(),
        duration_minutes=int(duration) if isinstance(duration, (int, float)) else 60,
        objectives=tuple(objectives),
        activities=tuple(activities),
        assessment_questions=tuple(assessments),
    )


def _parse_one_objective(entry: object) -> ExtractedLessonObjective | None:
    if not isinstance(entry, dict):
        return None

    objective = entry.get("objective")
    audience = entry.get("target_audience", "General Students")

    if not isinstance(objective, str) or not objective.strip():
        return None

    return ExtractedLessonObjective(
        objective=objective.strip(),
        target_audience=str(audience).strip() if audience else "General Students",
    )


def _parse_one_activity(entry: object) -> ExtractedLessonActivity | None:
    if not isinstance(entry, dict):
        return None

    title = entry.get("activity_title")
    timing = entry.get("timing_minutes", 15)
    desc = entry.get("description", "")
    raw_sources = entry.get("primary_sources", [])

    if not isinstance(title, str) or not title.strip():
        return None

    sources: list[str] = []
    if isinstance(raw_sources, list):
        for item in raw_sources:
            if isinstance(item, str) and item.strip():
                sources.append(item.strip())

    return ExtractedLessonActivity(
        timing_minutes=int(timing) if isinstance(timing, (int, float)) else 15,
        activity_title=title.strip(),
        description=str(desc).strip() if desc else "",
        primary_sources=tuple(sources),
    )
