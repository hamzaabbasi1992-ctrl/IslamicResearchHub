"""Tests for the paragraph citation-string formatter."""

from islamic_research_hub.shared.citation_formatting import format_citation


def test_formats_a_citation_with_a_real_volume_number() -> None:
    """A book that's part of a detected series includes its volume."""
    citation = format_citation("Kashf Al-Bari", page_no=217, paragraph_index=12, volume_number=3)

    assert citation == "Book Kashf Al-Bari, Volume 3, Page 217, Paragraph 12"


def test_formats_a_citation_without_a_volume_when_the_book_is_standalone() -> None:
    """A book with no detected series membership honestly omits Volume,
    rather than fabricating a "Volume 1" for a standalone book."""
    citation = format_citation("Some Standalone Book", page_no=5, paragraph_index=1)

    assert citation == "Book Some Standalone Book, Page 5, Paragraph 1"


def test_volume_number_defaults_to_none() -> None:
    """volume_number is optional and defaults to omitted."""
    citation = format_citation("Book Title", page_no=1, paragraph_index=1)

    assert "Volume" not in citation
