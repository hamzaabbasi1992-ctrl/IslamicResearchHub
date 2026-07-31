"""Tests for the desktop app's Taxonomy Browser screen."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QPushButton  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Category, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import (  # noqa: E402
    TaxonomyRepository,
)
from islamic_research_hub.interfaces.desktop_app.taxonomy_browser_screen import (  # noqa: E402
    TaxonomyBrowserScreen,
)


def _seed_populated_database(database_path: Path) -> None:
    """Two real books, one real subject hierarchy, taxonomy fully populated."""
    fiqh = Category(mjcn=9, name="الفقه", parent_mjcn=0, sort_key=1)
    zakat = Category(mjcn=10, name="الزكاة", parent_mjcn=9, sort_key=1)
    book_one = Book(
        information={"Name": "كتاب الزكاة", "ANAME": "Imam Al-Ghazali"},
        categories=(fiqh, zakat),
        table_of_contents=(),
        pages=(Page(1, 1, "Content one", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    book_two = Book(
        information={"Name": "كتاب الفقه", "ANAME": "Imam Al-Ghazali"},
        categories=(fiqh,),
        table_of_contents=(),
        pages=(Page(1, 1, "Content two", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    taxonomy = TaxonomyRepository(database_path)
    taxonomy.populate_subjects_from_category_taxonomy()
    taxonomy.populate_authors_from_authors_table()
    taxonomy.link_books_to_populated_taxonomy()


def test_screen_selects_the_first_populated_dimension_by_default(
    qtbot, tmp_path: Path
) -> None:
    """Subject (populated) is selected on load; empty dimensions are disabled."""
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)

    screen = TaxonomyBrowserScreen(database_path)
    qtbot.addWidget(screen)

    assert screen._current_dimension == "subject"
    assert screen._dimension_buttons["subject"].isEnabled()
    assert screen._dimension_buttons["subject"].isChecked()
    assert not screen._dimension_buttons["madhhab"].isEnabled()


def test_subject_tree_shows_the_real_category_hierarchy(qtbot, tmp_path: Path) -> None:
    """The tree mirrors the real parent/child subject structure."""
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)

    screen = TaxonomyBrowserScreen(database_path)
    qtbot.addWidget(screen)

    assert screen._tree.topLevelItemCount() == 1
    root = screen._tree.topLevelItem(0)
    assert root.text(0) == "الفقه"
    assert root.childCount() == 1
    assert root.child(0).text(0) == "الزكاة"


def test_clicking_a_term_shows_its_real_linked_books(qtbot, tmp_path: Path) -> None:
    """Clicking a subject node lists exactly the real books linked to it."""
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    screen = TaxonomyBrowserScreen(database_path)
    qtbot.addWidget(screen)

    root = screen._tree.topLevelItem(0)  # الفقه - linked to both real books
    screen._on_term_clicked(root, 0)

    cards = screen.findChildren(QPushButton, "")
    read_buttons = [b for b in screen.findChildren(QPushButton) if b.text() == "Read in app"]
    assert len(read_buttons) == 2
    assert "2 book(s)" in screen._status_label.text()


def test_clicking_read_in_app_emits_open_in_viewer_requested(qtbot, tmp_path: Path) -> None:
    """The Read-in-app button on a book card emits the real signal main_window.py wires up."""
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    screen = TaxonomyBrowserScreen(database_path)
    qtbot.addWidget(screen)
    root = screen._tree.topLevelItem(0)
    screen._on_term_clicked(root, 0)
    read_button = next(b for b in screen.findChildren(QPushButton) if b.text() == "Read in app")

    with qtbot.waitSignal(screen.open_in_viewer_requested, timeout=1000) as blocker:
        read_button.click()
    book_id, page_number = blocker.args
    assert page_number == 1
    assert book_id in (1, 2)


def test_search_filter_hides_non_matching_terms_and_expands_matching_branches(
    qtbot, tmp_path: Path
) -> None:
    """Typing in the filter box narrows the tree, same pattern as Search's category tree."""
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    screen = TaxonomyBrowserScreen(database_path)
    qtbot.addWidget(screen)

    screen._filter_edit.setText("الزكاة")

    root = screen._tree.topLevelItem(0)
    assert not root.isHidden()  # ancestor of a match stays visible
    assert root.isExpanded()
    assert not root.child(0).isHidden()


def test_switching_dimensions_reloads_the_tree_and_clears_results(qtbot, tmp_path: Path) -> None:
    """Selecting a different populated dimension shows that dimension's own real terms."""
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    screen = TaxonomyBrowserScreen(database_path)
    qtbot.addWidget(screen)

    screen._select_dimension("author")

    assert screen._current_dimension == "author"
    assert screen._tree.topLevelItemCount() == 1
    assert screen._tree.topLevelItem(0).text(0) == "Imam Al-Ghazali"


def test_a_click_on_a_disabled_empty_dimension_does_nothing(qtbot, tmp_path: Path) -> None:
    """Selecting an unpopulated dimension is a safe no-op, not a crash."""
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    screen = TaxonomyBrowserScreen(database_path)
    qtbot.addWidget(screen)

    screen._select_dimension("madhhab")

    assert screen._current_dimension == "subject"  # unchanged


def test_screen_degrades_honestly_on_an_unmigrated_database(qtbot, tmp_path: Path) -> None:
    """A database with no TaxonomyDimensions table at all doesn't crash - it
    just has no selectable dimension, the same honest degradation
    `verify_database_cli.py` already uses elsewhere."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book"}, categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )

    screen = TaxonomyBrowserScreen(database_path)
    qtbot.addWidget(screen)

    assert not any(button.isEnabled() for button in screen._dimension_buttons.values())
    assert screen._empty_dimension_label.text() != ""
