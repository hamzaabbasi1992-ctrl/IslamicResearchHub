"""Unit tests for series_diagnostics.py."""

from islamic_research_hub.application.series_diagnostics import (
    SeriesQualityIssue,
    analyze_series_consistency,
)


def test_analyze_series_consistency() -> None:
    books = [
        {"BookID": 1, "Title": "Tarikh Vol 1", "SeriesID": 10, "VolumeNumber": 1},
        {"BookID": 2, "Title": "Tarikh Vol 3", "SeriesID": 10, "VolumeNumber": 3},  # Missing Vol 2
        {"BookID": 3, "Title": "Tarikh Vol 3 Dup", "SeriesID": 10, "VolumeNumber": 3},  # Dup Vol 3
        {"BookID": 4, "Title": "Orphan Vol", "SeriesID": None, "VolumeNumber": 2},  # Orphan
    ]

    issues = analyze_series_consistency(books)
    assert len(issues) >= 3

    types = [i.issue_type for i in issues]
    assert "MISSING_VOLUME" in types
    assert "DUPLICATE_VOLUME" in types
    assert "ORPHAN_VOLUME" in types


def test_clean_series_no_issues() -> None:
    books = [
        {"BookID": 1, "Title": "Vol 1", "SeriesID": 1, "VolumeNumber": 1},
        {"BookID": 2, "Title": "Vol 2", "SeriesID": 1, "VolumeNumber": 2},
    ]
    issues = analyze_series_consistency(books)
    assert len(issues) == 0
