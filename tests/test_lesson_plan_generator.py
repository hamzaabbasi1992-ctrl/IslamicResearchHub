"""Unit tests for lesson_plan_generator.py."""

from islamic_research_hub.application.lesson_plan_generator import (
    ExtractedLessonPlan,
    parse_extracted_lesson_plan,
)


def test_parse_valid_lesson_plan() -> None:
    raw_json = """{
        "title": "Introduction to Hadith Methodology",
        "duration_minutes": 45,
        "objectives": [
            {
                "objective": "Understand the components of Isnad and Matn.",
                "target_audience": "Beginner Students"
            }
        ],
        "activities": [
            {
                "timing_minutes": 15,
                "activity_title": "Lecture on Hadith Terminology",
                "description": "Covering Sahih, Hasan, and Da'if definitions.",
                "primary_sources": ["Nukhbat al-Fikar"]
            }
        ],
        "assessment_questions": [
            "What is the difference between Sahih and Hasan hadith?"
        ]
    }"""
    result = parse_extracted_lesson_plan(raw_json)
    assert isinstance(result, ExtractedLessonPlan)
    assert result.title == "Introduction to Hadith Methodology"
    assert result.duration_minutes == 45
    assert len(result.objectives) == 1
    assert result.objectives[0].target_audience == "Beginner Students"
    assert len(result.activities) == 1
    assert result.activities[0].primary_sources == ("Nukhbat al-Fikar",)
    assert len(result.assessment_questions) == 1


def test_parse_lesson_plan_invalid() -> None:
    assert parse_extracted_lesson_plan("Not valid json") is None
    assert parse_extracted_lesson_plan("{}") is None
