"""Tests for the general multi-dimensional taxonomy repository."""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Category, Page
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


def test_get_or_create_term_with_stable_key_never_collapses_same_name_terms(
    tmp_path: Path,
) -> None:
    """Two source records sharing display text stay distinct when each has its own StableKey.

    Real bug this guards against: 43 of 691 real `CategoryTaxonomy` rows
    share exact `Name` text with an unrelated category under a different
    parent - matching by text alone silently collapsed them into one term.
    """
    repo = TaxonomyRepository(_migrated_database(tmp_path))

    first_id = repo.get_or_create_term("subject", "2009", "ar", stable_key="mjcn:70")
    second_id = repo.get_or_create_term("subject", "2009", "ar", stable_key="mjcn:89")

    assert first_id != second_id
    assert len(repo.list_terms("subject")) == 2


def test_get_or_create_term_with_stable_key_is_idempotent(tmp_path: Path) -> None:
    """Calling it twice with the same StableKey returns the same term, not a duplicate."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))

    first_id = repo.get_or_create_term("subject", "الزكاة", "ar", stable_key="mjcn:10")
    second_id = repo.get_or_create_term("subject", "الزكاة", "ar", stable_key="mjcn:10")

    assert first_id == second_id
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


def test_list_term_book_counts_reflects_real_links(tmp_path: Path) -> None:
    """Each term's real linked-book count, including zero for an unlinked term."""
    repo = TaxonomyRepository(_migrated_database(tmp_path))
    zakat_id = repo.get_or_create_term("subject", "الزكاة", "ar")
    fiqh_id = repo.get_or_create_term("subject", "الفقه", "ar")
    repo.link_book(1, zakat_id)

    counts = dict(
        (term.term_id, count) for term, count in repo.list_term_book_counts("subject")
    )

    assert counts[zakat_id] == 1
    assert counts[fiqh_id] == 0


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


def _migrated_database_with_categories_and_authors(tmp_path: Path) -> Path:
    """A real, fully-migrated database with real category hierarchy and authors."""
    database_path = tmp_path / "books.db"
    fiqh = Category(mjcn=9, name="الفقه", parent_mjcn=0, sort_key=1)
    zakat = Category(mjcn=10, name="الزكاة", parent_mjcn=9, sort_key=1)
    book_one = Book(
        information={"Name": "Book of Zakat", "ANAME": "Imam Al-Ghazali"},
        categories=(fiqh, zakat),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    book_two = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Imam Al-Ghazali"},
        categories=(fiqh,),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    return database_path


def test_populate_subjects_creates_real_terms_with_real_hierarchy(tmp_path: Path) -> None:
    """Subjects are populated from CategoryTaxonomy with the real parent/child structure intact."""
    database_path = _migrated_database_with_categories_and_authors(tmp_path)
    repo = TaxonomyRepository(database_path)

    count = repo.populate_subjects_from_category_taxonomy()

    assert count == 2
    tree = repo.get_term_tree("subject")
    assert len(tree) == 1
    assert tree[0].names["ar"] == "الفقه"
    assert len(tree[0].children) == 1
    assert tree[0].children[0].names["ar"] == "الزكاة"


def test_populate_subjects_keeps_categories_with_duplicate_display_text_distinct(
    tmp_path: Path,
) -> None:
    """Two real, unrelated categories that happen to share Name text stay two real terms.

    Reproduces the real production bug: `CategoryTaxonomy` can legitimately
    contain two different MJCNs under two different parents with the exact
    same `Name` (confirmed for real: 43 of 691 rows). Population must not
    silently merge them.
    """
    database_path = tmp_path / "books.db"
    root_a = Category(mjcn=100, name="Root A", parent_mjcn=0, sort_key=1)
    root_b = Category(mjcn=200, name="Root B", parent_mjcn=0, sort_key=2)
    duplicate_under_a = Category(mjcn=101, name="2009", parent_mjcn=100, sort_key=1)
    duplicate_under_b = Category(mjcn=201, name="2009", parent_mjcn=200, sort_key=1)
    book_one = Book(
        information={"Name": "Book One"},
        categories=(root_a, duplicate_under_a),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    book_two = Book(
        information={"Name": "Book Two"},
        categories=(root_b, duplicate_under_b),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    repo = TaxonomyRepository(database_path)

    count = repo.populate_subjects_from_category_taxonomy()

    assert count == 4  # Root A, Root B, and both distinct "2009" categories
    duplicate_named_terms = [t for t in repo.list_terms("subject") if t.names["ar"] == "2009"]
    assert len(duplicate_named_terms) == 2
    assert duplicate_named_terms[0].term_id != duplicate_named_terms[1].term_id
    assert {t.parent_term_id for t in duplicate_named_terms} == {
        next(t for t in repo.list_terms("subject") if t.names["ar"] == "Root A").term_id,
        next(t for t in repo.list_terms("subject") if t.names["ar"] == "Root B").term_id,
    }


def test_populate_subjects_is_idempotent_across_repeated_runs(tmp_path: Path) -> None:
    """Running population twice doesn't create duplicate real terms."""
    database_path = _migrated_database_with_categories_and_authors(tmp_path)
    repo = TaxonomyRepository(database_path)
    repo.populate_subjects_from_category_taxonomy()

    second_count = repo.populate_subjects_from_category_taxonomy()

    assert second_count == 2
    assert len(repo.list_terms("subject")) == 2


def test_populate_authors_creates_one_real_term_per_author(tmp_path: Path) -> None:
    """Authors are populated from the real, already-deduplicated Authors table."""
    database_path = _migrated_database_with_categories_and_authors(tmp_path)
    repo = TaxonomyRepository(database_path)

    count = repo.populate_authors_from_authors_table()

    assert count == 1  # both books share the same real author
    terms = repo.list_terms("author")
    assert len(terms) == 1
    assert terms[0].names["ar"] == "Imam Al-Ghazali"


def test_link_books_to_populated_taxonomy_links_real_subjects_and_authors(
    tmp_path: Path,
) -> None:
    """Every real book gets linked to its real subject(s) and author after population."""
    database_path = _migrated_database_with_categories_and_authors(tmp_path)
    repo = TaxonomyRepository(database_path)
    repo.populate_subjects_from_category_taxonomy()
    repo.populate_authors_from_authors_table()

    subject_links, author_links = repo.link_books_to_populated_taxonomy()

    assert subject_links == 3  # book 1: fiqh+zakat, book 2: fiqh
    assert author_links == 2  # both books share one real author

    fiqh_term = next(t for t in repo.list_terms("subject") if t.names["ar"] == "الفقه")
    assert set(repo.list_books_for_term(fiqh_term.term_id)) == {1, 2}
    zakat_term = next(t for t in repo.list_terms("subject") if t.names["ar"] == "الزكاة")
    assert repo.list_books_for_term(zakat_term.term_id) == (1,)

    author_terms = repo.list_terms_for_book(1, dimension_code="author")
    assert len(author_terms) == 1
    assert author_terms[0].names["ar"] == "Imam Al-Ghazali"


def test_link_books_to_populated_taxonomy_resyncs_away_stale_subject_links(
    tmp_path: Path,
) -> None:
    """A stale subject link (e.g. left over from the StableKey collision bug,
    now fixed) is removed on the next link call, not just added-to."""
    database_path = _migrated_database_with_categories_and_authors(tmp_path)
    repo = TaxonomyRepository(database_path)
    repo.populate_subjects_from_category_taxonomy()
    repo.populate_authors_from_authors_table()
    real_fiqh_term = next(t for t in repo.list_terms("subject") if t.names["ar"] == "الفقه")
    fake_term_id = repo.get_or_create_term("subject", "Stale Wrong Term", "ar")
    repo.link_book(1, fake_term_id)  # simulate a stale link left over from the old bug

    subject_links, _ = repo.link_books_to_populated_taxonomy()

    assert fake_term_id not in {t.term_id for t in repo.list_terms_for_book(1, "subject")}
    assert real_fiqh_term.term_id in {t.term_id for t in repo.list_terms_for_book(1, "subject")}
    assert repo.list_books_for_term(fake_term_id) == ()
    assert subject_links == 3


def test_populate_subjects_returns_zero_before_categories_migration_has_run(
    tmp_path: Path,
) -> None:
    """Before CategoryTaxonomy exists, population is a safe no-op, not a crash."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book"}, categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )

    count = TaxonomyRepository(database_path).populate_subjects_from_category_taxonomy()

    assert count == 0


def _migrated_database_with_language_and_publisher(tmp_path: Path) -> Path:
    """A real, fully-migrated database with real, mixed-spelling language values."""
    database_path = tmp_path / "books.db"
    book_one = Book(
        information={"Name": "Book One", "Language": "ur", "PNAME": "Darul Uloom Press"},
        categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    book_two = Book(
        information={"Name": "Book Two", "Language": "Urdu", "PNAME": "Darul Uloom Press"},
        categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )
    book_three = Book(
        information={"Name": "Book Three", "Language": "ar"},
        categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_three,), (database_path.parent / "three.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    return database_path


def test_populate_languages_merges_real_spelling_variants_into_one_term(
    tmp_path: Path,
) -> None:
    """"ur" and "Urdu" are the same real language - they merge into one term, not two."""
    database_path = _migrated_database_with_language_and_publisher(tmp_path)
    repo = TaxonomyRepository(database_path)

    count = repo.populate_languages_from_books()

    assert count == 2  # Urdu (merged from "ur"+"Urdu") and Arabic (from "ar")
    names = {term.names["en"] for term in repo.list_terms("language")}
    assert names == {"Urdu", "Arabic"}


def test_populate_languages_is_idempotent(tmp_path: Path) -> None:
    """Running language population twice doesn't create duplicate real terms."""
    database_path = _migrated_database_with_language_and_publisher(tmp_path)
    repo = TaxonomyRepository(database_path)
    repo.populate_languages_from_books()

    second_count = repo.populate_languages_from_books()

    assert second_count == 2
    assert len(repo.list_terms("language")) == 2


def test_populate_publishers_creates_one_real_term_per_distinct_publisher(
    tmp_path: Path,
) -> None:
    """Two real books sharing a publisher produce one real publisher term."""
    database_path = _migrated_database_with_language_and_publisher(tmp_path)
    repo = TaxonomyRepository(database_path)

    count = repo.populate_publishers_from_books()

    assert count == 1
    terms = repo.list_terms("publisher")
    assert terms[0].names["ar"] == "Darul Uloom Press"


def test_link_books_to_languages_and_publishers_links_real_data(tmp_path: Path) -> None:
    """Every real book gets linked to its real (merged) language and publisher."""
    database_path = _migrated_database_with_language_and_publisher(tmp_path)
    repo = TaxonomyRepository(database_path)
    repo.populate_languages_from_books()
    repo.populate_publishers_from_books()

    language_links, publisher_links = repo.link_books_to_languages_and_publishers()

    assert language_links == 3  # all three books have a real language
    assert publisher_links == 2  # only books one and two have a real publisher

    urdu_term = next(t for t in repo.list_terms("language") if t.names["en"] == "Urdu")
    assert set(repo.list_books_for_term(urdu_term.term_id)) == {1, 2}
    arabic_term = next(t for t in repo.list_terms("language") if t.names["en"] == "Arabic")
    assert repo.list_books_for_term(arabic_term.term_id) == (3,)
