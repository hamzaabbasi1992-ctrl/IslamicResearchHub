"""Tests for the desktop app's Search screen, wired to a real master database."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Category, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
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

    assert "1 result" in screen._status_label.text()
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

    assert "1 result" in screen._status_label.text()


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


def test_details_button_opens_a_dialog_with_the_real_book_metadata(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Clicking Details on a result opens a dialog built from the real catalog data."""
    from islamic_research_hub.interfaces.desktop_app import search_screen as search_screen_module

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs")
    qtbot.addWidget(screen)

    captured = {}
    original_init = search_screen_module.BookDetailsDialog.__init__

    def fake_init(self, metadata, parent=None):
        captured["metadata"] = metadata
        original_init(self, metadata, parent)

    monkeypatch.setattr(search_screen_module.BookDetailsDialog, "__init__", fake_init)
    monkeypatch.setattr(search_screen_module.BookDetailsDialog, "exec", lambda self: None)

    screen._show_details(1)

    assert captured["metadata"].title == "Book of Fiqh"
    assert captured["metadata"].author == "Author One"
