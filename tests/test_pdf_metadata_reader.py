"""Tests for the metadata-only PDF reader."""

from pathlib import Path

from islamic_research_hub.infrastructure.persistence.pdf_metadata_reader import (
    read_pdf_metadata,
)


def test_reads_title_from_filename_with_no_page_content(tmp_path: Path) -> None:
    """A PDF's stem becomes the title; no pages are read."""
    pdf_path = tmp_path / "Some Book Title.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")

    book = read_pdf_metadata(pdf_path)

    assert book.information["Name"] == "Some Book Title"
    assert book.pages == ()
    assert book.categories == ()
    assert book.table_of_contents == ()
