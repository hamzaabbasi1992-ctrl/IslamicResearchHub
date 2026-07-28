"""Tests for the desktop app's Search screen, wired to a real master database."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Category, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen  # noqa: E402


def _seed_database(database_path: Path) -> None:
    """Import one real book with searchable content and a category."""
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(Category(mjcn=9, name="Fiqh", parent_mjcn=0, sort_key=1),),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence in fiqh are extensive", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_search_screen_shows_ranked_results(qtbot, tmp_path: Path) -> None:
    """Typing a query and pressing Enter populates result cards."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    assert "1 content result" in screen._status_label.text()
    assert screen._results_layout.count() == 2  # one card + the trailing stretch


def test_search_screen_shows_no_results_message(qtbot, tmp_path: Path) -> None:
    """A query with no matches shows a clear message and no result cards."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._query_edit, "nonexistentterm")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    assert "No matches found" in screen._status_label.text()
    assert screen._results_layout.count() == 1  # only the trailing stretch


def test_search_screen_respects_author_filter(qtbot, tmp_path: Path) -> None:
    """The author filter field restricts results, matching the CLI's --author."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    other_book = Book(
        information={"Name": "Other Book", "ANAME": "Author Two"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence explained again", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (other_book,), (database_path.parent / "other.mjbz",)
    )
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._author_edit, "Author Two")
    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    assert "1 content result" in screen._status_label.text()


def test_search_screen_library_dropdown_lists_real_libraries(qtbot, tmp_path: Path) -> None:
    """The library filter is populated from the real database, not hardcoded."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    items = [screen._library_combo.itemText(i) for i in range(screen._library_combo.count())]
    assert "All libraries" in items
    assert "Maktaba Jibreel (Mobile)" in items


def test_search_screen_clears_previous_results_on_new_search(qtbot, tmp_path: Path) -> None:
    """Running a second search replaces the first result set, doesn't append to it."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)
    assert screen._results_layout.count() == 2

    screen._query_edit.clear()
    qtbot.keyClicks(screen._query_edit, "nonexistentterm")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)
    assert screen._results_layout.count() == 1


def test_details_button_populates_the_inline_detail_panel(qtbot, tmp_path: Path) -> None:
    """Clicking Details on a result fills the right-hand panel with real catalog data."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    screen._show_details(1, page_number=1)

    all_labels_text = " ".join(
        label.text()
        for label in screen._detail_content.findChildren(type(screen._status_label))
    )
    assert "Book of Fiqh" in all_labels_text
    assert "Author One" in all_labels_text


def test_clicking_a_category_in_the_tree_filters_and_searches(qtbot, tmp_path: Path) -> None:
    """Clicking a real category node sets the category filter and runs a search."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    screen._query_edit.setText("jurisprudence")
    top_item = screen._category_tree.topLevelItem(0)
    assert top_item is not None
    screen._on_category_clicked(top_item, 0)

    assert screen._category_edit.text() == "Fiqh"
    assert "1 content result" in screen._status_label.text()


def test_clicking_an_author_in_the_list_filters_and_searches(qtbot, tmp_path: Path) -> None:
    """Clicking a real author row sets the author filter and runs a search."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    screen._query_edit.setText("jurisprudence")
    screen._filter_by_author("Author One")

    assert screen._author_edit.text() == "Author One"
    assert "1 content result" in screen._status_label.text()


def test_clicking_a_category_with_no_query_browses_its_books_directly(
    qtbot, tmp_path: Path
) -> None:
    """With an empty search box, clicking a category lists its real books directly
    (previously did nothing - see the CHANGELOG fix for this exact gap)."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    top_item = screen._category_tree.topLevelItem(0)
    assert top_item is not None
    screen._on_category_clicked(top_item, 0)

    assert "1 book" in screen._status_label.text()
    assert screen._results_layout.count() == 2  # one book card + trailing stretch


def test_clicking_an_author_with_no_query_browses_their_books_directly(
    qtbot, tmp_path: Path
) -> None:
    """With an empty search box, clicking an author lists their real books directly."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    screen._filter_by_author("Author One")

    assert screen._results_layout.count() == 2  # one book card + trailing stretch


def test_clicking_a_library_chip_with_no_query_browses_its_books_directly(
    qtbot, tmp_path: Path
) -> None:
    """With an empty search box, clicking a specific library chip lists its real books."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    screen._filter_by_library("Maktaba Jibreel (Mobile)")

    assert screen._results_layout.count() == 2  # one book card + trailing stretch


def test_clicking_all_libraries_with_no_query_prompts_instead_of_listing_everything(
    qtbot, tmp_path: Path
) -> None:
    """"All libraries" with no query doesn't dump the whole corpus as cards."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    screen._filter_by_library("All libraries")

    assert screen._results_layout.count() == 1  # only the trailing stretch
    assert "Type a search" in screen._status_label.text()


def test_typing_an_author_and_clicking_search_with_no_query_browses_directly(
    qtbot, tmp_path: Path
) -> None:
    """Typing straight into the Author box and clicking Search (no query text)
    lists that author's real books, instead of doing nothing (previously the
    empty query box short-circuited _run_search before the filters were
    even read - see the CHANGELOG fix for this exact gap)."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._author_edit, "Author One")
    screen._run_search()

    assert "1 book" in screen._status_label.text()
    assert screen._results_layout.count() == 2  # one book card + trailing stretch


def test_typing_a_category_and_clicking_search_with_no_query_browses_directly(
    qtbot, tmp_path: Path
) -> None:
    """Typing straight into the Category box and clicking Search (no query
    text) lists that category's real books directly."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._category_edit, "Fiqh")
    screen._run_search()

    assert "1 book" in screen._status_label.text()
    assert screen._results_layout.count() == 2  # one book card + trailing stretch


def test_search_shows_real_title_matches_separately_from_content_matches(
    qtbot, tmp_path: Path
) -> None:
    """A query matching a real book title shows a distinct "Matching titles" group."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._query_edit, "Fiqh")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    assert "1 title match" in screen._status_label.text()


def test_exact_match_checkbox_requires_literal_spelling(qtbot, tmp_path: Path) -> None:
    """With Exact match checked, a spelling-variant query finds nothing, even
    though the same query finds a real match with it unchecked."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book About Ali"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "كتاب علی الفقه", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    screen._query_edit.setText("علي")
    screen._run_search()
    assert "1 content result" in screen._status_label.text()

    screen._exact_match_checkbox.setChecked(True)

    assert "No matches found" in screen._status_label.text()


def test_browse_filter_narrows_the_real_author_list(qtbot, tmp_path: Path) -> None:
    """Typing into the browse filter hides authors that don't match, in real time."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    other_book = Book(
        information={"Name": "Other Book", "ANAME": "Someone Else"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Other content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (other_book,), (database_path.parent / "other.mjbz",)
    )
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)
    screen._show_browse_tab(1)

    screen._browse_filter_edit.setText("Author One")

    # isHidden() reflects the widget's own explicit visibility flag (set by
    # our filter's setVisible() calls) regardless of whether the top-level
    # window is actually on-screen - unlike isVisible(), which also depends
    # on the whole ancestor chain being shown, unreliable in a headless test.
    buttons_by_name = dict(screen._author_row_buttons)
    assert buttons_by_name["Someone Else"].isHidden() is True
    assert buttons_by_name["Author One"].isHidden() is False
