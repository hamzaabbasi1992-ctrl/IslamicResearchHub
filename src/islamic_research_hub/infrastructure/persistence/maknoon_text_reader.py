"""Reader for Maknoon's pre-extracted PDF text files.

Maknoon ships one .txt file per PDF (already extracted by its own indexer),
named "<original pdf name>.pdf.txt". Many of these are placeholder-only
(the source PDF was a scanned image Maknoon's own indexer could not OCR),
containing nothing but page-number marker lines. This reader treats each
file as a single page and skips files without enough real Arabic/Urdu
text to be useful.
"""

import re
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page

TITLE_KEY = "Name"
SOURCE_SUFFIX = ".pdf.txt"
MINIMUM_ARABIC_CHARACTERS = 200

_ARABIC_RANGE = re.compile(r"[؀-ۿ]")


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
        pages=(Page(content_id=1, page_number=1, content_f=content, content_p=None),),
    )
