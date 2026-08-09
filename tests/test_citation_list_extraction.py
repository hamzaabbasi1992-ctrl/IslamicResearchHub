"""Unit tests for citation_list_extraction.py."""

from islamic_research_hub.application.citation_list_extraction import (
    ExtractedCitationEntry,
    parse_extracted_citation_list,
)


def test_parse_valid_citation_list() -> None:
    raw_json = """[
        {
            "source_title": "Sahih al-Bukhari",
            "author": "Imam al-Bukhari",
            "volume_or_page": "Vol 1, p. 45",
            "excerpt": "Actions are by intentions.",
            "relevance": "Primary hadith reference for intentions in worship."
        },
        {
            "source_title": "Al-Mawardi's Ahkam al-Sultaniyya",
            "author": "Al-Mawardi",
            "volume_or_page": "p. 112",
            "excerpt": "Governance principles.",
            "relevance": "Classical administrative framework."
        }
    ]"""
    results = parse_extracted_citation_list(raw_json)
    assert len(results) == 2
    assert isinstance(results[0], ExtractedCitationEntry)
    assert results[0].source_title == "Sahih al-Bukhari"
    assert results[0].author == "Imam al-Bukhari"
    assert results[1].volume_or_page == "p. 112"


def test_parse_citation_list_skips_malformed() -> None:
    raw_json = """[
        {
            "source_title": "Valid Title",
            "author": "Valid Author"
        },
        {
            "missing_title": true
        }
    ]"""
    results = parse_extracted_citation_list(raw_json)
    assert len(results) == 1
    assert results[0].source_title == "Valid Title"


def test_parse_invalid_citation_list() -> None:
    assert parse_extracted_citation_list("Not json") == ()
    assert parse_extracted_citation_list("{}") == ()
