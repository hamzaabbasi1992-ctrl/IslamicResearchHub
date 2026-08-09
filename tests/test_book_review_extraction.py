"""Unit tests for book_review_extraction.py."""

from islamic_research_hub.application.book_review_extraction import (
    ExtractedBookReview,
    parse_extracted_book_review,
)


def test_parse_valid_book_review() -> None:
    raw_json = """{
        "title": "Review of Fath al-Bari",
        "summary": "An exhaustive commentary on Sahih al-Bukhari.",
        "key_themes": ["Hadith Methodology", "Jurisprudence", "Linguistics"],
        "methodology_analysis": "Analytical and comparative approach.",
        "strengths": ["Thorough chain analysis", "Deep linguistic insights"],
        "notable_quotes": ["The most noble commentary."]
    }"""
    result = parse_extracted_book_review(raw_json)
    assert isinstance(result, ExtractedBookReview)
    assert result.title == "Review of Fath al-Bari"
    assert len(result.key_themes) == 3
    assert len(result.strengths) == 2
    assert result.notable_quotes == ("The most noble commentary.",)


def test_parse_book_review_markdown_fence() -> None:
    raw_json = """```json
    {
        "title": "Review of Al-Muqaddimah",
        "summary": "Foundational text on historiography."
    }
    ```"""
    result = parse_extracted_book_review(raw_json)
    assert result is not None
    assert result.title == "Review of Al-Muqaddimah"
    assert result.key_themes == ()


def test_parse_invalid_book_review() -> None:
    assert parse_extracted_book_review("Invalid text") is None
    assert parse_extracted_book_review("[]") is None
