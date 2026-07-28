"""Tests for the semantic embedding index CLI's real resume/batch logic.

Only `_load_pages_to_index` (pure SQL, no ML model involved) is tested
directly - `main()` constructs a real `SentenceTransformerEmbedder`, which
loads an actual local model and is deliberately left untested here, same
as the rest of this codebase's AI-dependent CLIs.
"""

import sqlite3
from pathlib import Path

import pytest

from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.sqlite_page_embedding_repository import (
    SqlitePageEmbeddingRepository,
)
from islamic_research_hub.interfaces.semantic_index_cli import _load_pages_to_index


def _seed_database(database_path: Path) -> None:
    """Import two real books, one under a real subject category, one not."""
    fiqh_book = Book(
        information={"Name": "Book of Fiqh", "MJCN": "9"},
        categories=(Category(mjcn=9, name="Fiqh", parent_mjcn=0, sort_key=1),),
        table_of_contents=(),
        pages=(Page(1, 1, "First page", "Plain"), Page(2, 2, "Second page", "Plain")),
    )
    MasterBookRepository().import_books(
        database_path, (fiqh_book,), (database_path.parent / "one.mjbz",)
    )
    other_book = Book(
        information={"Name": "Book of Hadith"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Only page", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (other_book,), (database_path.parent / "two.mjbz",)
    )


def test_load_pages_to_index_with_no_subject_returns_every_real_page(tmp_path: Path) -> None:
    """Omitting `subject` returns pages from every book in the corpus."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    SqlitePageEmbeddingRepository(database_path).ensure_schema()

    pages = _load_pages_to_index(database_path, subject=None, limit=None)

    assert len(pages) == 3


def test_load_pages_to_index_restricts_to_a_real_subject(tmp_path: Path) -> None:
    """Giving `subject` restricts pages to books resolving to that root category."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    SqlitePageEmbeddingRepository(database_path).ensure_schema()

    pages = _load_pages_to_index(database_path, subject="Fiqh", limit=None)

    assert len(pages) == 2
    assert all(book_id == 1 for book_id, _, _ in pages)


def test_load_pages_to_index_skips_pages_already_embedded(tmp_path: Path) -> None:
    """Real resume behavior: a page already in PageEmbeddings is never returned again."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    store = SqlitePageEmbeddingRepository(database_path)
    store.ensure_schema()
    store.store(((1, 1, (1.0, 0.0)),))

    pages = _load_pages_to_index(database_path, subject=None, limit=None)

    assert (1, 1, "First page") not in pages
    assert len(pages) == 2


def test_load_pages_to_index_respects_limit_for_a_deliberately_batched_run(
    tmp_path: Path,
) -> None:
    """`limit` caps a single run to a bounded batch, for splitting a large job up."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    SqlitePageEmbeddingRepository(database_path).ensure_schema()

    pages = _load_pages_to_index(database_path, subject=None, limit=1)

    assert len(pages) == 1


def test_load_pages_to_index_excludes_blank_content_pages(tmp_path: Path) -> None:
    """Pages with no real text content are never returned for embedding.

    A real book always has non-blank page content by the time it's
    imported (`MasterBookRepository` falls back to `content_p` when
    `content_f` is blank) - a genuinely blank/NULL `Pages.Content` row is
    inserted directly here to exercise this SQL-level guard on its own.
    """
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book With A Blank Page"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO Pages (BookID, PageNo, Content) VALUES (1, 2, '   ')"
        )
        connection.commit()
    SqlitePageEmbeddingRepository(database_path).ensure_schema()

    pages = _load_pages_to_index(database_path, subject=None, limit=None)

    assert len(pages) == 1
    assert pages[0][2] == "Real content"


def test_running_twice_with_a_limit_makes_real_incremental_progress(tmp_path: Path) -> None:
    """Two limited runs, storing between them, together cover every real page
    exactly once - simulating a batched/resumed real run across sessions."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    store = SqlitePageEmbeddingRepository(database_path)
    store.ensure_schema()

    first_batch = _load_pages_to_index(database_path, subject=None, limit=2)
    assert len(first_batch) == 2
    store.store(
        tuple((book_id, page_number, (1.0, 0.0)) for book_id, page_number, _ in first_batch)
    )

    second_batch = _load_pages_to_index(database_path, subject=None, limit=2)

    assert len(second_batch) == 1
    seen_keys = {(book_id, page_number) for book_id, page_number, _ in first_batch}
    seen_keys |= {(book_id, page_number) for book_id, page_number, _ in second_batch}
    assert len(seen_keys) == 3  # every real page covered exactly once, no repeats


def test_sqlite_error_on_a_missing_database_propagates(tmp_path: Path) -> None:
    """A missing database raises sqlite3.Error, matching main()'s try/except."""
    missing_path = tmp_path / "does_not_exist" / "books.db"

    with pytest.raises(sqlite3.Error):
        _load_pages_to_index(missing_path, subject=None, limit=None)
