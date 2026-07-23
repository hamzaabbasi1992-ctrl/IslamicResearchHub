"""Metadata-only reader for PDF collections without pre-extracted text.

Builds a Book record from a PDF's filename alone (title, no page content).
Used for sources where OCR/PDF text extraction is out of scope but the
book's existence, title, and file location are still worth cataloging.
"""

from pathlib import Path

from islamic_research_hub.domain.models.book import Book

TITLE_KEY = "Name"


def read_pdf_metadata(pdf_path: Path) -> Book:
    """Build a metadata-only Book (title only, no pages) from one PDF file."""
    title = pdf_path.stem
    return Book(
        information={TITLE_KEY: title},
        categories=(),
        table_of_contents=(),
        pages=(),
    )
