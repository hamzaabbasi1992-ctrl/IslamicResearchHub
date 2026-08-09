"""Unit tests for encyclopedia_builder.py."""

from islamic_research_hub.application.encyclopedia_builder import (
    EncyclopediaEntry,
    build_encyclopedia_entry,
)


def test_build_encyclopedia_entry() -> None:
    linked_books = [
        {"BookID": 10, "Title": "Sahih Bukhari", "Author": "Imam Bukhari", "PageNo": 5, "Snippet": "Hadith snippet"},
    ]
    paragraphs = [
        {"BookID": 12, "Title": "Sahih Muslim", "Author": "Imam Muslim", "PageNo": 10, "ParagraphID": "1001", "Snippet": "Paragraph content"},
    ]
    related = ["Hadith Sciences", "Fiqh"]

    entry = build_encyclopedia_entry(
        term_id=1,
        term_name="Hadith",
        dimension="Subject",
        linked_books=linked_books,
        paragraphs=paragraphs,
        related_terms=related,
    )

    assert isinstance(entry, EncyclopediaEntry)
    assert entry.term_name == "Hadith"
    assert entry.total_sources == 2
    assert entry.sources[0].book_title == "Sahih Bukhari"
    assert entry.sources[1].paragraph_id == "P-1001"
    assert entry.related_terms == ("Hadith Sciences", "Fiqh")
