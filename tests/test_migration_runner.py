"""Tests for the versioned schema migration runner."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.domain.models.migration import Migration
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (
    AUTHORS_VERSION,
    BASELINE_VERSION,
    BOOKMARKS_AND_RECENT_BOOKS_VERSION,
    CATEGORIES_VERSION,
    MIGRATIONS,
    NORMALIZED_SEARCH_KEYBOARD_FIX_VERSION,
    NORMALIZED_SEARCH_VERSION,
    TAXONOMY_DIMENSIONS,
    TAXONOMY_VERSION,
    VOLUMES_VERSION,
    FOOTNOTES_SEARCH_INDEX_VERSION,
    SOURCE_PDF_HINT_VERSION,
    BOOK_RATINGS_VERSION,
    PARAGRAPHS_VERSION,
    HADEES_AND_AYAH_NUMBERS_VERSION,
    BOOKS_SEARCH_INDEX_VERSION,
    DROP_UNUSED_PARAGRAPHS_SEARCH_INDEX_VERSION,
    WAL_JOURNAL_MODE_VERSION,
    MigrationRunner,
    model_volumes,
)


def test_current_version_defaults_to_zero_on_a_fresh_database() -> None:
    """A brand-new SQLite database has no schema version set."""
    connection = sqlite3.connect(":memory:")

    assert MigrationRunner.current_version(connection) == 0


def test_pending_migrations_returns_migrations_newer_than_current_version() -> None:
    """Only migrations above the database's current version are pending."""
    connection = sqlite3.connect(":memory:")
    applied_marker = []
    migrations = (
        Migration(1, "first", lambda c: applied_marker.append(1)),
        Migration(2, "second", lambda c: applied_marker.append(2)),
    )
    runner = MigrationRunner(migrations)

    pending = runner.pending_migrations(connection)

    assert [migration.version for migration in pending] == [1, 2]


def test_migrate_applies_pending_migrations_in_order_and_bumps_version() -> None:
    """Migrations run in ascending version order and update PRAGMA user_version."""
    connection = sqlite3.connect(":memory:")
    order: list[int] = []
    migrations = (
        Migration(2, "second", lambda c: order.append(2)),
        Migration(1, "first", lambda c: order.append(1)),
    )
    runner = MigrationRunner(migrations)

    applied = runner.migrate(connection)

    assert order == [1, 2]
    assert [migration.version for migration in applied] == [1, 2]
    assert runner.current_version(connection) == 2


def test_migrate_is_idempotent_once_up_to_date() -> None:
    """Running migrate again after everything is applied does nothing."""
    connection = sqlite3.connect(":memory:")
    call_count = []
    migrations = (Migration(1, "first", lambda c: call_count.append(1)),)
    runner = MigrationRunner(migrations)
    runner.migrate(connection)

    second_run_applied = runner.migrate(connection)

    assert second_run_applied == ()
    assert call_count == [1]


def test_migration_apply_function_can_alter_the_schema() -> None:
    """A migration's apply function can run real DDL/DML against the connection."""
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE Widgets (Name TEXT)")

    def _add_column(conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE Widgets ADD COLUMN Color TEXT")

    runner = MigrationRunner((Migration(1, "add color column", _add_column),))

    runner.migrate(connection)

    columns = {row[1] for row in connection.execute("PRAGMA table_info(Widgets)").fetchall()}
    assert "Color" in columns


def test_duplicate_migration_versions_are_rejected() -> None:
    """Constructing a runner with two migrations at the same version raises."""
    migrations = (
        Migration(1, "first", lambda c: None),
        Migration(1, "duplicate", lambda c: None),
    )

    with pytest.raises(ValueError):
        MigrationRunner(migrations)


def test_real_migrations_registry_adopts_a_freshly_imported_database(
    tmp_path: Path,
) -> None:
    """The real MIGRATIONS registry applies cleanly to a just-created database.

    Databases always get their baseline schema from `MasterBookRepository`
    (via an import) before migrations ever run against them - migration 1 is
    a no-op precisely because that schema already exists by then.
    """
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")
    runner = MigrationRunner(MIGRATIONS)

    with sqlite3.connect(database_path) as connection:
        applied = runner.migrate(connection)

        assert [migration.version for migration in applied] == [
            BASELINE_VERSION,
            AUTHORS_VERSION,
            CATEGORIES_VERSION,
            VOLUMES_VERSION,
            NORMALIZED_SEARCH_VERSION,
            TAXONOMY_VERSION,
            NORMALIZED_SEARCH_KEYBOARD_FIX_VERSION,
            BOOKMARKS_AND_RECENT_BOOKS_VERSION,
            WAL_JOURNAL_MODE_VERSION,
            FOOTNOTES_SEARCH_INDEX_VERSION,
            SOURCE_PDF_HINT_VERSION,
            BOOK_RATINGS_VERSION,
            PARAGRAPHS_VERSION,
            HADEES_AND_AYAH_NUMBERS_VERSION,
            BOOKS_SEARCH_INDEX_VERSION,
            DROP_UNUSED_PARAGRAPHS_SEARCH_INDEX_VERSION,
        ]
        assert runner.current_version(connection) == DROP_UNUSED_PARAGRAPHS_SEARCH_INDEX_VERSION


def _seed_book(database_path: Path, title: str, author: str | None, source: str) -> None:
    """Import one minimal real book with the given author into a master database."""
    book = Book(
        information={"Name": title, "ANAME": author},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / source,)
    )


def test_authors_migration_creates_and_backfills_a_normalized_authors_table(
    tmp_path: Path,
) -> None:
    """Migration 2 creates Authors and backfills Books.AuthorID from Books.Author."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", "Imam Al-Ghazali", "one.mjbz")
    _seed_book(database_path, "Book Two", "Imam Al-Ghazali", "two.mjbz")
    _seed_book(database_path, "Book Three", "Ibn Kathir", "three.mjbz")
    _seed_book(database_path, "Book Four", None, "four.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner = MigrationRunner(MIGRATIONS)
        applied = runner.migrate(connection)

        assert [migration.version for migration in applied] == [
            BASELINE_VERSION,
            AUTHORS_VERSION,
            CATEGORIES_VERSION,
            VOLUMES_VERSION,
            NORMALIZED_SEARCH_VERSION,
            TAXONOMY_VERSION,
            NORMALIZED_SEARCH_KEYBOARD_FIX_VERSION,
            BOOKMARKS_AND_RECENT_BOOKS_VERSION,
            WAL_JOURNAL_MODE_VERSION,
            FOOTNOTES_SEARCH_INDEX_VERSION,
            SOURCE_PDF_HINT_VERSION,
            BOOK_RATINGS_VERSION,
            PARAGRAPHS_VERSION,
            HADEES_AND_AYAH_NUMBERS_VERSION,
            BOOKS_SEARCH_INDEX_VERSION,
            DROP_UNUSED_PARAGRAPHS_SEARCH_INDEX_VERSION,
        ]

        authors = dict(connection.execute("SELECT Name, AuthorID FROM Authors").fetchall())
        assert set(authors) == {"Imam Al-Ghazali", "Ibn Kathir"}

        rows = connection.execute(
            "SELECT Title, Author, AuthorID FROM Books ORDER BY Title"
        ).fetchall()
        by_title = {title: (author, author_id) for title, author, author_id in rows}
        assert by_title["Book One"] == ("Imam Al-Ghazali", authors["Imam Al-Ghazali"])
        assert by_title["Book Two"] == ("Imam Al-Ghazali", authors["Imam Al-Ghazali"])
        assert by_title["Book Three"] == ("Ibn Kathir", authors["Ibn Kathir"])
        assert by_title["Book Four"] == (None, None)


def _seed_book_with_categories(
    database_path: Path, title: str, categories: tuple[Category, ...], source: str
) -> None:
    """Import one minimal real book carrying the given category hierarchy."""
    book = Book(
        information={"Name": title},
        categories=categories,
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / source,)
    )


def test_categories_migration_deduplicates_by_mjcn_across_books(tmp_path: Path) -> None:
    """Migration 3 builds one taxonomy row per distinct MJCN across all books."""
    database_path = tmp_path / "books.db"
    fiqh = Category(mjcn=9, name="Fiqh", parent_mjcn=0, sort_key=1)
    hadith = Category(mjcn=10, name="Hadith", parent_mjcn=0, sort_key=2)
    _seed_book_with_categories(database_path, "Book One", (fiqh,), "one.mjbz")
    _seed_book_with_categories(database_path, "Book Two", (fiqh, hadith), "two.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner = MigrationRunner(MIGRATIONS)
        applied = runner.migrate(connection)

        assert [migration.version for migration in applied] == [
            BASELINE_VERSION,
            AUTHORS_VERSION,
            CATEGORIES_VERSION,
            VOLUMES_VERSION,
            NORMALIZED_SEARCH_VERSION,
            TAXONOMY_VERSION,
            NORMALIZED_SEARCH_KEYBOARD_FIX_VERSION,
            BOOKMARKS_AND_RECENT_BOOKS_VERSION,
            WAL_JOURNAL_MODE_VERSION,
            FOOTNOTES_SEARCH_INDEX_VERSION,
            SOURCE_PDF_HINT_VERSION,
            BOOK_RATINGS_VERSION,
            PARAGRAPHS_VERSION,
            HADEES_AND_AYAH_NUMBERS_VERSION,
            BOOKS_SEARCH_INDEX_VERSION,
            DROP_UNUSED_PARAGRAPHS_SEARCH_INDEX_VERSION,
        ]

        rows = connection.execute(
            "SELECT MJCN, Name, ParentMJCN FROM CategoryTaxonomy ORDER BY MJCN"
        ).fetchall()
        assert rows == [(9, "Fiqh", 0), (10, "Hadith", 0)]


def test_categories_migration_resolves_inconsistent_spelling_by_frequency(
    tmp_path: Path,
) -> None:
    """When the same MJCN has conflicting Name/ParentMJCN, the most common wins."""
    database_path = tmp_path / "books.db"
    majority_a = Category(mjcn=5, name="Common Name", parent_mjcn=1, sort_key=1)
    majority_b = Category(mjcn=5, name="Common Name", parent_mjcn=1, sort_key=1)
    minority = Category(mjcn=5, name="Rare Spelling", parent_mjcn=2, sort_key=1)
    _seed_book_with_categories(database_path, "Book One", (majority_a,), "one.mjbz")
    _seed_book_with_categories(database_path, "Book Two", (majority_b,), "two.mjbz")
    _seed_book_with_categories(database_path, "Book Three", (minority,), "three.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        row = connection.execute(
            "SELECT Name, ParentMJCN FROM CategoryTaxonomy WHERE MJCN = 5"
        ).fetchone()
        assert row == ("Common Name", 1)


def test_categories_migration_produces_no_rows_when_no_books_have_categories(
    tmp_path: Path,
) -> None:
    """A database with no categorized books gets an empty (but present) taxonomy."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        count = connection.execute("SELECT COUNT(*) FROM CategoryTaxonomy").fetchone()[0]
        assert count == 0


def test_volumes_migration_groups_books_sharing_a_base_title(tmp_path: Path) -> None:
    """Migration 4 groups titles like 'X جلد N' into one Series with volume numbers."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "کفایت المفتی جلد 1", None, "one.mjbz")
    _seed_book(database_path, "کفایت المفتی جلد 2", None, "two.mjbz")
    _seed_book(database_path, "کفایت المفتی جلد 3", None, "three.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner = MigrationRunner(MIGRATIONS)
        applied = runner.migrate(connection)

        assert [migration.version for migration in applied] == [
            BASELINE_VERSION,
            AUTHORS_VERSION,
            CATEGORIES_VERSION,
            VOLUMES_VERSION,
            NORMALIZED_SEARCH_VERSION,
            TAXONOMY_VERSION,
            NORMALIZED_SEARCH_KEYBOARD_FIX_VERSION,
            BOOKMARKS_AND_RECENT_BOOKS_VERSION,
            WAL_JOURNAL_MODE_VERSION,
            FOOTNOTES_SEARCH_INDEX_VERSION,
            SOURCE_PDF_HINT_VERSION,
            BOOK_RATINGS_VERSION,
            PARAGRAPHS_VERSION,
            HADEES_AND_AYAH_NUMBERS_VERSION,
            BOOKS_SEARCH_INDEX_VERSION,
            DROP_UNUSED_PARAGRAPHS_SEARCH_INDEX_VERSION,
        ]

        series_rows = connection.execute("SELECT SeriesID, Title FROM Series").fetchall()
        assert series_rows == [(1, "کفایت المفتی")]

        rows = connection.execute(
            "SELECT Title, SeriesID, VolumeNumber FROM Books ORDER BY VolumeNumber"
        ).fetchall()
        assert rows == [
            ("کفایت المفتی جلد 1", 1, 1),
            ("کفایت المفتی جلد 2", 1, 2),
            ("کفایت المفتی جلد 3", 1, 3),
        ]


def test_volumes_migration_leaves_a_lone_volume_title_ungrouped(tmp_path: Path) -> None:
    """A title with a volume suffix but no sibling volumes gets no Series."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Some Book جلد 1", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        series_count = connection.execute("SELECT COUNT(*) FROM Series").fetchone()[0]
        assert series_count == 0

        row = connection.execute(
            "SELECT SeriesID, VolumeNumber FROM Books WHERE Title = 'Some Book جلد 1'"
        ).fetchone()
        assert row == (None, None)


def test_volumes_migration_leaves_non_volume_titles_untouched(tmp_path: Path) -> None:
    """A title with no volume suffix is left with SeriesID/VolumeNumber NULL."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "A Standalone Book", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        row = connection.execute(
            "SELECT SeriesID, VolumeNumber FROM Books WHERE Title = 'A Standalone Book'"
        ).fetchone()
        assert row == (None, None)


def test_model_volumes_is_safe_to_call_again_as_a_post_import_backfill(
    tmp_path: Path,
) -> None:
    """Calling `model_volumes` a second time (e.g. after a new importer adds
    more volumes of an existing work) doesn't error and re-derives the same
    real grouping - the guarantee a post-import backfill caller relies on."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "کفایت المفتی جلد 1", None, "one.mjbz")
    _seed_book(database_path, "کفایت المفتی جلد 2", None, "two.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        model_volumes(connection)  # re-run, simulating a post-import backfill call
        connection.commit()

        series_rows = connection.execute("SELECT SeriesID, Title FROM Series").fetchall()
        assert series_rows == [(1, "کفایت المفتی")]
        rows = connection.execute(
            "SELECT Title, SeriesID, VolumeNumber FROM Books ORDER BY VolumeNumber"
        ).fetchall()
        assert rows == [
            ("کفایت المفتی جلد 1", 1, 1),
            ("کفایت المفتی جلد 2", 1, 2),
        ]


def test_model_volumes_keeps_a_genuine_single_shamela_file_multi_part_split_together(
    tmp_path: Path,
) -> None:
    """Every part of one real .mdb file (same shamelaID before '.mdb') still
    groups into one Series with its plain, unsuffixed title - the normal,
    non-colliding case is unaffected by the collision fix."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Some Work - part 1", None, "37024.mdb#part1")
    _seed_book(database_path, "Some Work - part 2", None, "37024.mdb#part2")
    _seed_book(database_path, "Some Work - part 3", None, "37024.mdb#part3")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        series_rows = connection.execute("SELECT SeriesID, Title FROM Series").fetchall()
        assert series_rows == [(1, "Some Work")]
        rows = connection.execute(
            "SELECT SeriesID, VolumeNumber FROM Books ORDER BY VolumeNumber"
        ).fetchall()
        assert rows == [(1, 1), (1, 2), (1, 3)]


def test_model_volumes_does_not_merge_two_different_shamela_files_with_a_colliding_title(
    tmp_path: Path,
) -> None:
    """Real bug fixed: two unrelated .mdb files whose titles regex-parse to
    the same base title used to be merged into one bogus interleaved
    Series. Each file's own parts now get their own, separately-numbered
    Series instead."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Some Work - part 1", None, "14324.mdb#part1")
    _seed_book(database_path, "Some Work - part 2", None, "14324.mdb#part2")
    _seed_book(database_path, "Some Work - part 114", None, "35881.mdb#part114")
    _seed_book(database_path, "Some Work - part 115", None, "35881.mdb#part115")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        series_rows = dict(connection.execute("SELECT Title, SeriesID FROM Series").fetchall())
        assert set(series_rows) == {"Some Work (14324)", "Some Work (35881)"}

        rows = connection.execute(
            "SELECT VolumeNumber, SeriesID FROM Books ORDER BY VolumeNumber"
        ).fetchall()
        assert rows[0][0] == 1 and rows[1][0] == 2
        assert rows[0][1] == rows[1][1] == series_rows["Some Work (14324)"]
        assert rows[2][0] == 114 and rows[3][0] == 115
        assert rows[2][1] == rows[3][1] == series_rows["Some Work (35881)"]
        assert series_rows["Some Work (14324)"] != series_rows["Some Work (35881)"]


def test_model_volumes_leaves_a_lone_colliding_fragment_ungrouped(tmp_path: Path) -> None:
    """If one of the two colliding files only contributes a single part, that
    lone fragment still doesn't form a Series (no demonstrated sibling),
    while the other file's real multi-part group still does."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Some Work - part 1", None, "14324.mdb#part1")
    _seed_book(database_path, "Some Work - part 2", None, "35881.mdb#part2")
    _seed_book(database_path, "Some Work - part 3", None, "35881.mdb#part3")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        series_rows = connection.execute("SELECT Title FROM Series").fetchall()
        assert series_rows == [("Some Work (35881)",)]

        lone_row = connection.execute(
            "SELECT SeriesID, VolumeNumber FROM Books WHERE Title = 'Some Work - part 1'"
        ).fetchone()
        assert lone_row == (None, None)


def test_model_volumes_removes_the_orphaned_bogus_series_after_a_split(
    tmp_path: Path,
) -> None:
    """A Series created when only one real source file was known about
    (so it got the plain, unsuffixed title) shouldn't linger with zero
    real books pointing at it once a second file's later-imported,
    same-title volumes force a real split on the next backfill run."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Some Work - part 1", None, "14324.mdb#part1")
    _seed_book(database_path, "Some Work - part 2", None, "14324.mdb#part2")
    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)
        assert connection.execute(
            "SELECT Title FROM Series"
        ).fetchall() == [("Some Work",)]

    # A second, different real .mdb file's volumes for the same
    # regex-parsed title show up later (e.g. a second Shamela import
    # batch) - re-running model_volumes() should now detect the real
    # collision, split both apart, and clean up the now-orphaned plain
    # "Some Work" row.
    _seed_book(database_path, "Some Work - part 114", None, "35881.mdb#part114")
    _seed_book(database_path, "Some Work - part 115", None, "35881.mdb#part115")
    with sqlite3.connect(database_path) as connection:
        model_volumes(connection)
        connection.commit()

        series_titles = {
            row[0] for row in connection.execute("SELECT Title FROM Series").fetchall()
        }
        assert "Some Work" not in series_titles
        assert series_titles == {"Some Work (14324)", "Some Work (35881)"}


def test_model_volumes_clears_a_series_left_with_only_one_member(tmp_path: Path) -> None:
    """Real gap found applying this fix to production: if a sibling volume
    is later deleted elsewhere (e.g. real duplicate-removal), nothing else
    reconciles Series membership - a re-run of model_volumes() should
    self-heal a Series left with fewer than 2 real members, the same
    ">=2 members" rule applied when a Series is first created."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Some Work جلد 1", None, "one.mjbz")
    _seed_book(database_path, "Some Work جلد 2", None, "two.mjbz")
    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)
        assert connection.execute("SELECT Title FROM Series").fetchall() == [("Some Work",)]

        # Simulate a sibling volume being deleted elsewhere (e.g. as a
        # duplicate) without going through model_volumes() at all.
        connection.execute("DELETE FROM Books WHERE Title = 'Some Work جلد 2'")
        connection.commit()

        model_volumes(connection)
        connection.commit()

        assert connection.execute("SELECT Title FROM Series").fetchall() == []
        row = connection.execute(
            "SELECT SeriesID, VolumeNumber FROM Books WHERE Title = 'Some Work جلد 1'"
        ).fetchone()
        assert row == (None, None)


def test_model_volumes_collision_fix_is_idempotent_on_rerun(tmp_path: Path) -> None:
    """Re-running produces the exact same disambiguated Series, not new
    suffixes or duplicate rows each time."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Some Work - part 1", None, "14324.mdb#part1")
    _seed_book(database_path, "Some Work - part 2", None, "14324.mdb#part2")
    _seed_book(database_path, "Some Work - part 114", None, "35881.mdb#part114")
    _seed_book(database_path, "Some Work - part 115", None, "35881.mdb#part115")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)
        model_volumes(connection)
        connection.commit()

        series_rows = connection.execute("SELECT Title FROM Series ORDER BY Title").fetchall()
        assert series_rows == [("Some Work (14324)",), ("Some Work (35881)",)]


def _seed_book_with_page_content(database_path: Path, title: str, content: str, source: str) -> None:
    """Import one minimal real book carrying the given raw page content."""
    book = Book(
        information={"Name": title},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, content, "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / source,)
    )


def test_normalized_search_migration_backfills_existing_pages(tmp_path: Path) -> None:
    """Migration 5 populates PagesFTSNormalized with normalized existing content."""
    database_path = tmp_path / "books.db"
    _seed_book_with_page_content(database_path, "Book One", "الْحَمْدُ لِلَّهِ علی", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        applied = runner_migrate_all(connection)
        assert NORMALIZED_SEARCH_VERSION in [m.version for m in applied]

        stored = connection.execute("SELECT Content FROM PagesFTSNormalized").fetchone()[0]
        assert stored == "الحمد لله علي"


def test_normalized_search_migration_stays_in_sync_for_future_imports(tmp_path: Path) -> None:
    """The pure-SQL trigger keeps PagesFTSNormalized in sync for imports after migration."""
    database_path = tmp_path / "books.db"
    _seed_book_with_page_content(database_path, "Book One", "placeholder", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

    # A second, later import - simulating ongoing use after the migration ran once.
    _seed_book_with_page_content(database_path, "Book Two", "أحمد إبراهيم", "two.mjbz")

    with sqlite3.connect(database_path) as connection:
        rows = {
            row[0]
            for row in connection.execute(
                "SELECT Content FROM PagesFTSNormalized"
            ).fetchall()
        }
        assert "احمد ابراهيم" in rows


def test_normalized_search_migration_matches_variant_spellings(tmp_path: Path) -> None:
    """A query using one letter-form variant matches content using another."""
    database_path = tmp_path / "books.db"
    _seed_book_with_page_content(database_path, "Book One", "كتاب علی الفقه", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

        from islamic_research_hub.shared.arabic_text_normalization import (
            normalize_search_text,
        )

        match = connection.execute(
            "SELECT COUNT(*) FROM PagesFTSNormalized WHERE PagesFTSNormalized MATCH ?",
            (normalize_search_text("علي"),),
        ).fetchone()[0]
        assert match == 1


def test_taxonomy_migration_seeds_all_nine_dimensions(tmp_path: Path) -> None:
    """Migration 6 creates the taxonomy tables and seeds all nine real dimensions."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", "Imam Al-Ghazali", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        codes = {
            row[0] for row in connection.execute("SELECT Code FROM TaxonomyDimensions")
        }
        assert codes == set(TAXONOMY_DIMENSIONS)


def test_taxonomy_migration_leaves_existing_categories_and_authors_untouched(
    tmp_path: Path,
) -> None:
    """Migration 6 is purely additive - the existing normalized tables are unaffected."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", "Imam Al-Ghazali", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        authors = connection.execute("SELECT Name FROM Authors").fetchall()
        assert authors == [("Imam Al-Ghazali",)]

        term_count = connection.execute("SELECT COUNT(*) FROM TaxonomyTerms").fetchone()[0]
        assert term_count == 0


def test_taxonomy_tables_support_a_real_hierarchical_term_and_a_book_link(
    tmp_path: Path,
) -> None:
    """A real term, its multilingual names, and a book link all work end-to-end."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", "Imam Al-Ghazali", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        MigrationRunner(MIGRATIONS).migrate(connection)

        subject_dimension_id = connection.execute(
            "SELECT DimensionID FROM TaxonomyDimensions WHERE Code = 'subject'"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO TaxonomyTerms (TermID, DimensionID, ParentTermID) VALUES (1, ?, NULL)",
            (subject_dimension_id,),
        )
        connection.execute(
            "INSERT INTO TaxonomyTerms (TermID, DimensionID, ParentTermID) VALUES (2, ?, 1)",
            (subject_dimension_id,),
        )
        connection.execute(
            "INSERT INTO TaxonomyTermNames (TermID, LanguageCode, Name, IsPrimary) "
            "VALUES (2, 'ar', 'الزكاة', 1)"
        )
        connection.execute(
            "INSERT INTO TaxonomyTermNames (TermID, LanguageCode, Name, IsPrimary) "
            "VALUES (2, 'en', 'Zakat', 1)"
        )
        connection.execute("INSERT INTO BookTaxonomyTerms (BookID, TermID) VALUES (1, 2)")
        connection.commit()

        child_row = connection.execute(
            "SELECT ParentTermID FROM TaxonomyTerms WHERE TermID = 2"
        ).fetchone()
        assert child_row == (1,)

        names = dict(
            connection.execute(
                "SELECT LanguageCode, Name FROM TaxonomyTermNames WHERE TermID = 2"
            ).fetchall()
        )
        assert names == {"ar": "الزكاة", "en": "Zakat"}

        linked_books = connection.execute(
            "SELECT BookID FROM BookTaxonomyTerms WHERE TermID = 2"
        ).fetchall()
        assert linked_books == [(1,)]


def test_keyboard_fix_migration_matches_kaf_keheh_cross_keyboard_variants(
    tmp_path: Path,
) -> None:
    """A query typed with an Urdu keheh matches content stored with an Arabic kaf.

    Real bug this migration fixes: migration 5's trigger has its
    normalization SQL baked in at creation time, so updating
    `_NORMALIZATION_PAIRS` alone does not change an already-migrated
    database - this migration rebuilds both the trigger and the already-
    indexed content.
    """
    database_path = tmp_path / "books.db"
    _seed_book_with_page_content(database_path, "Book One", "كتاب الفقه", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

        from islamic_research_hub.shared.arabic_text_normalization import (
            normalize_search_text,
        )

        match = connection.execute(
            "SELECT COUNT(*) FROM PagesFTSNormalized WHERE PagesFTSNormalized MATCH ?",
            (normalize_search_text("کتاب"),),  # Urdu keheh, content has Arabic kaf
        ).fetchone()[0]
        assert match == 1


def test_keyboard_fix_migration_rebuilt_trigger_still_normalizes_new_pages(
    tmp_path: Path,
) -> None:
    """After the rebuild, a book imported afterward still gets indexed normalized."""
    database_path = tmp_path / "books.db"
    _seed_book_with_page_content(database_path, "Book One", "placeholder", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

    # Import a second book after all migrations (including the rebuild) have run.
    _seed_book_with_page_content(database_path, "Book Two", "کتاب جدید", "two.mjbz")

    with sqlite3.connect(database_path) as connection:
        from islamic_research_hub.shared.arabic_text_normalization import (
            normalize_search_text,
        )

        match = connection.execute(
            "SELECT COUNT(*) FROM PagesFTSNormalized WHERE PagesFTSNormalized MATCH ?",
            (normalize_search_text("كتاب"),),  # Arabic kaf, new content has Urdu keheh
        ).fetchone()[0]
        assert match == 1


def test_bookmarks_and_recent_books_migration_creates_real_working_tables(
    tmp_path: Path,
) -> None:
    """Migration 8 creates BookBookmarks/RecentBooks and real rows can be written."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

        connection.execute(
            "INSERT INTO BookBookmarks (BookID, PageNo, CreatedAt) VALUES (1, 5, datetime('now'))"
        )
        connection.execute(
            "INSERT INTO RecentBooks (BookID, LastPageNo, OpenedAt) "
            "VALUES (1, 5, datetime('now'))"
        )
        connection.commit()

        bookmark_row = connection.execute(
            "SELECT BookID, PageNo FROM BookBookmarks WHERE BookID = 1"
        ).fetchone()
        assert bookmark_row == (1, 5)

        recent_row = connection.execute(
            "SELECT BookID, LastPageNo FROM RecentBooks WHERE BookID = 1"
        ).fetchone()
        assert recent_row == (1, 5)


def test_wal_migration_switches_the_real_journal_mode(tmp_path: Path) -> None:
    """Migration 9 leaves the database in real WAL mode, verified via PRAGMA."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)
        mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"


def test_footnotes_search_migration_indexes_real_existing_footnotes(tmp_path: Path) -> None:
    """Migration 10 backfills FootnotesFTS/FootnotesFTSNormalized from real existing rows."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Hadith"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Main text", "Plain", footnote="A real note about sincerity"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

        raw_match = connection.execute(
            "SELECT COUNT(*) FROM FootnotesFTS WHERE FootnotesFTS MATCH 'sincerity'"
        ).fetchone()[0]
        assert raw_match == 1

        from islamic_research_hub.shared.arabic_text_normalization import (
            normalize_search_text,
        )

        normalized_match = connection.execute(
            "SELECT COUNT(*) FROM FootnotesFTSNormalized WHERE FootnotesFTSNormalized MATCH ?",
            (normalize_search_text("sincerity"),),
        ).fetchone()[0]
        assert normalized_match == 1


def test_footnotes_search_migration_trigger_indexes_future_footnotes(tmp_path: Path) -> None:
    """After the migration, a footnote imported afterward still gets indexed."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

    second_book = Book(
        information={"Name": "Book Two"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Main text", "Plain", footnote="A later real note about patience"),),
    )
    MasterBookRepository().import_books(
        database_path, (second_book,), (database_path.parent / "two.mjbz",)
    )

    with sqlite3.connect(database_path) as connection:
        match = connection.execute(
            "SELECT COUNT(*) FROM FootnotesFTS WHERE FootnotesFTS MATCH 'patience'"
        ).fetchone()[0]
        assert match == 1


def test_source_pdf_hint_migration_adds_a_null_column(tmp_path: Path) -> None:
    """Migration 11 adds Books.SourcePdfHint, additive and NULL until a backfill runs."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

        value = connection.execute("SELECT SourcePdfHint FROM Books").fetchone()[0]
        assert value is None

        connection.execute("UPDATE Books SET SourcePdfHint = 'REAL_PDF_NAME.pdf'")
        updated = connection.execute("SELECT SourcePdfHint FROM Books").fetchone()[0]
        assert updated == "REAL_PDF_NAME.pdf"


def test_book_ratings_migration_creates_an_empty_table(tmp_path: Path) -> None:
    """Migration 12 creates BookRatings, additive and empty until a user rates a book."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        book_id = connection.execute("SELECT BookID FROM Books").fetchone()[0]
        runner_migrate_all(connection)

        count = connection.execute("SELECT COUNT(*) FROM BookRatings").fetchone()[0]
        assert count == 0

        connection.execute(
            "INSERT INTO BookRatings (BookID, Rating, RatedAt) VALUES (?, 5, datetime('now'))",
            (book_id,),
        )
        rating = connection.execute("SELECT Rating FROM BookRatings").fetchone()[0]
        assert rating == 5


def test_books_search_migration_indexes_real_existing_books(tmp_path: Path) -> None:
    """Migration 15 backfills BooksFTS/BooksFTSNormalized from real existing rows."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Kashf Al-Bari", "Imam Al-Ghazali", "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

        title_match = connection.execute(
            "SELECT COUNT(*) FROM BooksFTS WHERE BooksFTS MATCH 'Kashf'"
        ).fetchone()[0]
        assert title_match == 1

        author_match = connection.execute(
            "SELECT COUNT(*) FROM BooksFTS WHERE BooksFTS MATCH 'Ghazali'"
        ).fetchone()[0]
        assert author_match == 1


def test_books_search_migration_trigger_indexes_future_books(tmp_path: Path) -> None:
    """After the migration, a book imported afterward still gets indexed."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "Book One", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

    _seed_book(database_path, "A Later Real Title", "A Later Real Author", "two.mjbz")

    with sqlite3.connect(database_path) as connection:
        match = connection.execute(
            "SELECT COUNT(*) FROM BooksFTS WHERE BooksFTS MATCH 'Later'"
        ).fetchone()[0]
        assert match == 1


def test_books_search_migration_normalized_index_matches_variant_spellings(
    tmp_path: Path,
) -> None:
    """BooksFTSNormalized tolerates real cross-keyboard spelling variants."""
    database_path = tmp_path / "books.db"
    _seed_book(database_path, "کتاب علی", None, "one.mjbz")

    with sqlite3.connect(database_path) as connection:
        runner_migrate_all(connection)

        from islamic_research_hub.shared.arabic_text_normalization import (
            normalize_search_text,
        )

        normalized_query = normalize_search_text("علي")  # variant spelling of علی
        match = connection.execute(
            "SELECT COUNT(*) FROM BooksFTSNormalized WHERE BooksFTSNormalized MATCH ?",
            (normalized_query,),
        ).fetchone()[0]
        assert match == 1


def runner_migrate_all(connection: sqlite3.Connection) -> tuple[Migration, ...]:
    """Run the real MIGRATIONS registry to completion against one connection."""
    return MigrationRunner(MIGRATIONS).migrate(connection)
