"""Tests for the desktop app's Viewer screen, wired to a real master database."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Chapter, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.viewer_screen import (  # noqa: E402
    MAX_READING_COLUMN_WIDTH,
    ViewerScreen,
)


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


def test_reading_content_is_capped_to_a_real_column_width(qtbot, tmp_path: Path) -> None:
    """Reader Redesign fix: text no longer fills the whole width of a wide
    monitor - a real, enforced max-width reading column, matching Acrobat/
    Zotero, instead of unconstrained full-bleed text."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)

    assert screen._content_label.maximumWidth() == MAX_READING_COLUMN_WIDTH


def test_load_book_populates_the_real_table_of_contents(qtbot, tmp_path: Path) -> None:
    """Reader Redesign: a real, browsable TOC panel, not just page-by-page
    navigation - reads the existing Chapters table for real."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book With Chapters"},
        categories=(),
        table_of_contents=(
            Chapter(title_id=1, title="Introduction", page_number=1, parent_id=None, sort_key=0),
            Chapter(title_id=2, title="Chapter One", page_number=2, parent_id=None, sort_key=1),
        ),
        pages=(Page(1, 1, "Intro content", "Plain"), Page(2, 2, "Chapter content", "Plain")),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)

    screen.load_book(1)

    assert screen._toc_tree.topLevelItemCount() == 2
    assert screen._toc_tree.topLevelItem(1).text(0) == "Chapter One"


def test_toc_tree_uses_rtl_layout_for_real_chapter_titles(qtbot, tmp_path: Path) -> None:
    """Typography fix: real Arabic/Urdu chapter titles need RTL layout
    direction, matching every other title tree/row in the app."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book With Chapters"},
        categories=(),
        table_of_contents=(
            Chapter(title_id=1, title="Introduction", page_number=1, parent_id=None, sort_key=0),
        ),
        pages=(Page(1, 1, "Intro content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)

    screen.load_book(1)

    assert screen._toc_tree.layoutDirection() == Qt.LayoutDirection.RightToLeft


def test_clicking_a_toc_item_jumps_to_its_page(qtbot, tmp_path: Path) -> None:
    """A real click on a TOC entry navigates the reader to that chapter's page."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book With Chapters"},
        categories=(),
        table_of_contents=(
            Chapter(title_id=1, title="Chapter Two", page_number=2, parent_id=None, sort_key=0),
        ),
        pages=(Page(1, 1, "First", "Plain"), Page(2, 2, "Second", "Plain")),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1)

    item = screen._toc_tree.topLevelItem(0)
    screen._on_toc_item_clicked(item, 0)

    assert screen._content_label.text() == "Second"


def test_bookmarking_a_page_adds_it_to_the_bookmarks_list(qtbot, tmp_path: Path) -> None:
    """Reader Redesign: bookmarks are now a real, browsable list, not just a
    per-page toggle - reflects live as pages are bookmarked."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen.toggle_bookmark()

    assert screen._bookmarks_list.count() == 1
    assert screen._bookmarks_list.item(0).text() == "Page 1"


def test_clicking_a_bookmark_jumps_to_its_page(qtbot, tmp_path: Path) -> None:
    """A real click on a bookmark entry navigates to that page."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1, bookmarked_pages={3})

    item = screen._bookmarks_list.item(0)
    screen._on_bookmark_item_clicked(item)

    assert screen._content_label.text() == "Third page content"


def test_copy_citation_puts_a_real_citation_on_the_clipboard(qtbot, tmp_path: Path) -> None:
    """Copy Citation uses the existing format_citation() with real, already-
    loaded data (title, current page) - no new backend needed."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1)
    screen.jump_to_page_number(2)

    screen.copy_citation()

    assert QGuiApplication.clipboard().text() == "Book Book of Fiqh, Page 2, Paragraph 1"


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


class _FakeTtsSpeaker:
    """Speaker returning a real, tiny, silent-but-valid waveform - real
    enough to become a real playable WAV file, without a real model."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.last_text: str | None = None

    def synthesize(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
        if self.fail:
            raise RuntimeError("synthesis failed")
        self.last_text = text
        return (0.0, 0.1, 0.0, -0.1) * 50, 8000


def _install_fake_tts(screen: "ViewerScreen", fail: bool = False) -> _FakeTtsSpeaker:
    """Inject a fake speaker in place of the real MmsTtsSpeaker, mirroring
    how test_search_screen.py monkeypatches _build_real_semantic_search_service
    to avoid a real model load in the widget test suite."""
    from islamic_research_hub.application.page_narration import PageNarrationService

    speaker = _FakeTtsSpeaker(fail=fail)
    screen._build_real_tts_narration_service = lambda: (
        None if fail else PageNarrationService(speaker)
    )
    return speaker


def test_play_button_hidden_when_tts_disabled_by_default(qtbot, tmp_path: Path) -> None:
    """Without enable_lazy_tts, the play button doesn't even show - a dead
    control offering a feature that's off is worse than no control.

    isHidden() reflects the widget's own explicit visibility flag
    regardless of whether the top-level window is actually on-screen -
    unlike isVisible(), which also depends on the whole ancestor chain
    being shown, unreliable in a headless test (see test_search_screen.py).
    """
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)

    assert screen._play_pause_button.isHidden() is True


def test_play_button_visible_when_tts_enabled(qtbot, tmp_path: Path) -> None:
    """With enable_lazy_tts=True (the real Settings-toggle-on case), the
    button shows."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, enable_lazy_tts=True)
    qtbot.addWidget(screen)

    assert screen._play_pause_button.isHidden() is False


def test_lazy_tts_is_not_attempted_by_default(qtbot, tmp_path: Path) -> None:
    """Without enable_lazy_tts, no real service is ever built - real model
    loading is opt-in, never a side effect of opening a book."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path)
    qtbot.addWidget(screen)
    screen.load_book(1)
    build_calls = []
    screen._build_real_tts_narration_service = lambda: (build_calls.append(1), None)[1]

    screen._start_narration()

    assert build_calls == []


def test_clicking_play_synthesizes_and_writes_a_real_wav_file(qtbot, tmp_path: Path) -> None:
    """Clicking Play, with a fake (fast) speaker standing in for the real
    model, reaches a real playable WAV file and flips the icon to pause."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    speaker = _install_fake_tts(screen)

    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert speaker.last_text == "First page content"
    assert screen._tts_wav_path is not None
    assert Path(screen._tts_wav_path).is_file()
    assert screen._play_pause_button.isEnabled()


def test_turning_the_page_while_playing_stops_and_cleans_up(qtbot, tmp_path: Path) -> None:
    """Real bug this guards against: turning the page mid-playback used to
    have no cleanup path at all - the toolbar's page-change funnel
    (_render_current_page) now stops playback and removes the temp WAV."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_tts(screen)
    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)
    wav_path = Path(screen._tts_wav_path)
    assert wav_path.is_file()

    screen._go_next()

    assert screen._tts_wav_path is None
    assert not wav_path.is_file()


def test_narration_failure_resets_the_button_without_crashing(qtbot, tmp_path: Path) -> None:
    """A build failure (e.g. the optional "tts" extra isn't installed) must
    degrade gracefully - reading/navigation keeps working unaffected."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_tts(screen, fail=True)

    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert screen._play_pause_button.isEnabled()
    assert screen._tts_wav_path is None
    # The screen itself is still fully usable - real navigation still works.
    screen._go_next()
    assert screen._content_label.text() == "Second page content"
