"""Tests for the desktop app's Search screen, wired to a real master database."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QFrame, QLabel, QPushButton  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Category, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (  # noqa: E402
    RecentBookRepository,
)
from islamic_research_hub.domain.models.semantic_search_result import (  # noqa: E402
    SemanticSearchResult,
)
from islamic_research_hub.infrastructure.persistence.sqlite_page_embedding_repository import (  # noqa: E402
    PageEmbeddingError,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen  # noqa: E402


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


class FakeSemanticSearchService:
    """A real-shaped, controllable stand-in for SemanticBookSearchService.

    Duck-typed rather than subclassed - SearchScreen only ever calls
    `.search(query, limit, library)`, matching the real service's public
    surface, so no real embedder/model is ever loaded in these tests.
    """

    def __init__(
        self,
        results: tuple[SemanticSearchResult, ...] = (),
        error: Exception | None = None,
    ) -> None:
        self._results = results
        self._error = error
        self.last_query: str | None = None

    def search(
        self, query: str, limit: int = 20, library: str | None = None
    ) -> tuple[SemanticSearchResult, ...]:
        self.last_query = query
        if self._error is not None:
            raise self._error
        return self._results[:limit]


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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    assert "1 content result" in screen._status_label.text()
    assert screen._results_layout.count() == 2  # one card + the trailing stretch


def _seed_two_matching_books(database_path: Path) -> None:
    """Two real books that both match the same query, for keyboard-nav tests."""
    book_one = Book(
        information={"Name": "Book One", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence, part one", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    book_two = Book(
        information={"Name": "Book Two", "ANAME": "Author Two"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "The rules of jurisprudence, part two", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )


def test_arrow_keys_move_selection_through_result_cards(qtbot, tmp_path: Path) -> None:
    """Search UX: Down/Up arrows move a real, visible selection through
    results without needing to click - keyboard-only navigation."""
    database_path = tmp_path / "books.db"
    _seed_two_matching_books(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Down)
    assert screen._selected_card_index == 0

    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Down)
    assert screen._selected_card_index == 1

    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Up)
    assert screen._selected_card_index == 0


def test_enter_opens_the_selected_result(qtbot, tmp_path: Path) -> None:
    """Pressing Enter with a card selected opens it, instead of re-searching."""
    database_path = tmp_path / "books.db"
    _seed_two_matching_books(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Down)

    with qtbot.waitSignal(screen.open_in_viewer_requested, timeout=1000) as blocker:
        qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)
    assert blocker.args[1] == 1  # target page


def test_copy_citation_button_on_a_result_card_copies_a_real_citation(
    qtbot, tmp_path: Path
) -> None:
    """Search UX: Copy Citation is available directly on result cards, not
    just in the reader - reuses the existing format_citation(), no new backend."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    card = screen._results_layout.itemAt(0).widget()
    citation_button = next(b for b in card.findChildren(QPushButton) if b.text() == "Copy citation")
    citation_button.click()

    from PySide6.QtGui import QGuiApplication

    assert "Book of Fiqh" in QGuiApplication.clipboard().text()


def test_result_card_excerpt_is_capped_to_a_dense_desktop_height(
    qtbot, tmp_path: Path
) -> None:
    """Layout Audit fix: excerpts no longer grow unbounded (the 'mobile
    card' complaint) - a real, enforced max height caps them to ~2 lines."""
    from islamic_research_hub.interfaces.desktop_app.search_screen import (
        _EXCERPT_MAX_HEIGHT_PX,
    )

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    card = screen._results_layout.itemAt(0).widget()
    assert isinstance(card, QFrame)
    excerpt_labels = [
        label
        for label in card.findChildren(QLabel)
        if label.maximumHeight() == _EXCERPT_MAX_HEIGHT_PX
    ]
    assert len(excerpt_labels) == 1


def test_results_and_detail_panes_have_no_redundant_native_frame(
    qtbot, tmp_path: Path
) -> None:
    """Layout Audit fix: both scroll areas previously rendered a native Qt
    frame stacked on top of their own #resultCard QSS border - a real,
    doubled-border artifact found during the audit."""
    from PySide6.QtWidgets import QScrollArea

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    detail_pane = next(
        area for area in screen.findChildren(QScrollArea) if area.widget() is screen._detail_content
    )
    assert screen._results_area.frameShape() == QFrame.Shape.NoFrame
    assert detail_pane.frameShape() == QFrame.Shape.NoFrame


def test_search_screen_shows_no_results_message(qtbot, tmp_path: Path) -> None:
    """A query with no matches shows a clear message and no result cards."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._author_edit, "Author Two")
    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    assert "1 content result" in screen._status_label.text()


def test_search_screen_library_dropdown_lists_real_libraries(qtbot, tmp_path: Path) -> None:
    """The library filter is populated from the real database, not hardcoded."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    items = [screen._library_combo.itemText(i) for i in range(screen._library_combo.count())]
    assert "All libraries" in items
    assert "Maktaba Jibreel (Mobile)" in items


def test_search_screen_clears_previous_results_on_new_search(qtbot, tmp_path: Path) -> None:
    """Running a second search replaces the first result set, doesn't append to it."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)
    assert screen._results_layout.count() == 2

    screen._query_edit.clear()
    qtbot.keyClicks(screen._query_edit, "nonexistentterm")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)
    assert screen._results_layout.count() == 1


def test_detail_panel_shows_a_real_empty_state_before_any_selection(
    qtbot, tmp_path: Path
) -> None:
    """Real bug: the right-hand detail pane used to start as a totally
    blank rectangle (just a layout stretch, no widget) before any result
    was clicked - a real, visible "big empty box". It now shows a real
    guidance message instead."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._detail_layout.count() >= 1
    first_item = screen._detail_layout.itemAt(0).widget()
    assert first_item is not None
    assert "select a result" in first_item.text().lower()


def test_details_button_populates_the_inline_detail_panel(qtbot, tmp_path: Path) -> None:
    """Clicking Details on a result fills the right-hand panel with real catalog data."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._show_details(1, page_number=1)

    all_labels_text = " ".join(
        label.text()
        for label in screen._detail_content.findChildren(type(screen._status_label))
    )
    assert "Book of Fiqh" in all_labels_text
    assert "Author One" in all_labels_text


def test_detail_panel_shows_not_rated_by_default(qtbot, tmp_path: Path) -> None:
    """A book with no stored rating shows "Not rated" selected, not an error."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._show_details(1, page_number=1)

    assert screen._rating_combo.currentData() is None
    assert screen._rating_combo.currentText() == "Not rated"


def test_selecting_a_rating_persists_it(qtbot, tmp_path: Path) -> None:
    """Picking a star rating in the detail panel really saves it."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    screen._show_details(1, page_number=1)

    screen._rating_combo.setCurrentIndex(screen._rating_combo.findData(4))

    assert screen._ratings.get_rating(1) == 4


def test_reopening_details_shows_the_previously_saved_rating(qtbot, tmp_path: Path) -> None:
    """Re-opening a rated book's details pre-selects its real stored rating."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    screen._ratings.set_rating(1, 5)

    screen._show_details(1, page_number=1)

    assert screen._rating_combo.currentData() == 5
    assert screen._rating_combo.currentText() == "★★★★★"


def test_clicking_a_category_in_the_tree_filters_and_searches(qtbot, tmp_path: Path) -> None:
    """Clicking a real category node sets the category filter and runs a search."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._filter_by_author("Author One")

    assert screen._results_layout.count() == 2  # one book card + trailing stretch


def test_clicking_a_library_chip_with_no_query_browses_its_books_directly(
    qtbot, tmp_path: Path
) -> None:
    """With an empty search box, clicking a specific library chip lists its real books."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._filter_by_library("Maktaba Jibreel (Mobile)")

    assert screen._results_layout.count() == 2  # one book card + trailing stretch


def test_clicking_all_libraries_with_no_query_prompts_instead_of_listing_everything(
    qtbot, tmp_path: Path
) -> None:
    """"All libraries" with no query doesn't dump the whole corpus as cards."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._filter_by_library("All libraries")

    assert screen._results_layout.count() == 1  # only the trailing stretch
    assert "Type a search" in screen._status_label.text()


def test_recent_tab_shows_empty_state_with_no_history(qtbot, tmp_path: Path) -> None:
    """A fresh database (no books ever opened) shows an honest empty message."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._show_browse_tab(2)

    labels = [
        label.text() for label in screen._recent_list.findChildren(type(screen._status_label))
    ]
    assert any("No recently opened books" in text for text in labels)


def test_recent_tab_lists_a_real_recently_opened_book_and_opens_it_on_click(
    qtbot, tmp_path: Path
) -> None:
    """A real recorded open shows up in the Recent tab and re-opens at its last page."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    RecentBookRepository(database_path).record_open(1, page_number=5)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._show_browse_tab(2)

    buttons = screen._recent_list.findChildren(QPushButton)
    assert len(buttons) == 1
    assert "Book of Fiqh" in buttons[0].text()

    with qtbot.waitSignal(screen.open_in_viewer_requested, timeout=1000) as blocker:
        buttons[0].click()
    assert blocker.args == [1, 5]


def test_typing_an_author_and_clicking_search_with_no_query_browses_directly(
    qtbot, tmp_path: Path
) -> None:
    """Typing straight into the Author box and clicking Search (no query text)
    lists that author's real books, instead of doing nothing (previously the
    empty query box short-circuited _run_search before the filters were
    even read - see the CHANGELOG fix for this exact gap)."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._query_edit.setText("علي")
    screen._run_search()
    assert "1 content result" in screen._status_label.text()

    screen._exact_match_checkbox.setChecked(True)

    assert "No matches found" in screen._status_label.text()


def test_semantic_results_shown_as_a_separate_related_pages_section(
    qtbot, tmp_path: Path
) -> None:
    """When a semantic service is wired in, its results appear under
    "Related pages", separate from and in addition to keyword content
    results."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    semantic = FakeSemanticSearchService(
        results=(
            SemanticSearchResult(
                book_id=99,
                title="Conceptually Related Book",
                author="Someone",
                page_number=5,
                excerpt="A passage about the same idea, different words",
                similarity=0.87,
                library="Some Library",
            ),
        )
    )
    screen = SearchScreen(
        database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), semantic_search_service=semantic
    )
    qtbot.addWidget(screen)

    screen._query_edit.setText("jurisprudence")
    screen._run_search()
    with qtbot.waitSignal(screen._semantic_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)  # let the queued search_succeeded slot run after the thread finishes

    assert "1 related page" in screen._status_label.text()
    assert semantic.last_query == "jurisprudence"
    all_titles = " ".join(
        label.text() for label in screen._results_area.findChildren(type(screen._status_label))
    )
    assert "Conceptually Related Book" in all_titles
    assert "Related pages" in all_titles


def test_semantic_results_exclude_pages_already_shown_as_keyword_matches(
    qtbot, tmp_path: Path
) -> None:
    """A page found by both keyword and semantic search is shown once, not twice."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    semantic = FakeSemanticSearchService(
        results=(
            SemanticSearchResult(
                book_id=1,
                title="Book of Fiqh",
                author="Author One",
                page_number=1,
                excerpt="duplicate of the real keyword match",
                similarity=0.99,
                library="Maktaba Jibreel (Mobile)",
            ),
        )
    )
    screen = SearchScreen(
        database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), semantic_search_service=semantic
    )
    qtbot.addWidget(screen)

    screen._query_edit.setText("jurisprudence")
    screen._run_search()
    with qtbot.waitSignal(screen._semantic_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert "0 related page" not in screen._status_label.text()
    assert "related page" not in screen._status_label.text()


def test_semantic_search_failure_degrades_gracefully_not_a_crash(
    qtbot, tmp_path: Path
) -> None:
    """A semantic-search failure (e.g. no embedding index yet) never breaks
    the real keyword search results."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    semantic = FakeSemanticSearchService(error=PageEmbeddingError("no index"))
    screen = SearchScreen(
        database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), semantic_search_service=semantic
    )
    qtbot.addWidget(screen)

    screen._query_edit.setText("jurisprudence")
    screen._run_search()
    with qtbot.waitSignal(screen._semantic_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert "1 content result" in screen._status_label.text()
    assert "related page" not in screen._status_label.text()


def test_semantic_search_is_skipped_under_exact_match(qtbot, tmp_path: Path) -> None:
    """Exact match means literal keyword matching only - no semantic results."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    semantic = FakeSemanticSearchService(
        results=(
            SemanticSearchResult(
                book_id=99, title="Other", author=None, page_number=1,
                excerpt="x", similarity=0.9, library=None,
            ),
        )
    )
    screen = SearchScreen(
        database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), semantic_search_service=semantic
    )
    qtbot.addWidget(screen)

    screen._exact_match_checkbox.setChecked(True)
    screen._query_edit.setText("jurisprudence")
    screen._run_search()

    assert semantic.last_query is None


def test_lazy_semantic_search_is_not_attempted_by_default(qtbot, tmp_path: Path) -> None:
    """Without enable_lazy_semantic_search, no real service is ever built -
    real model loading is opt-in, never a side effect of a plain search."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    build_calls = []
    screen._build_real_semantic_search_service = lambda: (build_calls.append(1), None)[1]

    screen._query_edit.setText("jurisprudence")
    screen._run_search()

    assert build_calls == []


def test_lazy_semantic_search_builds_at_most_once_across_searches(
    qtbot, tmp_path: Path
) -> None:
    """The real service is built (attempted) on the first search only - a
    second search reuses the cached result instead of retrying the load."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(
        database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), enable_lazy_semantic_search=True
    )
    qtbot.addWidget(screen)
    build_calls = []
    fake_service = FakeSemanticSearchService()

    def _fake_build() -> FakeSemanticSearchService:
        build_calls.append(1)
        return fake_service

    screen._build_real_semantic_search_service = _fake_build

    screen._query_edit.setText("jurisprudence")
    screen._run_search()
    with qtbot.waitSignal(screen._semantic_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    screen._run_search()
    with qtbot.waitSignal(screen._semantic_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert build_calls == [1]
    assert screen._semantic_search_service is fake_service


def test_search_target_book_name_only_skips_content_search(qtbot, tmp_path: Path) -> None:
    """"Book name only" finds real title matches and never runs content search."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    title_only_index = screen._search_target_combo.findData("title")
    screen._search_target_combo.setCurrentIndex(title_only_index)
    screen._query_edit.setText("Fiqh")
    screen._run_search()

    assert "title match" in screen._status_label.text()
    assert "content result" not in screen._status_label.text()


def test_search_target_book_content_only_skips_title_search(qtbot, tmp_path: Path) -> None:
    """"Book content only" finds real content matches and never runs title search."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    content_only_index = screen._search_target_combo.findData("content")
    screen._search_target_combo.setCurrentIndex(content_only_index)
    screen._query_edit.setText("jurisprudence")
    screen._run_search()

    assert "content result" in screen._status_label.text()
    assert "title match" not in screen._status_label.text()


def test_search_target_default_runs_both_name_and_content(qtbot, tmp_path: Path) -> None:
    """The default "Name + content" still runs both, matching prior behavior."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._query_edit.setText("Fiqh")
    screen._run_search()

    assert "title match" in screen._status_label.text()
    assert "content result" in screen._status_label.text()


def test_scope_dropdown_footnotes_finds_a_real_footnote_only_term(qtbot, tmp_path: Path) -> None:
    """Selecting "Footnotes" in the scope dropdown finds a term only in a footnote,
    and shows it tagged as a footnote match on the result card."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Hadith"},
        categories=(),
        table_of_contents=(),
        pages=(
            Page(1, 1, "Main text about prayer", "Plain",
                 footnote="A real note discussing sincerity in worship"),
        ),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._query_edit.setText("sincerity")
    screen._run_search()
    assert "No matches found" in screen._status_label.text()

    footnotes_index = screen._scope_combo.findData("footnotes")
    screen._scope_combo.setCurrentIndex(footnotes_index)

    assert "1 content result" in screen._status_label.text()
    labels_text = " ".join(
        label.text() for label in screen._results_area.findChildren(type(screen._status_label))
    )
    assert "footnote match" in labels_text


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
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
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


def test_running_a_search_records_it_in_recent_searches(qtbot, tmp_path: Path) -> None:
    """Running a real search adds the query to the recent-searches store."""
    from PySide6.QtCore import QSettings

    from islamic_research_hub.interfaces.desktop_app.search_history import RecentSearchStore

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    store = RecentSearchStore(settings)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), recent_search_store=store)
    qtbot.addWidget(screen)

    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)

    assert store.list_recent() == ["jurisprudence"]


def test_search_box_has_a_completer_seeded_from_authors_and_recent_searches(
    qtbot, tmp_path: Path
) -> None:
    """The search box offers real author/category/recent-search suggestions."""
    from PySide6.QtCore import QSettings

    from islamic_research_hub.interfaces.desktop_app.search_history import RecentSearchStore

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    RecentSearchStore(settings).record("a prior search")
    screen = SearchScreen(
        database_path,
        tmp_path / "maknoon_pdfs",
        _translator(tmp_path),
        recent_search_store=RecentSearchStore(settings),
    )
    qtbot.addWidget(screen)

    completer = screen._query_edit.completer()

    assert completer is not None
    model = completer.model()
    suggestions = {model.index(row, 0).data() for row in range(model.rowCount())}
    assert "Author One" in suggestions
    assert "a prior search" in suggestions


def test_detail_panel_toggle_collapses_and_expands(qtbot, tmp_path: Path) -> None:
    """UI Polish Pass 2: the detail (right) pane can be collapsed to free
    width for the reader/results, mirroring ViewerScreen's existing TOC
    toggle - visible by default, matching prior behavior."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    assert screen._detail_toggle_button.isChecked() is True
    assert screen._splitter.sizes()[2] > 0

    expanded_width = screen._splitter.sizes()[2]

    screen._detail_toggle_button.setChecked(False)
    screen._detail_panel_animation.setCurrentTime(1000)  # jump straight to the end value

    # A QScrollArea's own real minimumSizeHint keeps a small residual width
    # even fully "collapsed" (see _on_detail_panel_toggled's docstring) -
    # the real assertion is "shrank dramatically", not literally 0.
    assert screen._splitter.sizes()[2] < expanded_width / 2

    screen._detail_toggle_button.setChecked(True)
    screen._detail_panel_animation.setCurrentTime(1000)

    assert screen._splitter.sizes()[2] >= expanded_width


def test_detail_panel_maximize_grows_it_and_shrinks_the_siblings(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.resize(1200, 700)
    screen.show()
    qtbot.waitExposed(screen)
    initial_sizes = screen._splitter.sizes()

    screen._on_detail_maximize_clicked()

    assert screen._detail_panel_toggle.is_maximized is True

    screen._on_detail_maximize_clicked()

    assert screen._detail_panel_toggle.is_maximized is False
    assert screen._splitter.sizes() == initial_sizes


def test_detail_panel_maximize_expands_it_first_if_collapsed(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.resize(1200, 700)
    screen._detail_toggle_button.setChecked(False)
    screen._detail_panel_animation.setCurrentTime(1000)

    screen._on_detail_maximize_clicked()

    assert screen._detail_toggle_button.isChecked() is True
    assert screen._splitter.sizes()[2] > 100


class _FakeVoiceTranscriber:
    """Transcriber returning a fixed transcript, recording what it was asked
    to transcribe - a real-shaped, controllable stand-in for
    FasterWhisperTranscriber, mirroring how FakeSemanticSearchService stands
    in for the real semantic search model."""

    def __init__(self, transcript: str = "jurisprudence", fail: bool = False) -> None:
        self.transcript = transcript
        self.fail = fail
        self.last_samples: tuple[float, ...] | None = None

    def transcribe(self, samples: tuple[float, ...], sample_rate: int) -> str:
        if self.fail:
            raise RuntimeError("transcription failed")
        self.last_samples = samples
        return self.transcript


def _install_fake_voice_transcriber(
    screen: SearchScreen, transcript: str = "jurisprudence", fail: bool = False
) -> _FakeVoiceTranscriber:
    """Inject a fake transcriber in place of the real FasterWhisperTranscriber,
    mirroring _install_fake_tts in test_viewer_screen.py."""
    from islamic_research_hub.application.voice_transcription import VoiceSearchService

    transcriber = _FakeVoiceTranscriber(transcript=transcript, fail=fail)
    screen._build_real_voice_search_service = lambda: (
        None if fail else VoiceSearchService(transcriber)
    )
    return transcriber


def test_mic_button_hidden_when_voice_search_disabled_by_default(qtbot, tmp_path: Path) -> None:
    """Without enable_lazy_voice_search, the mic button doesn't even show -
    a dead control offering a feature that's off is worse than no control."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._mic_button.isHidden() is True


def test_mic_button_visible_when_voice_search_enabled(qtbot, tmp_path: Path) -> None:
    """With enable_lazy_voice_search=True (the real Settings-toggle-on
    case), the mic button shows."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(
        database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), enable_lazy_voice_search=True
    )
    qtbot.addWidget(screen)

    assert screen._mic_button.isHidden() is False


def test_lazy_voice_search_is_not_attempted_by_default(qtbot, tmp_path: Path) -> None:
    """Without enable_lazy_voice_search, no real service is ever built -
    real model loading is opt-in, never a side effect of recording."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    qtbot.addWidget(screen)
    build_calls = []
    screen._build_real_voice_search_service = lambda: (build_calls.append(1), None)[1]

    screen._on_recording_captured((0.1, 0.2, 0.1), 16000)

    assert build_calls == []


def test_finishing_a_recording_transcribes_and_runs_search(qtbot, tmp_path: Path) -> None:
    """`_on_recording_captured` is the directly-callable, test-friendly
    completion seam - real QAudioSource microphone capture has no place in
    a headless test, so this calls it with synthetic samples instead of
    driving real hardware. A successful transcript fills the query box and
    runs a real search."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(
        database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), enable_lazy_voice_search=True
    )
    qtbot.addWidget(screen)
    transcriber = _install_fake_voice_transcriber(screen, transcript="jurisprudence")

    screen._on_recording_captured((0.1, 0.2, 0.1), 16000)
    with qtbot.waitSignal(screen._voice_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert transcriber.last_samples == (0.1, 0.2, 0.1)
    assert screen._query_edit.text() == "jurisprudence"
    assert "1 content result" in screen._status_label.text()
    assert screen._mic_button.isEnabled()


def test_voice_search_failure_resets_mic_button_without_crashing(qtbot, tmp_path: Path) -> None:
    """A build/transcription failure (e.g. the optional "voice" extra isn't
    installed, or real silence was recorded) must degrade gracefully -
    typed search keeps working unaffected."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = SearchScreen(
        database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path), enable_lazy_voice_search=True
    )
    qtbot.addWidget(screen)
    _install_fake_voice_transcriber(screen, fail=True)

    screen._on_recording_captured((0.1, 0.2, 0.1), 16000)
    with qtbot.waitSignal(screen._voice_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert screen._mic_button.isEnabled()
    assert screen._query_edit.text() == ""
    # The screen itself is still fully usable - real typed search still works.
    qtbot.keyClicks(screen._query_edit, "jurisprudence")
    qtbot.keyClick(screen._query_edit, Qt.Key.Key_Return)
    assert "1 content result" in screen._status_label.text()


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    """Static chrome (tabs, filter combos, buttons) and the idle status/
    empty detail placeholder all re-render in the new language."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    translator = _translator(tmp_path)
    screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", translator)
    qtbot.addWidget(screen)
    assert screen._categories_tab_button.text() == "Categories"
    assert screen._search_button.text() == "Search"
    assert screen._library_combo.itemText(0) == "All libraries"

    translator.set_language("ur")

    assert screen._categories_tab_button.text() == "موضوعات"
    assert screen._search_button.text() == "تلاش کریں"
    assert screen._library_combo.itemText(0) == "تمام مکاتب"
    assert screen._exact_match_checkbox.text() == "عین مطابق"
    assert screen._status_label.text() == "تلاش کریں، یا براؤز کرنے کے لیے کوئی مخصوص زمرہ/مصنف/لائبریری منتخب کریں۔"
