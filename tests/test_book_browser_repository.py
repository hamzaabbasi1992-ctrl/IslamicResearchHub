"""Tests for the read-only book browsing/reading repository."""

from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


def _seed_database(database_path: Path) -> None:
    """Import two real books into two different libraries."""
    book_one = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "First page", "Plain"), Page(2, 2, "Second page", "Plain")),
    )
    MasterBookRepository().import_books(
        database_path,
        (book_one,),
        (database_path.parent / "one.mjbz",),
        library_name="Library A",
    )
    book_two = Book(
        information={"Name": "Book of Hadith"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Only page", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path,
        (book_two,),
        (database_path.parent / "two.mjbz",),
        library_name="Library B",
    )


def test_list_libraries_returns_real_names_alphabetically(tmp_path: Path) -> None:
    """Every real library name is returned, sorted.

    `import_books()` always ensures the default legacy library exists as a
    side effect of its NULL-LibraryID backfill, even when nothing is
    imported into it - that shows up here too, sorted alphabetically with
    the two real ones.
    """
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    libraries = BookBrowserRepository(database_path).list_libraries()

    assert libraries == ("Library A", "Library B", "Maktaba Jibreel (Mobile)")


def test_list_libraries_with_counts_returns_real_book_counts(tmp_path: Path) -> None:
    """Each library is paired with its real, current book count."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    counts = BookBrowserRepository(database_path).list_libraries_with_counts()

    assert counts == (
        ("Library A", 1),
        ("Library B", 1),
        ("Maktaba Jibreel (Mobile)", 0),
    )


def test_get_book_source_returns_path_and_library(tmp_path: Path) -> None:
    """The real source path and library name are returned for a known book."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    source = BookBrowserRepository(database_path).get_book_source(1)

    assert source is not None
    assert source[0].endswith("one.mjbz")
    assert source[1] == "Library A"


def test_get_book_source_returns_none_for_unknown_book(tmp_path: Path) -> None:
    """A nonexistent book id returns None instead of raising."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    assert BookBrowserRepository(database_path).get_book_source(9999) is None


def test_get_book_detail_returns_title_author_and_ordered_pages(tmp_path: Path) -> None:
    """Real page content is returned in page order."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    detail = BookBrowserRepository(database_path).get_book_detail(1)

    assert detail is not None
    title, author, pages = detail
    assert title == "Book of Fiqh"
    assert author == "Author One"
    assert [page.content_f for page in pages] == ["First page", "Second page"]


def test_get_book_detail_returns_none_for_unknown_book(tmp_path: Path) -> None:
    """A nonexistent book id returns None instead of raising."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    assert BookBrowserRepository(database_path).get_book_detail(9999) is None
