"""Unit tests for khutbah_extraction.py."""

from islamic_research_hub.application.khutbah_extraction import (
    ExtractedKhutbahOutline,
    parse_extracted_khutbah,
)


def test_parse_valid_khutbah_json() -> None:
    raw_json = """{
        "topic": "Patience in Times of Trial",
        "sections": [
            {
                "section_type": "Khutbah 1",
                "title": "The Meaning of Sabr",
                "arabic_content": "إن الله مع الصابرين",
                "translation_content": "Indeed Allah is with the patient.",
                "citations": ["Quran 2:153"]
            },
            {
                "section_type": "Sitting",
                "title": "Brief Pause",
                "arabic_content": "استغفروا الله",
                "translation_content": "Seek forgiveness from Allah.",
                "citations": []
            }
        ]
    }"""
    result = parse_extracted_khutbah(raw_json)
    assert isinstance(result, ExtractedKhutbahOutline)
    assert result.topic == "Patience in Times of Trial"
    assert len(result.sections) == 2
    assert result.sections[0].section_type == "Khutbah 1"
    assert result.sections[0].citations == ("Quran 2:153",)


def test_parse_khutbah_with_markdown_fence() -> None:
    raw_json = """```json
    {
        "topic": "Gratitude to Allah",
        "sections": [
            {
                "section_type": "Khutbah 1",
                "title": "Al-Hamd",
                "arabic_content": "الحمد لله رب العالمين",
                "translation_content": "Praise be to Allah, Lord of the worlds.",
                "citations": ["Quran 1:2"]
            }
        ]
    }
    ```"""
    result = parse_extracted_khutbah(raw_json)
    assert result is not None
    assert result.topic == "Gratitude to Allah"
    assert len(result.sections) == 1


def test_parse_invalid_khutbah_returns_none() -> None:
    assert parse_extracted_khutbah("Not valid json") is None
    assert parse_extracted_khutbah("[]") is None
    assert parse_extracted_khutbah("{}") is None
