"""Tests for building domain Books from a Shamela .mdb's raw rows.

Uses hand-built `ShamelaRawBook` fixtures rather than real files - the
real PowerShell/ADODB extraction was verified by hand against real
Shamela files (see CHANGELOG); these tests cover the row-to-domain-model
logic in isolation.
"""

from pathlib import Path

import pytest

from islamic_research_hub.infrastructure.persistence.powershell_shamela_reader import (
    ShamelaRawBook,
)
from islamic_research_hub.infrastructure.persistence.shamela_book_reader import (
    ShamelaBookReadError,
    read_shamela_book,
)
from islamic_research_hub.infrastructure.persistence.shamela_catalog_reader import (
    ShamelaCatalogEntry,
)

_CATALOG_ENTRY = ShamelaCatalogEntry(
    book_name="كتاب الزكاة", author_name="الإمام النووي", author_death=676, category_id=14
)


def _raw_book(book_rows: tuple[dict, ...], title_rows: tuple[dict, ...] = ()) -> ShamelaRawBook:
    return ShamelaRawBook(
        path=Path(r"F:\shamela\Books\0\1.mdb"),
        succeeded=True,
        error=None,
        book_rows=book_rows,
        title_rows=title_rows,
    )


def test_a_single_part_book_produces_one_book_with_the_catalog_title() -> None:
    """A book with only one real part/volume isn't given a volume suffix."""
    raw = _raw_book(
        book_rows=(
            {"id": 1, "nass": "First page", "page": 1, "part": 1, "seal": "AB"},
            {"id": 2, "nass": "Second page", "page": 2, "part": 1, "seal": "CD"},
        )
    )

    books = read_shamela_book(raw, _CATALOG_ENTRY)

    assert len(books) == 1
    assert books[0].information["Name"] == "كتاب الزكاة"
    assert books[0].information["ANAME"] == "الإمام النووي"
    assert books[0].information["Language"] == "Arabic"
    assert [p.content_f for p in books[0].pages] == ["First page", "Second page"]


def test_a_multi_part_book_produces_one_book_per_part_with_volume_suffixes() -> None:
    """A real multi-volume file (page numbers reset per part) splits into
    separate Books, each titled to match the existing volume-title pattern."""
    raw = _raw_book(
        book_rows=(
            {"id": 1, "nass": "Vol 1 page 1", "page": 1, "part": 1},
            {"id": 2, "nass": "Vol 1 page 2", "page": 2, "part": 1},
            {"id": 3, "nass": "Vol 2 page 1", "page": 1, "part": 2},
        )
    )

    books = read_shamela_book(raw, _CATALOG_ENTRY)

    assert len(books) == 2
    assert books[0].information["Name"] == "كتاب الزكاة - part 1"
    assert books[1].information["Name"] == "كتاب الزكاة - part 2"
    assert len(books[0].pages) == 2
    assert len(books[1].pages) == 1


def test_falls_back_to_the_filename_when_no_catalog_entry_exists() -> None:
    """A file with no matching catalog row still imports, titled by filename."""
    raw = _raw_book(book_rows=({"id": 1, "nass": "Content", "page": 1, "part": 1},))

    books = read_shamela_book(raw, catalog_entry=None)

    assert books[0].information["Name"] == "1"
    assert books[0].information["ANAME"] is None


def test_chapter_hierarchy_nests_by_level_not_by_the_unreliable_id_sub_link() -> None:
    """Real Shamela files reuse the same title.id across different lvls
    (confirmed against real data) - hierarchy must come from lvl alone."""
    raw = _raw_book(
        book_rows=(
            {"id": 1, "nass": "p1", "page": 1, "part": 1},
            {"id": 2, "nass": "p2", "page": 2, "part": 1},
            {"id": 3, "nass": "p3", "page": 3, "part": 1},
        ),
        title_rows=(
            {"id": 1, "tit": "Book One", "lvl": 1, "sub": 0},
            {"id": 1, "tit": "Chapter One", "lvl": 2, "sub": 0},  # same id, deeper level
            {"id": 2, "tit": "Section A", "lvl": 3, "sub": 0},
            {"id": 3, "tit": "Book Two", "lvl": 1, "sub": 0},
        ),
    )

    books = read_shamela_book(raw, _CATALOG_ENTRY)

    toc = books[0].table_of_contents
    assert [c.title for c in toc] == ["Book One", "Book Two"]
    assert toc[0].children[0].title == "Chapter One"
    assert toc[0].children[0].children[0].title == "Section A"
    assert toc[0].children[0].page_number == 1  # inherited from title.id=1 -> book.id=1
    assert toc[1].children == ()


def test_hadees_and_ayah_numbers_are_captured_when_present() -> None:
    """hno/Sora/Aya columns (when a file has them) populate real citation fields."""
    raw = _raw_book(
        book_rows=(
            {"id": 1, "nass": "hadith text", "page": 1, "part": 1, "hno": "42", "Sora": 0, "Aya": 0},
            {"id": 2, "nass": "ayah text", "page": 2, "part": 1, "hno": "", "Sora": 2, "Aya": 255},
        )
    )

    books = read_shamela_book(raw, _CATALOG_ENTRY)

    assert books[0].pages[0].hadees_number == "42"
    assert books[0].pages[0].ayah_number is None
    assert books[0].pages[1].hadees_number is None
    assert books[0].pages[1].ayah_number == "2:255"


def test_rows_sharing_a_real_page_number_merge_into_one_page() -> None:
    """Real, non-obvious finding at pilot scale: a book.id row is closer
    to a paragraph than a page - multiple rows commonly share one real
    page number and must merge, not produce duplicate PageNo rows."""
    raw = _raw_book(
        book_rows=(
            {"id": 1, "nass": "First chunk on page 5", "page": 5, "part": 1, "hno": "10"},
            {"id": 2, "nass": "Second chunk on page 5", "page": 5, "part": 1, "hno": "11"},
            {"id": 3, "nass": "Page 6 content", "page": 6, "part": 1},
        )
    )

    books = read_shamela_book(raw, _CATALOG_ENTRY)

    pages = books[0].pages
    assert len(pages) == 2  # not 3 - the two page-5 rows merged
    page_five = next(p for p in pages if p.page_number == 5)
    assert page_five.content_f == "First chunk on page 5\n\nSecond chunk on page 5"
    assert page_five.hadees_number == "10; 11"
    assert page_five.content_id == 1  # the first row's id, deterministically
    page_six = next(p for p in pages if p.page_number == 6)
    assert page_six.content_f == "Page 6 content"


def test_raises_when_the_raw_read_failed() -> None:
    """A file that failed to read (missing/corrupt) is not silently skipped."""
    raw = ShamelaRawBook(
        path=Path(r"F:\shamela\Books\0\missing.mdb"),
        succeeded=False,
        error="Could not find file.",
        book_rows=(),
        title_rows=(),
    )

    with pytest.raises(ShamelaBookReadError):
        read_shamela_book(raw, _CATALOG_ENTRY)


def test_raises_when_a_successfully_opened_file_has_no_real_pages() -> None:
    """An empty book table is a real, honest failure, not a zero-page Book."""
    raw = _raw_book(book_rows=())

    with pytest.raises(ShamelaBookReadError):
        read_shamela_book(raw, _CATALOG_ENTRY)
