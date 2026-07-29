"""Tests for the real page-level book comparison repository."""

from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.book_comparison_repository import (
    BookComparisonRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


def _import_book(database_path: Path, title: str, pages: tuple[Page, ...], source: str) -> None:
    book = Book(
        information={"Name": title}, categories=(), table_of_contents=(), pages=pages
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / source,)
    )


def test_identical_pages_have_similarity_close_to_one_and_no_differing_pages(
    tmp_path: Path,
) -> None:
    """Two books with byte-identical page content compare as fully similar."""
    database_path = tmp_path / "books.db"
    _import_book(
        database_path,
        "Book A",
        (Page(1, 1, "The exact same real content", "Plain"),),
        "one.mjbz",
    )
    _import_book(
        database_path,
        "Book B",
        (Page(1, 1, "The exact same real content", "Plain"),),
        "two.mjbz",
    )

    result = BookComparisonRepository(database_path).compare(1, 2)

    assert result.common_page_count == 1
    assert result.overall_similarity == 1.0
    assert result.differing_pages == ()


def test_real_textual_differences_are_reported_with_both_sides(tmp_path: Path) -> None:
    """A page that genuinely differs between editions shows up with both texts."""
    database_path = tmp_path / "books.db"
    _import_book(
        database_path,
        "Book A",
        (Page(1, 1, "The rules of jurisprudence in fiqh are extensive", "Plain"),),
        "one.mjbz",
    )
    _import_book(
        database_path,
        "Book B",
        (Page(1, 1, "A completely different sentence about something else", "Plain"),),
        "two.mjbz",
    )

    result = BookComparisonRepository(database_path).compare(1, 2)

    assert result.common_page_count == 1
    assert len(result.differing_pages) == 1
    entry = result.differing_pages[0]
    assert entry.page_number == 1
    assert entry.similarity < 0.5
    assert entry.content_a == "The rules of jurisprudence in fiqh are extensive"
    assert entry.content_b == "A completely different sentence about something else"


def test_page_counts_reported_even_when_they_differ(tmp_path: Path) -> None:
    """Real page counts are always reported, even for books of different lengths."""
    database_path = tmp_path / "books.db"
    _import_book(
        database_path,
        "Book A",
        (Page(1, 1, "Page one", "Plain"), Page(2, 2, "Page two", "Plain")),
        "one.mjbz",
    )
    _import_book(
        database_path,
        "Book B",
        (Page(1, 1, "Page one", "Plain"),),
        "two.mjbz",
    )

    result = BookComparisonRepository(database_path).compare(1, 2)

    assert result.page_count_a == 2
    assert result.page_count_b == 1
    assert result.common_page_count == 1


def test_no_overlapping_page_numbers_reports_none_not_a_misleading_score(
    tmp_path: Path,
) -> None:
    """When pagination doesn't overlap at all, similarity is honestly None, not 0."""
    database_path = tmp_path / "books.db"
    _import_book(
        database_path, "Book A", (Page(1, 10, "Content at page 10", "Plain"),), "one.mjbz"
    )
    _import_book(
        database_path, "Book B", (Page(1, 20, "Content at page 20", "Plain"),), "two.mjbz"
    )

    result = BookComparisonRepository(database_path).compare(1, 2)

    assert result.common_page_count == 0
    assert result.overall_similarity is None
    assert result.differing_pages == ()


def test_titles_are_included_in_the_result(tmp_path: Path) -> None:
    """Both books' real titles are included, for display without a second lookup."""
    database_path = tmp_path / "books.db"
    _import_book(database_path, "Book Alpha", (Page(1, 1, "x", "Plain"),), "one.mjbz")
    _import_book(database_path, "Book Beta", (Page(1, 1, "x", "Plain"),), "two.mjbz")

    result = BookComparisonRepository(database_path).compare(1, 2)

    assert result.title_a == "Book Alpha"
    assert result.title_b == "Book Beta"


def test_differing_pages_capped_at_max(tmp_path: Path) -> None:
    """A pair with many differing pages is capped, not returned unbounded."""
    database_path = tmp_path / "books.db"
    pages_a = tuple(
        Page(i, i, f"Original content number {i}", "Plain") for i in range(1, 60)
    )
    pages_b = tuple(
        Page(i, i, f"Totally rewritten content number {i} zzz", "Plain")
        for i in range(1, 60)
    )
    _import_book(database_path, "Book A", pages_a, "one.mjbz")
    _import_book(database_path, "Book B", pages_b, "two.mjbz")

    result = BookComparisonRepository(database_path).compare(1, 2)

    assert result.common_page_count == 59
    assert len(result.differing_pages) == 50
