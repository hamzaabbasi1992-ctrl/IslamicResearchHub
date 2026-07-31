"""Tests for the desktop app's global keyboard shortcuts.

Triggers each shortcut by emitting its `QShortcut.activated` signal
directly, rather than simulating real key presses - real key-press
delivery depends on window focus/activation state, which is unreliable
in an offscreen headless test environment. Emitting the signal directly
still exercises the exact same connected behavior a real key press would.
"""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

import sqlite3

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QKeySequence  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.bookmark_repository import (  # noqa: E402
    BookmarkRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.interfaces.desktop_app.main_window import MainWindow  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.shortcuts import SHORTCUTS  # noqa: E402


def _isolated_settings(tmp_path: Path) -> QSettings:
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


def _shortcut_for(window: MainWindow, key: str):
    for shortcut in window._shortcuts:
        if shortcut.key() == QKeySequence(key):
            return shortcut
    raise AssertionError(f"No installed shortcut for {key!r}")


def test_installs_exactly_the_documented_shortcuts(qtbot, tmp_path: Path) -> None:
    """Every key in SHORTCUTS is actually wired, one QShortcut per entry."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    installed_keys = [shortcut.key().toString() for shortcut in window._shortcuts]
    documented_keys = [QKeySequence(key).toString() for key, _description in SHORTCUTS]
    assert sorted(installed_keys) == sorted(documented_keys)


def test_shortcuts_install_safely_with_no_database(qtbot, tmp_path: Path) -> None:
    """Shortcuts don't crash construction when there's no database to act on."""
    window = MainWindow(
        tmp_path / "does_not_exist" / "books.db",
        tmp_path / "maknoon_pdfs",
        _isolated_settings(tmp_path),
    )
    qtbot.addWidget(window)

    assert len(window._shortcuts) == len(SHORTCUTS)


def test_ctrl_f_switches_to_the_search_screen(qtbot, tmp_path: Path) -> None:
    """Ctrl+F jumps to the Search/Workspace screen."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    window._show_screen(0)  # start somewhere else (Home)

    _shortcut_for(window, "Ctrl+F").activated.emit()

    assert window._stack.currentIndex() == 1


def test_ctrl_comma_opens_settings(qtbot, tmp_path: Path) -> None:
    """Ctrl+, jumps straight to Settings."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    _shortcut_for(window, "Ctrl+,").activated.emit()

    assert window._stack.currentIndex() == 6


def test_alt_number_keys_jump_to_the_matching_rail_screen(qtbot, tmp_path: Path) -> None:
    """Alt+1..7 jump directly to each rail screen by position."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    for index, key in enumerate(
        ("Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5", "Alt+6", "Alt+7")
    ):
        _shortcut_for(window, key).activated.emit()
        assert window._stack.currentIndex() == index


def test_ctrl_d_toggles_dark_mode(qtbot, tmp_path: Path) -> None:
    """Ctrl+D flips the theme between light and dark."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    assert window._theme_controller.theme_name == "light"

    _shortcut_for(window, "Ctrl+D").activated.emit()
    assert window._theme_controller.theme_name == "dark"

    _shortcut_for(window, "Ctrl+D").activated.emit()
    assert window._theme_controller.theme_name == "light"


def test_ctrl_b_toggles_bookmark_on_the_open_book(qtbot, tmp_path: Path) -> None:
    """Ctrl+B bookmarks the currently-open reader page, via the real repository."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    window._search_screen.open_in_viewer_requested.emit(1, 1)

    _shortcut_for(window, "Ctrl+B").activated.emit()

    assert 1 in BookmarkRepository(database_path).list_bookmarked_pages(1)


def test_ctrl_b_is_a_safe_no_op_when_nothing_is_open(qtbot, tmp_path: Path) -> None:
    """Ctrl+B before any book is open doesn't raise."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    _shortcut_for(window, "Ctrl+B").activated.emit()  # must not raise
