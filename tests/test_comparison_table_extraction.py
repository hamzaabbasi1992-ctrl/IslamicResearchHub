"""Unit tests for comparison_table_extraction.py."""

from islamic_research_hub.application.comparison_table_extraction import (
    ExtractedComparisonTable,
    parse_extracted_comparison_table,
)


def test_parse_valid_comparison_table() -> None:
    raw_json = """{
        "title": "Comparison of Madhhab Positions on Wudu Requirements",
        "rows": [
            {
                "topic": "Touching a member of the opposite sex",
                "positions": [
                    {
                        "scholar_or_school": "Hanafi",
                        "position_summary": "Does not invalidate wudu unless sexual desire is present.",
                        "primary_evidence": "Narrations from Aisha (RA)."
                    },
                    {
                        "scholar_or_school": "Shafi'i",
                        "position_summary": "Invalidates wudu upon skin contact.",
                        "primary_evidence": "Quran 5:6"
                    }
                ]
            }
        ]
    }"""
    result = parse_extracted_comparison_table(raw_json)
    assert isinstance(result, ExtractedComparisonTable)
    assert result.title == "Comparison of Madhhab Positions on Wudu Requirements"
    assert len(result.rows) == 1
    assert len(result.rows[0].positions) == 2
    assert result.rows[0].positions[0].scholar_or_school == "Hanafi"


def test_parse_comparison_table_invalid() -> None:
    assert parse_extracted_comparison_table("Not json") is None
    assert parse_extracted_comparison_table("{}") is None
