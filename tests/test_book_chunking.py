"""Tests for splitting one book into real page-range extraction chunks."""

from islamic_research_hub.application.book_chunking import compute_extraction_chunks
from islamic_research_hub.domain.models.book import Chapter


def _chapter(title: str, page_number: int | None, children: tuple[Chapter, ...] = ()) -> Chapter:
    return Chapter(
        title_id=None, title=title, page_number=page_number, parent_id=None, sort_key=None,
        children=children,
    )


def test_no_chapters_falls_back_to_fixed_size_chunks() -> None:
    chunks = compute_extraction_chunks((), page_count=45, max_chunk_pages=20)

    assert chunks == ((1, 20), (21, 40), (41, 45))


def test_chapter_based_chunks_use_real_chapter_boundaries() -> None:
    chapters = (
        _chapter("Introduction", 1),
        _chapter("Chapter One", 5),
        _chapter("Chapter Two", 15),
    )

    chunks = compute_extraction_chunks(chapters, page_count=30, max_chunk_pages=20)

    assert chunks == ((1, 4), (5, 14), (15, 30))


def test_a_chapter_longer_than_the_cap_is_split_further() -> None:
    chapters = (_chapter("One Long Chapter", 1),)

    chunks = compute_extraction_chunks(chapters, page_count=50, max_chunk_pages=20)

    assert chunks == ((1, 20), (21, 40), (41, 50))


def test_nested_chapter_sharing_its_parents_start_page_is_deduplicated() -> None:
    """A real, common TOC shape: a chapter's first sub-heading starts on
    the exact same page as the chapter itself - must not produce a
    zero-length range."""
    chapters = (
        _chapter("Part One", 1, children=(_chapter("Part One, Section A", 1),)),
        _chapter("Part Two", 10),
    )

    chunks = compute_extraction_chunks(chapters, page_count=20, max_chunk_pages=20)

    assert chunks == ((1, 9), (10, 20))


def test_chapters_with_no_real_page_number_are_ignored() -> None:
    chapters = (_chapter("Untitled", None), _chapter("Real Chapter", 5))

    chunks = compute_extraction_chunks(chapters, page_count=15, max_chunk_pages=20)

    assert chunks == ((5, 15),)


def test_zero_page_count_returns_no_chunks() -> None:
    assert compute_extraction_chunks((), page_count=0) == ()


def test_default_max_chunk_pages_matches_get_book_pages_cap() -> None:
    from islamic_research_hub.application.agent_tools import MAX_PAGES_PER_CALL
    from islamic_research_hub.application.book_chunking import DEFAULT_MAX_CHUNK_PAGES

    assert DEFAULT_MAX_CHUNK_PAGES == MAX_PAGES_PER_CALL
