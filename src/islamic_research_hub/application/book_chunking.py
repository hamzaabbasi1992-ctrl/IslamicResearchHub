"""Split one book into real page-range chunks for event extraction.

Chapter-sized chunks when a book has real table-of-contents structure
(each capped at `max_chunk_pages`, split further if one chapter runs
longer); fixed-size page-range chunks when it doesn't - an honest
fallback, not a fabricated structure. Either way, no chunk exceeds
`get_book_pages`' own `MAX_PAGES_PER_CALL` cap, so one chunk maps to one
real tool call.
"""

from collections.abc import Iterable

from islamic_research_hub.domain.models.book import Chapter

DEFAULT_MAX_CHUNK_PAGES = 20
"""Matches `agent_tools.MAX_PAGES_PER_CALL` - one chunk, one real
`get_book_pages` call, no pagination needed inside a single chunk."""


def compute_extraction_chunks(
    chapters: tuple[Chapter, ...], page_count: int, max_chunk_pages: int = DEFAULT_MAX_CHUNK_PAGES
) -> tuple[tuple[int, int], ...]:
    """Return real `(start_page, end_page)` chunks covering the whole book.

    `Chapter` has no end-page field - a chapter's real end is the next
    chapter's start minus one, or the book's own `page_count` for the
    last one. Chapters with no real `page_number`, or that collapse onto
    an already-seen start page (a nested chapter's first child starting
    on the same page as its parent - a real, common TOC shape), are
    skipped rather than producing a zero/negative-length range.
    """
    if page_count <= 0:
        return ()
    starts = _real_chapter_starts(chapters)
    if not starts:
        return _fixed_size_chunks(1, page_count, max_chunk_pages)

    chunks: list[tuple[int, int]] = []
    for index, start in enumerate(starts):
        end = (starts[index + 1] - 1) if index + 1 < len(starts) else page_count
        if end < start:
            continue
        chunks.extend(_fixed_size_chunks(start, end, max_chunk_pages))
    return tuple(chunks)


def _real_chapter_starts(chapters: tuple[Chapter, ...]) -> list[int]:
    """Flatten the chapter tree to document order, real start pages only,
    de-duplicated (a nested chapter's TOC entry often shares its parent's
    start page)."""
    starts: list[int] = []
    for page_number in _flatten_page_numbers(chapters):
        if page_number is not None and (not starts or page_number != starts[-1]):
            starts.append(page_number)
    return starts


def _flatten_page_numbers(chapters: Iterable[Chapter]) -> Iterable[int | None]:
    for chapter in chapters:
        yield chapter.page_number
        yield from _flatten_page_numbers(chapter.children)


def _fixed_size_chunks(start: int, end: int, max_chunk_pages: int) -> tuple[tuple[int, int], ...]:
    chunks: list[tuple[int, int]] = []
    current = start
    while current <= end:
        chunk_end = min(current + max_chunk_pages - 1, end)
        chunks.append((current, chunk_end))
        current = chunk_end + 1
    return tuple(chunks)
