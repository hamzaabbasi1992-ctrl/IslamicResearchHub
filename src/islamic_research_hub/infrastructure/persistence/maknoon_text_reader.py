"""Reader for Maknoon's pre-extracted PDF text files.

Maknoon ships one .txt file per PDF (already extracted by its own indexer),
named "<original pdf name>.pdf.txt". Many of these are placeholder-only
(the source PDF was a scanned image Maknoon's own indexer could not OCR),
containing nothing but page-number marker lines. This reader filters those
out via an Arabic/Urdu character count threshold, and splits the remaining
files into real per-page content using Maknoon's own page-marker lines
(e.g. "oooooo 42 oooooo", using a stylised o character), so that page
numbers line up with the original PDF's page numbers. Verified against a
200-file random sample: every usable file had detectable markers.
"""

import re
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page

TITLE_KEY = "Name"
SOURCE_SUFFIX = ".pdf.txt"
MINIMUM_ARABIC_CHARACTERS = 200

_ARABIC_RANGE = re.compile(r"[؀-ۿ]")
_PAGE_MARKER = re.compile(r"^ö{3,}\s*(\d+)\s*ö{3,}\s*$", re.MULTILINE)


def read_maknoon_text_file(txt_path: Path) -> Book | None:
    """Build a Book from one Maknoon text file, or None if it has no real content."""
    content = txt_path.read_text(encoding="utf-8", errors="replace")
    if len(_ARABIC_RANGE.findall(content)) < MINIMUM_ARABIC_CHARACTERS:
        return None

    title = txt_path.name
    if title.endswith(SOURCE_SUFFIX):
        title = title[: -len(SOURCE_SUFFIX)]

    return Book(
        information={TITLE_KEY: title},
        categories=(),
        table_of_contents=(),
        pages=_split_into_pages(content),
    )


def _split_into_pages(content: str) -> tuple[Page, ...]:
    """Split content on Maknoon's own page-marker lines into real per-page content."""
    matches = list(_PAGE_MARKER.finditer(content))
    if not matches:
        return (Page(content_id=1, page_number=1, content_f=content, content_p=None),)

    pages: list[Page] = []
    for index, match in enumerate(matches):
        page_number = int(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        page_text = content[start:end].strip()
        if page_text:
            pages.append(
                Page(
                    content_id=index + 1,
                    page_number=page_number,
                    content_f=page_text,
                    content_p=None,
                )
            )

    if not pages:
        return (Page(content_id=1, page_number=1, content_f=content, content_p=None),)
    return tuple(pages)
