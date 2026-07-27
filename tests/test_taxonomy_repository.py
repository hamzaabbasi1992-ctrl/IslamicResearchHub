"""Tests for the general multi-dimensional taxonomy repository."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import MigrationRunner
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import (
    TaxonomyRepository,
    UnknownDimensionError,
)


def _migrated_database(tmp_path: Path) -> Path:
    """Create a real, fully-migrated database with one real book (BookID 1)."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Zakat"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    return database_path


def test_get_or_create_term_creates_a_real_term_with_a_primary_name(tmp_path: Path) -> None:
    """A brand-new term gets created with its primary name recorded."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))

    term_id = repo.get_or_create_term("subject", "الزكاة", "ar")

    terms = repo.list_terms("subject")
    assert len(terms) == 1
    assert terms[0].term_id == term_id
    assert terms[0].names == {"ar": "الزكاة"}


def test_get_or_create_term_returns_the_same_id_for_the_same_name(tmp_path: Path) -> None:
    """Calling it twice with the same name doesn't create a duplicate term."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))

    first_id = repo.get_or_create_term("subject", "الزكاة", "ar")
    second_id = repo.get_or_create_term("subject", "الزكاة", "ar")

    assert first_id == second_id
    assert len(repo.list_terms("subject")) == 1


def test_get_or_create_term_resolves_via_a_recorded_alias(tmp_path: Path) -> None:
    """A name matching a real recorded alias resolves to the existing term, not a new one."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))
    term_id = repo.get_or_create_term("subject", "الزكاة", "ar")
    repo.add_alias(term_id, "زکوة", "ur")

    resolved_id = repo.get_or_create_term("subject", "زکوة", "ur")

    assert resolved_id == term_id
    assert len(repo.list_terms("subject")) == 1


def test_get_or_create_term_raises_for_an_unknown_dimension(tmp_path: Path) -> None:
    """A dimension code that isn't one of the nine real ones raises clearly."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))

    with pytest.raises(UnknownDimensionError):
        repo.get_or_create_term("not-a-real-dimension", "Something", "en")


def test_link_book_and_list_books_for_term(tmp_path: Path) -> None:
    """Linking a real book to a term makes it show up in both directions."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))
    term_id = repo.get_or_create_term("subject", "الزكاة", "ar")

    repo.link_book(1, term_id)

    assert repo.list_books_for_term(term_id) == (1,)
    linked_terms = repo.list_terms_for_book(1, dimension_code="subject")
    assert len(linked_terms) == 1
    assert linked_terms[0].term_id == term_id


def test_get_term_tree_builds_a_real_parent_child_hierarchy(tmp_path: Path) -> None:
    """Subject terms with a real ParentTermID nest correctly under their parent."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))
    fiqh_id = repo.get_or_create_term("subject", "الفقه", "ar")
    zakat_id = repo.get_or_create_term("subject", "الزكاة", "ar", parent_term_id=fiqh_id)

    tree = repo.get_term_tree("subject")

    assert len(tree) == 1
    assert tree[0].term_id == fiqh_id
    assert len(tree[0].children) == 1
    assert tree[0].children[0].term_id == zakat_id


def test_add_name_records_a_second_language_for_a_term(tmp_path: Path) -> None:
    """A term can carry real primary names in more than one language."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))
    term_id = repo.get_or_create_term("subject", "الزكاة", "ar")

    repo.add_name(term_id, "en", "Zakat", is_primary=True)

    terms = repo.list_terms("subject")
    assert terms[0].names == {"ar": "الزكاة", "en": "Zakat"}


def test_merge_duplicate_terms_merges_by_normalized_identity_and_keeps_book_links(
    tmp_path: Path,
) -> None:
    """Two terms that normalize to the same text merge, keeping every real book link."""
    database_path = _migrated_database(tmp_path)
    repo = TaxonomyRepository(database_path)
    # Two distinct spellings that normalize to the same text (alef variant).
    first_id = repo.get_or_create_term("subject", "علي", "ar")
    with sqlite3.connect(database_path) as connection:
        # Bypass get_or_create_term's own dedup so both terms genuinely exist,
        # simulating two independent imports that used different spellings.
        connection.execute(
            "INSERT INTO TaxonomyTerms (TermID, DimensionID, ParentTermID) "
            "SELECT 999, DimensionID, NULL FROM TaxonomyDimensions WHERE Code = 'subject'"
        )
        connection.execute(
            "INSERT INTO TaxonomyTermNames (TermID, LanguageCode, Name, IsPrimary) "
            "VALUES (999, 'ar', 'علی', 1)"
        )
        connection.commit()
    repo.link_book(1, first_id)
    repo.link_book(1, 999)

    merged_count = repo.merge_duplicate_terms("subject")

    assert merged_count == 1
    remaining_terms = repo.list_terms("subject")
    assert len(remaining_terms) == 1
    assert repo.list_books_for_term(remaining_terms[0].term_id) == (1,)


def test_taxonomy_repository_never_touches_the_existing_categories_table(tmp_path: Path) -> None:
    """Real proof of non-interference: creating taxonomy terms doesn't alter Categories."""
    database_path = _migrated_database(tmp_path)
    with sqlite3.connect(database_path) as connection:
        categories_before = connection.execute("SELECT COUNT(*) FROM Categories").fetchone()[0]

    TaxonomyRepository(database_path).get_or_create_term("subject", "الزكاة", "ar")

    with sqlite3.connect(database_path) as connection:
        categories_after = connection.execute("SELECT COUNT(*) FROM Categories").fetchone()[0]
    assert categories_after == categories_before
