"""Smoke tests for the desktop app's main window shell."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.main_window import MainWindow  # noqa: E402


def _isolated_settings(tmp_path: Path) -> QSettings:
    """A real QSettings backed by a temp ini file - never the real Windows registry.

    MainWindow's default QSettings(SETTINGS_ORGANIZATION, ...) is real,
    persistent, machine-wide storage; without this, every test here would
    read and write the actual app's saved language/font preference.
    """
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def _seed_database(database_path: Path) -> None:
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_main_window_constructs_with_search_screen_active(qtbot, tmp_path: Path) -> None:
    """The window opens on the Search screen without raising."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    assert window.windowTitle() == "Islamic Research Hub"
    assert window._stack.currentIndex() == 0


def test_rail_buttons_switch_the_visible_screen(qtbot, tmp_path: Path) -> None:
    """Clicking a rail button switches the stacked screen and its checked state."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    viewer_button = window._rail_buttons[1]
    qtbot.mouseClick(viewer_button, Qt.MouseButton.LeftButton)

    assert window._stack.currentIndex() == 1
    assert viewer_button.isChecked()
    assert not window._rail_buttons[0].isChecked()


def test_settings_screen_is_real_and_shows_real_app_info(qtbot, tmp_path: Path) -> None:
    """Settings is a real screen now, not a placeholder - it reflects the real database."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    settings_screen = window._stack.widget(4)
    assert settings_screen._language_combo.count() == 3
    assert settings_screen.default_font_size() > 0


def test_changing_language_updates_rail_labels_and_layout_direction(
    qtbot, tmp_path: Path
) -> None:
    """Switching to Urdu in Settings retranslates the rail and mirrors the app RTL.

    Resets QApplication's layout direction back to LTR afterward - it's a
    process-wide singleton shared across the whole test session, so leaving
    it RTL would leak into unrelated tests run later.
    """
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    settings_screen = window._stack.widget(4)

    try:
        ur_index = settings_screen._language_combo.findData("ur")
        settings_screen._language_combo.setCurrentIndex(ur_index)

        assert window._rail_buttons[0].text() == "تلاش"
        assert window._translator.layout_direction == Qt.LayoutDirection.RightToLeft
    finally:
        QApplication.instance().setLayoutDirection(Qt.LayoutDirection.LeftToRight)


def test_search_result_open_in_viewer_switches_screen_and_loads_the_book(
    qtbot, tmp_path: Path
) -> None:
    """Clicking 'Read in app' on a search result switches to Viewer with that book loaded."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    search_screen = window._stack.widget(0)
    viewer_screen = window._stack.widget(1)

    search_screen.open_in_viewer_requested.emit(1, 1)

    assert window._stack.currentIndex() == 1
    assert window._rail_buttons[1].isChecked()
    assert viewer_screen._title_label.text() == "Book of Fiqh"
    assert viewer_screen._content_label.text() == "Some real page content"


def test_missing_database_shows_a_clear_message_not_a_broken_search_screen(
    qtbot, tmp_path: Path
) -> None:
    """A missing database path shows an honest message instead of silently
    building a search screen backed by a nonexistent/empty database."""
    missing_path = tmp_path / "does_not_exist" / "books.db"

    window = MainWindow(missing_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    search_placeholder = window._stack.widget(0)
    labels = [label.text() for label in search_placeholder.findChildren(QLabel)]
    assert any("Database not found" in text for text in labels)
    assert any(str(missing_path) in text for text in labels)
    assert not missing_path.exists()  # never silently created
