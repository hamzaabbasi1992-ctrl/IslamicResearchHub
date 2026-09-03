"""End-to-end tests for the mobile catalog export command-line interface."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.interfaces.catalog_export_cli import MOBILE_ROOM_SCHEMA_VERSION, main


def _seed_database(database_path: Path) -> None:
    book_one = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One", "Language": "Arabic"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    book_two = Book(
        information={"Name": "Book of Tafsir", "ANAME": "Author Two", "Language": "Urdu"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None), Page(2, 2, "More content", None)),
    )
    MasterBookRepository().import_books(
        database_path,
        (book_one, book_two),
        (database_path.parent / "a.mjbz", database_path.parent / "b.mjbz"),
    )


def test_exports_a_real_catalog_with_no_page_content(tmp_path: Path, capsys) -> None:
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "catalog.db"
    _seed_database(database_path)

    exit_code = main(
        ["--database", str(database_path), "--output", str(output_path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Books: 2" in captured.out
    assert output_path.is_file()

    with sqlite3.connect(output_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "Pages" not in tables  # deliberately excluded - metadata only
        titles = {
            row[0] for row in connection.execute("SELECT Title FROM Books").fetchall()
        }
        assert titles == {"Book of Fiqh", "Book of Tafsir"}
        library_names = {
            row[0] for row in connection.execute("SELECT Name FROM Libraries").fetchall()
        }
        assert library_names  # at least the default library was copied


def test_book_rows_carry_real_metadata_fields(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "catalog.db"
    _seed_database(database_path)

    main(["--database", str(database_path), "--output", str(output_path)])

    with sqlite3.connect(output_path) as connection:
        row = connection.execute(
            "SELECT Title, Author, Language, PageCount FROM Books WHERE Title = ?",
            ("Book of Tafsir",),
        ).fetchone()
    assert row == ("Book of Tafsir", "Author Two", "Urdu", 2)


def test_fails_cleanly_when_database_is_missing(tmp_path: Path) -> None:
    exit_code = main(
        ["--database", str(tmp_path / "missing.db"), "--output", str(tmp_path / "catalog.db")]
    )

    assert exit_code == 1


def test_creates_the_output_folder_if_it_does_not_exist(tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "exports" / "nested" / "catalog.db"
    _seed_database(database_path)

    exit_code = main(["--database", str(database_path), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.is_file()


def test_re_running_overwrites_the_previous_export(tmp_path: Path) -> None:
    """Real safety guard: a stale catalog file from an earlier export must
    not silently merge with a fresh one."""
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "catalog.db"
    _seed_database(database_path)
    main(["--database", str(database_path), "--output", str(output_path)])

    main(["--database", str(database_path), "--output", str(output_path)])

    with sqlite3.connect(output_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
    assert count == 2  # not 4


def test_output_file_carries_the_room_expected_schema_version(tmp_path: Path) -> None:
    """Real regression guard for the confirmed Room prepackaged-database
    crash (2026-08-12): Android's `SQLiteOpenHelper` treats a copied file
    at `user_version = 0` as uninitialized and tries to CREATE TABLEs
    that already exist. Stamping this must never regress."""
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "catalog.db"
    _seed_database(database_path)

    main(["--database", str(database_path), "--output", str(output_path)])

    with sqlite3.connect(output_path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
    assert version == MOBILE_ROOM_SCHEMA_VERSION


def test_exports_real_named_categories_and_their_book_links(tmp_path: Path) -> None:
    """Books.Category (mostly empty/raw MJCN numbers on the real
    production database) is deliberately not what the mobile Categories
    tab groups by - CategoryTaxonomy's real names, joined to real
    per-book membership, are. The exported Name is the Urdu display
    translation ("فقہ"), not the raw canonical key ("Fiqh") - see
    `_display_category_name()`."""
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "catalog.db"
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One", "Language": "Arabic"},
        categories=(Category(mjcn=42, name="Fiqh", parent_mjcn=None, sort_key=1),),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    main(["--database", str(database_path), "--output", str(output_path)])

    with sqlite3.connect(output_path) as connection:
        category_row = connection.execute(
            "SELECT MJCN, Name, ParentMJCN FROM CategoryNames"
        ).fetchone()
        link_row = connection.execute("SELECT BookID, MJCN FROM BookCategories").fetchone()
    assert category_row == (42, "فقہ", None)
    assert link_row == (1, 42)


def test_excludes_purely_numeric_placeholder_category_names(tmp_path: Path) -> None:
    """A bare MJCN number with no real taxonomy name resolved for it is
    never a legitimate category to show a user - mirrors
    BookBrowserRepository.get_category_tree()'s own real-data guard."""
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "catalog.db"
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(Category(mjcn=99, name="630", parent_mjcn=None, sort_key=1),),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    main(["--database", str(database_path), "--output", str(output_path)])

    with sqlite3.connect(output_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM CategoryNames").fetchone()[0]
    assert count == 0


def test_missing_category_taxonomy_degrades_to_an_empty_categories_export(
    tmp_path: Path,
) -> None:
    """A database that hasn't run migration 3 yet (no CategoryTaxonomy)
    exports cleanly with empty category tables, not an error - same
    honest degradation `_has_series_columns` already models."""
    database_path = tmp_path / "books.db"
    output_path = tmp_path / "catalog.db"
    _seed_database(database_path)  # no migrate() call - CategoryTaxonomy absent

    exit_code = main(["--database", str(database_path), "--output", str(output_path)])

    assert exit_code == 0
    with sqlite3.connect(output_path) as connection:
        count = connection.execute("SELECT COUNT(*) FROM CategoryNames").fetchone()[0]
    assert count == 0
