"""Tests for the desktop app's Viewer screen, wired to a real master database."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.viewer_screen import ViewerScreen  # noqa: E402


def _seed_database(database_path: Path) -> None:
    """Import one real, multi-page book."""
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(
            Page(1, 1, "First page content", "Plain"),
            Page(2, 2, "Second page content", "Plain"),
            Page(3, 3, "Third page content", "Plain"),
        ),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_load_book_shows_title_author_and_first_page(qtbot, tmp_path: Path) -> None:
    """Loading a real book shows its metadata and starts on page one."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)

    loaded = screen.load_book(1)

    assert loaded is True
    assert screen._title_label.text() == "Book of Fiqh"
    assert screen._author_label.text() == "Author One"
    assert screen._content_label.text() == "First page content"
    assert screen._page_input.text() == "1"
    assert screen._page_count_label.text() == "/ 3"
    assert not screen._prev_button.isEnabled()
    assert screen._next_button.isEnabled()


def test_load_book_returns_false_for_unknown_book(qtbot, tmp_path: Path) -> None:
    """Requesting a nonexistent book id returns False instead of raising."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)

    assert screen.load_book(9999) is False


def test_next_and_previous_navigate_between_real_pages(qtbot, tmp_path: Path) -> None:
    """Prev/Next move through the real page content in order."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen._go_next()
    assert screen._content_label.text() == "Second page content"
    assert screen._prev_button.isEnabled()

    screen._go_next()
    assert screen._content_label.text() == "Third page content"
    assert not screen._next_button.isEnabled()

    screen._go_previous()
    assert screen._content_label.text() == "Second page content"


def test_jump_to_page_number_finds_the_matching_page(qtbot, tmp_path: Path) -> None:
    """Jumping to a specific real page number shows that page's content."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen.jump_to_page_number(3)

    assert screen._content_label.text() == "Third page content"
    assert screen._page_input.text() == "3"


def test_font_size_controls_change_the_stylesheet(qtbot, tmp_path: Path) -> None:
    """A+ and A- change the applied font size within its bounds."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1)

    starting_size = screen._font_px
    screen._change_font_size(1.5)
    assert screen._font_px == starting_size + 1.5
    assert f"font-size: {screen._font_px}px" in screen._content_label.styleSheet()


def test_font_family_choice_defaults_to_jameel_noori_nastaleeq(qtbot, tmp_path: Path) -> None:
    """With no persisted choice, the reading font defaults to Jameel Noori Nastaleeq -
    the widely-installed real redistribution, not the rarer "Noori Nastaleeq" name."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)

    assert screen.selected_font_family() == "Jameel Noori Nastaleeq"
    assert "font-family" in screen._content_label.styleSheet()


def test_font_family_dropdown_changes_the_applied_font(qtbot, tmp_path: Path) -> None:
    """Picking a different font from the dropdown updates the page content's font-family.

    Picks a font not offered as a first choice in any FONT_CHOICES stack
    (Sakkal Majalla) that's also genuinely installed on this machine, so
    the resolved, rendered family name is real and stable to assert on -
    unlike a font that may not be installed everywhere (see
    reading_fonts.resolve_installed_font_family).
    """
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen._font_family_combo.setCurrentText("Sakkal Majalla")

    assert screen.selected_font_family() == "Sakkal Majalla"
    assert "font-family" in screen._content_label.styleSheet()


def test_initial_font_family_is_honored(qtbot, tmp_path: Path) -> None:
    """A persisted default reading font is applied from construction, not just the built-in default."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, initial_font_family="Scheherazade New")
    qtbot.addWidget(screen)

    assert screen.selected_font_family() == "Scheherazade New"
    assert screen._font_family_combo.currentText() == "Scheherazade New"
