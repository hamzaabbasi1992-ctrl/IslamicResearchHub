"""Tests for the read-only book browsing/reading repository."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner


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


def test_get_book_metadata_returns_full_real_details(tmp_path: Path) -> None:
    """Every real catalog field is returned for a known book."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={
            "Name": "Book of Fiqh",
            "ANAME": "Author One",
            "PNAME": "Publisher One",
            "Language": "Urdu",
            "MJCN": "Fiqh",
        },
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",), library_name="Library A"
    )

    metadata = BookBrowserRepository(database_path).get_book_metadata(1)

    assert metadata is not None
    assert metadata.title == "Book of Fiqh"
    assert metadata.author == "Author One"
    assert metadata.publisher == "Publisher One"
    assert metadata.language == "Urdu"
    assert metadata.category == "Fiqh"
    assert metadata.library == "Library A"
    assert metadata.page_count == 1
    # No migration has run on this database - Series support isn't there yet.
    assert metadata.series_title is None
    assert metadata.volume_number is None


def test_get_book_metadata_includes_series_after_migration(tmp_path: Path) -> None:
    """Once migration 4 has run, real series/volume info is included too."""
    database_path = tmp_path / "books.db"
    for volume in (1, 2):
        book = Book(
            information={"Name": f"کفایت المفتی جلد {volume}"},
            categories=(),
            table_of_contents=(),
            pages=(Page(1, 1, "Content", "Plain"),),
        )
        MasterBookRepository().import_books(
            database_path, (book,), (database_path.parent / f"v{volume}.mjbz",)
        )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    metadata = BookBrowserRepository(database_path).get_book_metadata(1)

    assert metadata is not None
    assert metadata.series_title == "کفایت المفتی"
    assert metadata.volume_number == 1


def test_get_book_metadata_returns_none_for_unknown_book(tmp_path: Path) -> None:
    """A nonexistent book id returns None instead of raising."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    assert BookBrowserRepository(database_path).get_book_metadata(9999) is None


def test_get_header_stats_returns_real_counts_pre_migration(tmp_path: Path) -> None:
    """Book/library/author/category counts are real, even with no migration run."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    stats = BookBrowserRepository(database_path).get_header_stats()

    assert stats.book_count == 2
    assert stats.library_count == 3  # Library A, Library B, + the legacy default
    assert stats.author_count == 1  # only book_one has a real author
    assert stats.category_count == 0
    assert stats.series_count == 0  # Series table doesn't exist pre-migration


def test_get_header_stats_counts_authors_and_series_after_migration(tmp_path: Path) -> None:
    """Author/series counts use the normalized tables once migrations have run."""
    database_path = tmp_path / "books.db"
    for volume in (1, 2):
        book = Book(
            information={"Name": f"کفایت المفتی جلد {volume}", "ANAME": "Author One"},
            categories=(),
            table_of_contents=(),
            pages=(Page(1, 1, "Content", "Plain"),),
        )
        MasterBookRepository().import_books(
            database_path, (book,), (database_path.parent / f"v{volume}.mjbz",)
        )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    stats = BookBrowserRepository(database_path).get_header_stats()

    assert stats.book_count == 2
    assert stats.author_count == 1
    assert stats.series_count == 1  # both volumes collapse into one real series


def test_list_authors_with_counts_returns_real_names_and_counts(tmp_path: Path) -> None:
    """Every real author is paired with their real book count, alphabetically."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    authors = BookBrowserRepository(database_path).list_authors_with_counts()

    assert authors == (("Author One", 1),)


def test_get_category_tree_builds_real_hierarchy_with_counts(tmp_path: Path) -> None:
    """Top-level categories carry their real children and real book counts.

    Root categories use MJCN sentinel `0` as ParentMJCN, not NULL - the
    convention already used throughout this corpus's real data.
    """
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(
            Category(mjcn=9, name="Fiqh", parent_mjcn=0, sort_key=1),
            Category(mjcn=90, name="Zakat", parent_mjcn=9, sort_key=1),
        ),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )

    tree = BookBrowserRepository(database_path).get_category_tree()

    assert len(tree) == 1
    assert tree[0].mjcn == 9
    assert tree[0].name == "Fiqh"
    assert tree[0].book_count == 1
    assert len(tree[0].children) == 1
    assert tree[0].children[0].mjcn == 90
    assert tree[0].children[0].book_count == 1


def test_list_books_in_category_returns_real_matching_books(tmp_path: Path) -> None:
    """Only books with a real Categories entry matching this exact name are returned."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(Category(mjcn=9, name="Fiqh", parent_mjcn=0, sort_key=1),),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    other = Book(
        information={"Name": "Book of Hadith"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (other,), (database_path.parent / "two.mjbz",)
    )

    summaries = BookBrowserRepository(database_path).list_books_in_category("Fiqh")

    assert len(summaries) == 1
    assert summaries[0].title == "Book of Fiqh"


def test_list_books_by_author_returns_real_matching_books(tmp_path: Path) -> None:
    """Only books by this exact author are returned."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    summaries = BookBrowserRepository(database_path).list_books_by_author("Author One")

    assert len(summaries) == 1
    assert summaries[0].title == "Book of Fiqh"


def test_list_books_in_library_returns_real_matching_books(tmp_path: Path) -> None:
    """Only books in this exact library are returned."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    summaries = BookBrowserRepository(database_path).list_books_in_library("Library B")

    assert len(summaries) == 1
    assert summaries[0].title == "Book of Hadith"


def test_search_by_title_matches_a_real_substring(tmp_path: Path) -> None:
    """A partial, exact-script title match finds the real book."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    summaries = BookBrowserRepository(database_path).search_by_title("Hadith")

    assert len(summaries) == 1
    assert summaries[0].title == "Book of Hadith"


def test_search_by_title_tolerates_real_letter_form_variants(tmp_path: Path) -> None:
    """A query using one Arabic/Urdu letter-form variant matches a title using another."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "كتاب علی الفقه"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )

    summaries = BookBrowserRepository(database_path).search_by_title("علي")

    assert len(summaries) == 1
    assert summaries[0].title == "كتاب علی الفقه"


def test_search_by_title_returns_nothing_for_an_empty_query(tmp_path: Path) -> None:
    """An empty/whitespace-only query returns no results instead of every book."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    assert BookBrowserRepository(database_path).search_by_title("   ") == ()
