"""Tests for the read-only master database integrity verifier."""

import sqlite3
from pathlib import Path

from islamic_research_hub.domain.models.book import Book, Category, Chapter, Page
from islamic_research_hub.infrastructure.persistence.database_verifier import DatabaseVerifier
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)


def _seed_valid_database(database_path: Path) -> None:
    """Import one well-formed book into a fresh master database."""
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(Category(1, "Root", None, 1),),
        table_of_contents=(Chapter(1, "Chapter", 1, None, 1),),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_healthy_database_reports_no_issues(tmp_path: Path) -> None:
    """A freshly-imported, untouched database reports as healthy."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy
    assert report.error_count == 0
    assert report.issues == ()


def test_detects_orphaned_pages(tmp_path: Path) -> None:
    """A Pages row referencing a nonexistent BookID is flagged as an error."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Pages (BookID, PageNo, Content) VALUES (9999, 1, 'orphaned')"
        )

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(issue.category == "orphaned_rows" for issue in report.issues)


def test_detects_stale_page_count(tmp_path: Path) -> None:
    """A Books.PageCount that disagrees with the real Pages rows is a warning."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Books SET PageCount = 999 WHERE BookID = 1")

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy  # stale counts are a warning, not an error
    assert any(issue.category == "stale_counts" for issue in report.issues)


def test_detects_duplicate_page_numbers(tmp_path: Path) -> None:
    """A repeated (BookID, PageNo) pair is flagged as a warning."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Pages (BookID, PageNo, Content) VALUES (1, 1, 'duplicate page')"
        )

    report = DatabaseVerifier(database_path).verify()

    assert any(issue.category == "duplicate_pages" for issue in report.issues)


def test_detects_orphaned_footnotes(tmp_path: Path) -> None:
    """A Footnotes row referencing a nonexistent BookID is flagged as an error."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Footnotes (BookID, PageNo, FootnoteText) VALUES (9999, 1, 'orphaned')"
        )

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(
        issue.category == "orphaned_rows" and "Footnotes" in issue.message
        for issue in report.issues
    )


def test_orphan_check_skips_a_table_that_does_not_exist_yet(tmp_path: Path) -> None:
    """A database predating a checked table (e.g. an old backup) doesn't crash the verifier."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("DROP TABLE Footnotes")

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy


def test_detects_orphaned_library_reference(tmp_path: Path) -> None:
    """A Books row referencing a nonexistent LibraryID is flagged as an error."""
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Books SET LibraryID = 9999 WHERE BookID = 1")

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(
        issue.category == "orphaned_rows" and "Books" in issue.message
        for issue in report.issues
    )


def _seed_valid_migrated_database(database_path: Path) -> None:
    """Import one well-formed book, then run every migration on top of it."""
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        from islamic_research_hub.infrastructure.persistence.migration_runner import (
            MigrationRunner,
        )

        MigrationRunner().migrate(connection)


def test_healthy_migrated_database_reports_no_issues(tmp_path: Path) -> None:
    """A freshly-migrated database (Paragraphs, all FTS indexes, taxonomy) is healthy too."""
    database_path = tmp_path / "books.db"
    _seed_valid_migrated_database(database_path)

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy
    assert report.issues == ()


def test_detects_orphaned_paragraphs(tmp_path: Path) -> None:
    """A Paragraphs row referencing a nonexistent BookID is flagged as an error."""
    database_path = tmp_path / "books.db"
    _seed_valid_migrated_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Paragraphs (BookID, PageNo, ParagraphIndex, Content) "
            "VALUES (9999, 1, 1, 'orphaned')"
        )

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(
        issue.category == "orphaned_rows" and "Paragraphs" in issue.message
        for issue in report.issues
    )


def test_detects_duplicate_paragraphs(tmp_path: Path) -> None:
    """A repeated (BookID, PageNo, ParagraphIndex) triple is flagged as an
    error - checked directly since it should be structurally impossible
    given the real `Paragraphs` table's own UNIQUE constraint (SQLite
    won't even let a test drop that constraint's backing index to force a
    violation). This test's `Paragraphs` table is hand-crafted without the
    constraint instead, representing a database that predates it, e.g. an
    old backup - the check itself doesn't care why a database lacks the
    constraint, only whether a real duplicate is present.
    """
    database_path = tmp_path / "books.db"
    _seed_valid_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE Paragraphs (BookID INTEGER, PageNo INTEGER, "
            "ParagraphIndex INTEGER, IsHeading INTEGER DEFAULT 0, Content TEXT)"
        )
        connection.executemany(
            "INSERT INTO Paragraphs (BookID, PageNo, ParagraphIndex, Content) VALUES (?, ?, ?, ?)",
            [(1, 1, 1, "first"), (1, 1, 1, "duplicate")],
        )

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(issue.category == "duplicate_paragraphs" for issue in report.issues)


def test_detects_missing_title(tmp_path: Path) -> None:
    """A Books row with a NULL/blank Title is flagged as a warning."""
    database_path = tmp_path / "books.db"
    _seed_valid_migrated_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE Books SET Title = NULL WHERE BookID = 1")

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy  # missing metadata is a warning, not an error
    assert any(issue.category == "missing_metadata" for issue in report.issues)


def test_detects_orphaned_category_taxonomy_parent(tmp_path: Path) -> None:
    """A CategoryTaxonomy row whose ParentMJCN doesn't exist is flagged - but
    the real root sentinel (ParentMJCN = 0) is never flagged."""
    database_path = tmp_path / "books.db"
    _seed_valid_migrated_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO CategoryTaxonomy (MJCN, Name, ParentMJCN) VALUES (777, 'Broken', 9999)"
        )

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(issue.category == "taxonomy_quality" for issue in report.issues)


def test_root_categories_are_not_flagged_as_orphaned(tmp_path: Path) -> None:
    """ParentMJCN = 0 (the real root sentinel) never triggers a false positive."""
    database_path = tmp_path / "books.db"
    _seed_valid_migrated_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO CategoryTaxonomy (MJCN, Name, ParentMJCN) VALUES (778, 'Root Topic', 0)"
        )

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy


def test_fts_sync_check_covers_paragraphs_and_books_indexes_too(tmp_path: Path) -> None:
    """The generalized FTS sync check runs against ParagraphsFTS/BooksFTS, not just PagesFTS."""
    database_path = tmp_path / "books.db"
    _seed_valid_migrated_database(database_path)
    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert "ParagraphsFTS" in tables
    assert "BooksFTS" in tables

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy


def test_detects_reused_taxonomy_stable_key(tmp_path: Path) -> None:
    """Two terms in the same dimension sharing a StableKey is flagged as an
    error - the real bug this guards against once silently collapsed 43
    distinct real subject categories into one term."""
    database_path = tmp_path / "books.db"
    _seed_valid_migrated_database(database_path)
    with sqlite3.connect(database_path) as connection:
        dimension_id = connection.execute(
            "SELECT DimensionID FROM TaxonomyDimensions WHERE Code = 'subject'"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO TaxonomyTerms (DimensionID, StableKey) VALUES (?, 'mjcn:1')",
            (dimension_id,),
        )
        connection.execute(
            "INSERT INTO TaxonomyTerms (DimensionID, StableKey) VALUES (?, 'mjcn:1')",
            (dimension_id,),
        )

    report = DatabaseVerifier(database_path).verify()

    assert not report.is_healthy
    assert any(issue.category == "taxonomy_quality" for issue in report.issues)


def test_taxonomy_stable_keys_across_different_dimensions_are_not_flagged(
    tmp_path: Path,
) -> None:
    """The same StableKey text in two different dimensions is not a collision."""
    database_path = tmp_path / "books.db"
    _seed_valid_migrated_database(database_path)
    with sqlite3.connect(database_path) as connection:
        subject_id, author_id = (
            row[0]
            for row in connection.execute(
                "SELECT DimensionID FROM TaxonomyDimensions "
                "WHERE Code IN ('subject', 'author') ORDER BY Code"
            ).fetchall()
        )
        connection.execute(
            "INSERT INTO TaxonomyTerms (DimensionID, StableKey) VALUES (?, 'shared-key')",
            (subject_id,),
        )
        connection.execute(
            "INSERT INTO TaxonomyTerms (DimensionID, StableKey) VALUES (?, 'shared-key')",
            (author_id,),
        )

    report = DatabaseVerifier(database_path).verify()

    assert report.is_healthy
