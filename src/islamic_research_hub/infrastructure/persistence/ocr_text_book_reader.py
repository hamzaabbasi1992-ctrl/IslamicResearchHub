"""Reader for real, Google-Vision-OCR'd Urdu book text files.

Each source book was OCR'd externally into one plain .txt file per book
(no PDF text-layer extraction involved - the source PDFs are scanned
images, per the earlier "Generic PDF text extraction" evaluation that
found under 5% of this corpus's PDFs have any real text layer at all).
The OCR pass left one real, distinctive artifact behind: a standalone
line containing just the original scanned page's number, at the point
each new page began. Mirrors `maknoon_text_reader.py`'s page-marker-
splitting shape, with one real difference: Maknoon's own markers use a
distinctive stylised-character wrapper that can never collide with real
body text, but a bare number line here could - a numbered list item
whose OCR line-wrap happened to isolate just the digit is a real risk
in this kind of content (e.g. a home-remedies book: "1.\nTake honey...").
Guarded against by only accepting a marker whose number is strictly
greater than the last accepted one - a genuine page sequence only ever
increases, so a spurious low/repeated number (a running header/footer,
a duplicated OCR marker) is treated as page text instead of splitting
on it. Honest limitation, not silently ignored: a numbered list that
happens to count upward from just after a real page break (e.g. "1. Take
honey" / "2. Add water" immediately after page 40 starts) can still
pass this check and cause a false split, since it's just as
"increasing" as a real next page. Not solvable from the marker pattern
alone; real per-book page counts should be spot-checked against a known
source (the original scan, if available) before treating this as fully
trustworthy. Content before the first accepted marker (front matter/
table of contents) is dropped, same as `maknoon_text_reader.py` - it's
not real page content.

A second, real problem confirmed by actually running this against all
46 real source files before ever touching production data: for roughly
a third of them, the standalone-number-line convention isn't real page
markers at all - it's an isolated footnote/hadith-reference number that
happens to be the only (or one of very few) standalone digit lines in
the whole file, which the monotonic check above happily accepts since
it's the only candidate. The tell is the resulting page's size: a real
single OCR'd page in this corpus's genuinely well-detected books never
averaged above ~18,000 characters; every file where detection was
actually wrong jumped straight to 30,000+, most into the hundreds of
thousands. `_MAX_PLAUSIBLE_AVERAGE_PAGE_CHARACTERS` enforces that real,
measured split - if a file's average accepted-page length exceeds it,
the accepted markers are discarded and the whole file becomes one
honest page instead of a real book split into implausibly-numbered
chunks (e.g. one "page" literally labelled 8210).
"""

import re
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page

TITLE_KEY = "Name"

_PAGE_MARKER = re.compile(r"^\s*(\d{1,4})\.?\s*$", re.MULTILINE)
_TITLE_SEPARATORS = re.compile(r"[_\-]+")
_MAX_PLAUSIBLE_AVERAGE_PAGE_CHARACTERS = 20_000
_MINIMUM_PLAUSIBLE_COVERAGE_RATIO = 0.6
"""A single spurious marker (a footnote/hadith-reference number, not a
real page break) near the end of the file would otherwise pass the
average-page-length check with a small, innocent-looking final "page" -
while silently dropping everything before it (content before the first
accepted marker is never captured in any page, same as
`maknoon_text_reader.py`'s deliberate front-matter drop, but here that
dropped span could be almost the entire real book). Not confirmed to
have actually happened in the real 46-file batch (every real low-
plausibility file found so far also failed the average-length check on
its own), but a real risk the average-length check alone can't catch -
losing that much real content is worse than an implausible page number,
so it's guarded independently rather than assumed away."""


def read_ocr_text_book_file(txt_path: Path) -> Book | None:
    """Build a Book from one real OCR'd text file, or None if it's blank."""
    content = txt_path.read_text(encoding="utf-8", errors="replace")
    if not content.strip():
        return None

    return Book(
        information={TITLE_KEY: _title_from_filename(txt_path)},
        categories=(),
        table_of_contents=(),
        pages=_split_into_pages(content),
    )


def _title_from_filename(txt_path: Path) -> str:
    """Turn a filename like "Kitab_ut_Tib" or "Ainak-Laghana-Choriye" into
    a readable title - no real in-content title exists to parse instead
    (same honest filename-derived convention as `maknoon_text_reader.py`,
    extended with underscore/dash cleanup since these filenames use them
    as word separators, unlike Maknoon's already-clean titles)."""
    return _TITLE_SEPARATORS.sub(" ", txt_path.stem).strip()


def _split_into_pages(content: str) -> tuple[Page, ...]:
    """Split content on real, strictly-increasing page-number marker
    lines. A candidate marker whose number doesn't exceed the last
    accepted one is treated as ordinary page text, not a real page
    boundary - see the module docstring. If the resulting split isn't
    plausible as real per-page content (see
    `_MAX_PLAUSIBLE_AVERAGE_PAGE_CHARACTERS`), the whole file becomes
    one honest page instead."""
    accepted: list[re.Match[str]] = []
    last_page_number = 0
    for match in _PAGE_MARKER.finditer(content):
        page_number = int(match.group(1))
        if page_number > last_page_number:
            accepted.append(match)
            last_page_number = page_number

    fallback = (Page(content_id=1, page_number=1, content_f=content, content_p=None),)
    if not accepted:
        return fallback

    pages: list[Page] = []
    for index, match in enumerate(accepted):
        page_number = int(match.group(1))
        start = match.end()
        end = accepted[index + 1].start() if index + 1 < len(accepted) else len(content)
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
        return fallback
    total_captured = sum(len(page.content_f or "") for page in pages)
    average_page_length = total_captured / len(pages)
    coverage_ratio = total_captured / len(content) if content else 1.0
    if (
        average_page_length > _MAX_PLAUSIBLE_AVERAGE_PAGE_CHARACTERS
        or coverage_ratio < _MINIMUM_PLAUSIBLE_COVERAGE_RATIO
    ):
        return fallback
    return tuple(pages)
