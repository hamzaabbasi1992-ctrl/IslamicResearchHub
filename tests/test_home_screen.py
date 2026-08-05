"""Tests for the desktop app's Home dashboard screen."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Category, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.bookmark_repository import (  # noqa: E402
    BookmarkRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (  # noqa: E402
    RecentBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.home_screen import HomeScreen  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.search_history import RecentSearchStore  # noqa: E402


def _isolated_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def _seed_database(database_path: Path) -> None:
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(Category(mjcn=9, name="الفقه", parent_mjcn=0, sort_key=1),),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def _migrated_and_seeded(tmp_path: Path) -> Path:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    return database_path


def _new_screen(tmp_path: Path, database_path: Path) -> HomeScreen:
    return HomeScreen(
        database_path,
        Translator(_isolated_settings(tmp_path)),
        recent_search_store=RecentSearchStore(_isolated_settings(tmp_path)),
    )


def _row_texts(body_layout) -> list[str]:
    return [body_layout.itemAt(i).widget().text() for i in range(body_layout.count())]


def test_collections_and_pinned_books_and_ai_suggestions_stay_honest_placeholders(
    qtbot, tmp_path: Path
) -> None:
    """No backend exists for these sections - they never claim real data."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    assert "open a book" in screen._collections_body.text().lower()
    assert "isn't available" in screen._pinned_books_body.text().lower()
    assert "assistant panel" in screen._ai_suggestions_body.text().lower()


def test_continue_reading_rows_use_rtl_layout_for_real_book_titles(
    qtbot, tmp_path: Path
) -> None:
    """Typography fix: real Arabic/Urdu book titles need RTL layout
    direction, matching every other book-title row in the app."""
    database_path = _migrated_and_seeded(tmp_path)
    RecentBookRepository(database_path).record_open(book_id=1)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    button = screen._continue_reading_body.itemAt(0).widget()
    assert button.layoutDirection() == Qt.LayoutDirection.RightToLeft


def test_continue_reading_shows_a_real_clickable_recently_opened_book(
    qtbot, tmp_path: Path
) -> None:
    """Continue Reading reflects a real RecentBooks entry as a real, clickable row."""
    database_path = _migrated_and_seeded(tmp_path)
    RecentBookRepository(database_path).record_open(book_id=1, page_number=3)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    rows = _row_texts(screen._continue_reading_body)
    assert any("Book of Fiqh" in text for text in rows)


def test_clicking_a_continue_reading_row_emits_open_in_viewer_requested(
    qtbot, tmp_path: Path
) -> None:
    """A real click on a Continue Reading row opens that real book."""
    database_path = _migrated_and_seeded(tmp_path)
    RecentBookRepository(database_path).record_open(book_id=1, page_number=3)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)
    button = screen._continue_reading_body.itemAt(0).widget()

    with qtbot.waitSignal(screen.open_in_viewer_requested, timeout=1000) as blocker:
        button.click()
    assert blocker.args == [1, 1]


def test_continue_reading_is_honest_when_nothing_has_been_opened(qtbot, tmp_path: Path) -> None:
    """With no RecentBooks entries, the card says so rather than showing nothing."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    rows = _row_texts(screen._continue_reading_body)
    assert len(rows) == 1
    assert "no books opened" in rows[0].lower()


def test_recent_searches_shows_a_real_stored_query(qtbot, tmp_path: Path) -> None:
    """Recent Searches reflects the real RecentSearchStore, not a placeholder."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    RecentSearchStore(settings).record("hadith of intentions")
    screen = HomeScreen(
        database_path, Translator(settings), recent_search_store=RecentSearchStore(settings)
    )
    qtbot.addWidget(screen)

    assert "hadith of intentions" in screen._recent_searches_body.text()


def test_statistics_shows_real_corpus_counts(qtbot, tmp_path: Path) -> None:
    """Statistics reflects the real database's book/library counts."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    assert "1 books" in screen._statistics_body.text()


def test_bookmarks_shows_a_real_clickable_bookmark(qtbot, tmp_path: Path) -> None:
    """Bookmarks reflects a real BookBookmarks entry, across the whole library."""
    database_path = _migrated_and_seeded(tmp_path)
    BookmarkRepository(database_path).add_bookmark(1, 1)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    rows = _row_texts(screen._bookmarks_body)
    assert any("Book of Fiqh" in text and "page 1" in text for text in rows)


def test_bookmarks_is_honest_when_none_exist(qtbot, tmp_path: Path) -> None:
    """With no real bookmarks, the card says so rather than showing nothing."""
    database_path = _migrated_and_seeded(tmp_path)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    rows = _row_texts(screen._bookmarks_body)
    assert len(rows) == 1
    assert "no bookmarks" in rows[0].lower()


def test_recently_viewed_authors_derives_from_recent_books(qtbot, tmp_path: Path) -> None:
    """Recently Viewed Authors is derived from real recently-opened books,
    zero new query beyond what Continue Reading already fetches."""
    database_path = _migrated_and_seeded(tmp_path)
    RecentBookRepository(database_path).record_open(book_id=1)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    assert "Author One" in screen._recent_authors_body.text()


def test_recently_viewed_categories_shows_a_real_category(qtbot, tmp_path: Path) -> None:
    """Recently Viewed Categories reflects a real recently-opened book's real category."""
    database_path = _migrated_and_seeded(tmp_path)
    RecentBookRepository(database_path).record_open(book_id=1)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    assert "الفقه" in screen._recent_categories_body.text()


def test_library_health_starts_idle_and_updates_on_check(qtbot, tmp_path: Path) -> None:
    """Library Health only runs its real integrity scan on demand, not on load."""
    database_path = _migrated_and_seeded(tmp_path)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    assert "not checked" in screen._library_health_body.text().lower()

    screen._check_health_button.click()

    assert "healthy" in screen._library_health_body.text().lower()


def test_note_library_imported_updates_the_session_only_list(qtbot, tmp_path: Path) -> None:
    """A noted import shows up immediately, session-only (no persisted history)."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    screen.note_library_imported("Maktaba Ashrafia")

    assert "Maktaba Ashrafia" in screen._recently_imported_body.text()


def test_recently_imported_is_honest_when_nothing_was_imported_this_session(
    qtbot, tmp_path: Path
) -> None:
    """With no imports noted this run, the card says so rather than faking history."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = _new_screen(tmp_path, database_path)
    qtbot.addWidget(screen)

    assert "no libraries imported this session" in screen._recently_imported_body.text().lower()


def test_switching_language_retranslates_the_whole_screen(qtbot, tmp_path: Path) -> None:
    """Real bug this guards against: only Settings/header used to retranslate
    on a language change - every other screen, including this one, silently
    stayed in English. Heading, card titles, and placeholders must all
    update for real when the app language changes."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    translator = Translator(settings)
    screen = HomeScreen(
        database_path, translator, recent_search_store=RecentSearchStore(settings)
    )
    qtbot.addWidget(screen)
    assert screen._heading.text() == "Home"

    translator.set_language("ur")

    assert screen._heading.text() == "ہوم"
    assert screen._card_headings["home-card-bookmarks"].text() == "نشانیاں"
    assert screen._pinned_books_body.text() == "کتابیں پن کرنا ابھی دستیاب نہیں۔"
