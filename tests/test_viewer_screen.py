"""Tests for the desktop app's Viewer screen, wired to a real master database."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Chapter, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.icons import (  # noqa: E402
    button_icon,
    button_icon_size,
)
from islamic_research_hub.interfaces.desktop_app.viewer_screen import (  # noqa: E402
    MAX_READING_COLUMN_WIDTH,
    ViewerScreen,
)
from islamic_research_hub.research_notes.research_notes_manager import (  # noqa: E402
    ResearchNotesManager,
)


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


class _NoOpNotesStorage:
    """Finds nothing, real or fake - the default stand-in for every test
    in this file (see `_no_real_research_notes_lookup` below)."""

    def find_documents_mentioning(self, book_title: str) -> tuple:
        return ()


@pytest.fixture(autouse=True)
def _no_real_research_notes_lookup(monkeypatch, tmp_path: Path):
    """`load_book()` always calls `_reload_research_notes_list()`, which
    by default would construct a real `ResearchNotesManager` - touching
    the real Documents folder and the real Windows-registry-backed
    `QSettings` on every single test in this file. This project already
    hit exactly that kind of real-registry pollution once before (a
    stray `language=ur` value leaked into the real registry from tests -
    see CHANGELOG) - autouse-patched here so no test in this file can
    repeat it by accident. Tests that specifically want to exercise real
    (fake-storage-backed) lookups override this patch again themselves.
    """
    isolated_settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        ViewerScreen,
        "_build_research_notes_manager",
        lambda self: ResearchNotesManager(_NoOpNotesStorage(), isolated_settings),
    )


def _icon_matches(button, name: str) -> bool:
    """`button_icon()` builds a fresh QIcon/QPixmap every call (not cached),
    so QIcon.cacheKey() is never equal across two logically-identical
    icons - compare rendered pixel content instead."""
    size = button_icon_size()
    return button.icon().pixmap(size).toImage() == button_icon(name).pixmap(size).toImage()


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
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen.toggle_bookmark()

    assert screen._bookmarks_list.count() == 1
    assert screen._bookmarks_list.item(0).text() == "Book of Fiqh, Page 1"


def test_clicking_a_bookmark_jumps_to_its_page(qtbot, tmp_path: Path) -> None:
    """A real click on a bookmark entry navigates to that page."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)
    screen.jump_to_page_number(2)

    screen.copy_citation()

    assert QGuiApplication.clipboard().text() == "Book Book of Fiqh, Page 2, Paragraph 1"


def test_load_book_returns_false_for_unknown_book(qtbot, tmp_path: Path) -> None:
    """Requesting a nonexistent book id returns False instead of raising."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen.load_book(9999) is False


def test_next_and_previous_navigate_between_real_pages(qtbot, tmp_path: Path) -> None:
    """Prev/Next move through the real page content in order."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen.jump_to_page_number(3)

    assert screen._content_label.text() == "Third page content"
    assert screen._page_input.text() == "3"


def test_font_size_controls_change_the_stylesheet(qtbot, tmp_path: Path) -> None:
    """A+ and A- change the applied font size within its bounds."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen._font_family_combo.setCurrentText("Sakkal Majalla")

    assert screen.selected_font_family() == "Sakkal Majalla"
    assert "font-family" in screen._content_label.styleSheet()


def test_initial_font_family_is_honored(qtbot, tmp_path: Path) -> None:
    """A persisted default reading font is applied from construction, not just the built-in default."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), initial_font_family="Scheherazade New")
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
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._play_pause_button.isHidden() is True


def test_play_button_visible_when_tts_enabled(qtbot, tmp_path: Path) -> None:
    """With enable_lazy_tts=True (the real Settings-toggle-on case), the
    button shows."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)

    assert screen._play_pause_button.isHidden() is False


def test_extract_events_button_hidden_when_ai_agent_disabled_by_default(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._extract_events_button.isHidden() is True


def test_extract_events_button_visible_when_ai_agent_enabled(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_ai_agent=True)
    qtbot.addWidget(screen)

    assert screen._extract_events_button.isHidden() is False


def test_extract_events_button_emits_the_current_book_id(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_ai_agent=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    received = []
    screen.extract_events_requested.connect(received.append)

    screen._extract_events_button.click()

    assert received == [1]


def test_extract_events_button_does_nothing_with_no_book_loaded(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_ai_agent=True)
    qtbot.addWidget(screen)
    received = []
    screen.extract_events_requested.connect(received.append)

    screen._on_extract_events_clicked()

    assert received == []


def test_extract_narrators_button_hidden_when_ai_agent_disabled_by_default(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._extract_narrators_button.isHidden() is True


def test_extract_narrators_button_visible_when_ai_agent_enabled(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_ai_agent=True)
    qtbot.addWidget(screen)

    assert screen._extract_narrators_button.isHidden() is False


def test_extract_narrators_button_emits_the_current_book_id(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_ai_agent=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    received = []
    screen.extract_narrators_requested.connect(received.append)

    screen._extract_narrators_button.click()

    assert received == [1]


def test_extract_narrators_button_does_nothing_with_no_book_loaded(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_ai_agent=True)
    qtbot.addWidget(screen)
    received = []
    screen.extract_narrators_requested.connect(received.append)

    screen._on_extract_narrators_clicked()

    assert received == []


def test_lazy_tts_is_not_attempted_by_default(qtbot, tmp_path: Path) -> None:
    """Without enable_lazy_tts, no real service is ever built - real model
    loading is opt-in, never a side effect of opening a book."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
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
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    speaker = _install_fake_tts(screen)

    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert speaker.last_text == "First page content"
    assert screen._tts_chunk_paths
    assert Path(screen._tts_chunk_paths[0][0]).is_file()
    assert screen._play_pause_button.isEnabled()


def test_volume_slider_sets_real_audio_output_volume(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)

    screen._tts_volume_slider.setValue(40)

    assert screen._tts_audio_output.volume() == pytest.approx(0.4)


def test_speed_combo_sets_real_media_player_playback_rate(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)

    index_1_5x = screen._tts_speed_combo.findText("1.5x")
    screen._tts_speed_combo.setCurrentIndex(index_1_5x)

    assert screen._media_player.playbackRate() == pytest.approx(1.5)


def test_auto_continue_checked_advances_to_next_page_and_keeps_reading(
    qtbot, tmp_path: Path
) -> None:
    """"Keep reading until I pause it" - the real reported behavior:
    finishing one page's real narration, with auto-continue on, must
    advance the page and start a fresh narration for it, not just stop."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    speaker = _install_fake_tts(screen)
    screen._tts_auto_continue_checkbox.setChecked(True)

    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    screen._finish_narration_playback()

    assert screen._current_index == 1
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    assert speaker.last_text == "Second page content"


def test_auto_continue_unchecked_stops_at_the_end_of_the_page(qtbot, tmp_path: Path) -> None:
    """Regression guard: auto-continue is opt-in - the existing single-page
    stop behavior must be unchanged when the box isn't checked."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_tts(screen)
    assert screen._tts_auto_continue_checkbox.isChecked() is False

    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    screen._finish_narration_playback()

    assert screen._current_index == 0
    assert _icon_matches(screen._play_pause_button, "play")


def _seed_database_with_language(database_path: Path, language: str) -> None:
    """Import one real, single-page book with a real recorded language -
    the translation context-menu item only ever offers itself for a book
    whose language is one Milestone 1 actually supports."""
    book = Book(
        information={"Name": "Arabic Book", "Language": language},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "النص العربي", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


class _FakeTranslator:
    """Translator returning a fixed string, recording what it was asked
    to translate - mirrors `_FakeTtsSpeaker`'s shape."""

    def __init__(self, raise_on_translate: bool = False) -> None:
        self.raise_on_translate = raise_on_translate
        self.last_text: str | None = None
        self.last_source_language: str | None = None

    def translate_to_english(self, text: str, source_language: str) -> str:
        if self.raise_on_translate:
            raise RuntimeError("translation failed")
        self.last_text = text
        self.last_source_language = source_language
        return f"[EN] {text}"


def _install_fake_translation(
    screen: "ViewerScreen", unavailable: bool = False, raise_on_translate: bool = False
) -> _FakeTranslator:
    """Inject a fake translator in place of the real MarianTranslator,
    mirroring `_install_fake_tts`."""
    from islamic_research_hub.application.text_translation import PageTranslationService

    fake = _FakeTranslator(raise_on_translate=raise_on_translate)
    screen._build_real_translation_service = lambda: (
        None if unavailable else PageTranslationService(fake)
    )
    return fake


def test_translate_menu_item_offered_for_a_supported_language_when_enabled(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_language(database_path, "Arabic")
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_translation=True)
    qtbot.addWidget(screen)
    screen.load_book(1)

    assert screen._translation_offered() is True


def test_translate_menu_item_hidden_when_translation_disabled(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_language(database_path, "Arabic")
    screen = ViewerScreen(database_path, _translator(tmp_path))  # enable_lazy_translation defaults False
    qtbot.addWidget(screen)
    screen.load_book(1)

    assert screen._translation_offered() is False


def test_translate_menu_item_hidden_for_an_unsupported_language(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_language(database_path, "English")
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_translation=True)
    qtbot.addWidget(screen)
    screen.load_book(1)

    assert screen._translation_offered() is False


def test_explain_action_emits_the_real_selected_text(qtbot, tmp_path: Path) -> None:
    """Phase 13 Milestone 1: "Explain this passage" routes up to
    MainWindow (which owns the real AI Agent service), not handled
    locally like TTS/translation - this screen just emits the signal
    with the real selected text."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_ai_agent=True)
    qtbot.addWidget(screen)
    screen.load_book(1)

    received = []
    screen.explain_selection_requested.connect(received.append)
    screen._handle_context_menu_action("explain", "a real selected passage")

    assert received == ["a real selected passage"]


def test_show_explanation_opens_a_real_dialog_with_save_to_notes(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    import islamic_research_hub.interfaces.desktop_app.viewer_screen as viewer_screen_module

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_ai_agent=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    calls = []
    monkeypatch.setattr(
        viewer_screen_module,
        "_show_explanation_dialog",
        lambda *args: calls.append(args),
    )

    screen.show_explanation("a real passage", "a real explanation")

    assert len(calls) == 1
    _parent, _translator_arg, passage, explanation, on_save = calls[0]
    assert passage == "a real passage"
    assert explanation == "a real explanation"

    # The dialog's own Save-to-Notes button calls back with the
    # explanation text - confirm it wires to the real, currently-open
    # book/page via show_save_to_notes_dialog, same as the existing
    # Save to Research Notes context-menu action.
    notes_calls = []
    monkeypatch.setattr(
        viewer_screen_module,
        "show_save_to_notes_dialog",
        lambda *args: notes_calls.append(args),
    )
    on_save("a real explanation")

    assert len(notes_calls) == 1
    _parent, _browser, book_id, title, page_number, saved_text = notes_calls[0]
    assert book_id == 1
    assert title == "Book of Fiqh"
    assert page_number == 1
    assert saved_text == "a real explanation"


def test_translating_a_selection_shows_a_real_translation_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    import islamic_research_hub.interfaces.desktop_app.viewer_screen as viewer_screen_module

    database_path = tmp_path / "books.db"
    _seed_database_with_language(database_path, "Arabic")
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_translation=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    fake = _install_fake_translation(screen)
    calls = []
    monkeypatch.setattr(
        viewer_screen_module,
        "_show_translation_dialog",
        lambda *args: calls.append(args),
    )

    screen._handle_context_menu_action("translate", "بسم الله")
    with qtbot.waitSignal(screen._translation_worker.finished, timeout=5000):
        pass

    assert fake.last_text == "بسم الله"
    assert fake.last_source_language == "Arabic"
    assert len(calls) == 1
    _parent, _translator_arg, original, translated = calls[0]
    assert original == "بسم الله"
    assert translated == "[EN] بسم الله"


def test_translation_unavailable_shows_a_warning_not_a_crash(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database_with_language(database_path, "Arabic")
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_translation=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_translation(screen, unavailable=True)

    warnings = []
    screen._on_translation_unavailable = lambda key: warnings.append(key)
    screen._handle_context_menu_action("translate", "بسم الله")
    with qtbot.waitSignal(screen._translation_worker.finished, timeout=5000):
        pass

    assert len(warnings) == 1


def test_turning_the_page_while_playing_stops_and_cleans_up(qtbot, tmp_path: Path) -> None:
    """Real bug this guards against: turning the page mid-playback used to
    have no cleanup path at all - the toolbar's page-change funnel
    (_render_current_page) now stops playback and removes the temp WAV(s)."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_tts(screen)
    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)
    chunk_dir = screen._tts_chunk_dir
    wav_paths = [Path(path) for path, _ in screen._tts_chunk_paths]
    assert wav_paths
    assert all(path.is_file() for path in wav_paths)

    screen._go_next()

    assert screen._tts_chunk_dir is None
    assert screen._tts_chunk_paths == []
    assert all(not path.is_file() for path in wav_paths)
    assert not chunk_dir.exists()


def test_narration_failure_resets_the_button_without_crashing(qtbot, tmp_path: Path) -> None:
    """A build failure (e.g. the optional "tts" extra isn't installed) must
    degrade gracefully - reading/navigation keeps working unaffected."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_tts(screen, fail=True)

    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert screen._play_pause_button.isEnabled()
    assert screen._tts_chunk_paths == []
    # The screen itself is still fully usable - real navigation still works.
    screen._go_next()
    assert screen._content_label.text() == "Second page content"


def _seed_database_with_long_page(database_path: Path) -> None:
    """One page with real sentence structure long enough (>320 chars, the
    default chunk cap) to split into multiple real TTS chunks - needed to
    exercise auto-advance/streaming playback at all."""
    sentence = "This is a real sentence with several words in it."
    long_page_text = " ".join([sentence] * 10)  # ~530 chars, several chunks at the default cap
    book = Book(
        information={"Name": "Book of Long Pages", "ANAME": "Author Two"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, long_page_text, "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_multi_chunk_playback_auto_advances_and_resets_icon_on_completion(
    qtbot, tmp_path: Path
) -> None:
    """Real streaming behavior: chunk 1 plays while later chunks are still
    synthesizing; EndOfMedia advances to the next chunk automatically; the
    icon resets to "play" only once the true last chunk finishes."""
    from PySide6.QtMultimedia import QMediaPlayer

    database_path = tmp_path / "books.db"
    _seed_database_with_long_page(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_tts(screen)

    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass

    total_chunks = len(screen._tts_chunk_paths)
    assert total_chunks > 1
    assert screen._tts_next_play_index == 1  # chunk 0 already playing

    # Real playback duration can't practically be waited out headless -
    # directly invoking the status-changed handler is the chosen technique
    # to simulate each chunk finishing. No qtbot.wait() here on purpose:
    # a real bug found running this suite under system load - the fake
    # chunk's audio is only ~30ms long, and even a 50ms wait gave it
    # enough real wall-clock time to actually finish playing and
    # auto-advance for real, racing this assertion. queued Qt signals
    # emitted before worker.finished are already delivered by the time
    # waitSignal(finished) returns, so no extra wait is needed.
    for _ in range(total_chunks - 1):
        screen._on_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)
    assert screen._tts_next_play_index == total_chunks
    assert _icon_matches(screen._play_pause_button, "pause")

    screen._on_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)  # final chunk ends

    assert _icon_matches(screen._play_pause_button, "play")


def test_late_arriving_chunk_plays_immediately_once_awaiting(qtbot, tmp_path: Path) -> None:
    """Playback can catch up with synthesis (chunk N ends before chunk N+1
    has finished synthesizing) - the next chunk must auto-play the instant
    it arrives, with no extra user action required."""
    from PySide6.QtMultimedia import QMediaPlayer

    database_path = tmp_path / "books.db"
    _seed_database_with_long_page(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_tts(screen)

    # Simulate "caught up": one chunk queued and already played, nothing
    # else queued yet, more chunks still expected.
    screen._reset_narration_playback_state()
    screen._tts_chunk_paths = [("chunk0.wav", False)]
    screen._tts_next_play_index = 1
    screen._tts_is_last_chunk_playing = False
    screen._on_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)
    assert screen._tts_awaiting_next_chunk is True

    played_paths: list[str] = []
    screen._media_player.setSource = lambda url: played_paths.append(url.toLocalFile())
    screen._media_player.play = lambda: None
    screen._on_chunk_ready("chunk1.wav", 1, True, screen._current_narration_key())

    assert screen._tts_awaiting_next_chunk is False
    assert played_paths == ["chunk1.wav"]


def test_pausing_while_awaiting_next_chunk_does_not_start_a_new_narration(
    qtbot, tmp_path: Path
) -> None:
    """Regression test: QMediaPlayer.playbackState() is StoppedState once
    EndOfMedia fires, so the play/pause handler's ordinary fallback would
    otherwise wrongly spin up a second, redundant TtsWorker while the
    first is still producing chunks in the background."""
    database_path = tmp_path / "books.db"
    _seed_database_with_long_page(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)
    _install_fake_tts(screen)
    screen._tts_awaiting_next_chunk = True
    start_calls = []
    screen._start_narration = lambda: start_calls.append(1)

    screen._on_play_pause_clicked()  # pause during the gap

    assert screen._tts_paused_while_waiting is True
    assert start_calls == []

    screen._on_play_pause_clicked()  # resume

    assert screen._tts_paused_while_waiting is False
    assert start_calls == []


def test_partial_chunk_failure_still_plays_earlier_chunks(qtbot, tmp_path: Path) -> None:
    """A later chunk failing (e.g. the 2nd of several) must not discard the
    real CPU already spent on earlier chunks - they still play, and the
    button resets normally once the last available chunk finishes."""
    from PySide6.QtMultimedia import QMediaPlayer

    database_path = tmp_path / "books.db"
    _seed_database_with_long_page(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path), enable_lazy_tts=True)
    qtbot.addWidget(screen)
    screen.load_book(1)

    class _FailOnSecondCall:
        def __init__(self) -> None:
            self.calls = 0

        def synthesize(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("synthesis failed")
            return (0.0, 0.1, 0.0, -0.1) * 50, 8000

    from islamic_research_hub.application.page_narration import PageNarrationService

    speaker = _FailOnSecondCall()
    screen._build_real_tts_narration_service = lambda: PageNarrationService(speaker)

    screen._on_play_pause_clicked()
    with qtbot.waitSignal(screen._tts_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert len(screen._tts_chunk_paths) == 1
    # narration_failed is only emitted when chunk 0 itself fails - a later
    # chunk failing must not trigger the "Text-to-speech unavailable" reset.
    assert screen._play_pause_button.toolTip() != "Text-to-speech unavailable"

    screen._on_media_status_changed(QMediaPlayer.MediaStatus.EndOfMedia)

    assert _icon_matches(screen._play_pause_button, "play")


def test_page_content_strips_raw_structural_markup_before_display(
    qtbot, tmp_path: Path
) -> None:
    """Real bug reported directly against the running app: ~471,000 real
    pages (mostly Maktaba Jibreel) carry raw markup like
    '<urh1>...</urh1>' - already stripped for narration
    (PageNarrationService) but never for the on-screen reader text itself
    until now."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book with markup"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "<urh1>A real heading</urh1> Body text follows", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen.load_book(1)

    assert "<" not in screen._content_label.text()
    assert ">" not in screen._content_label.text()
    assert "A real heading" in screen._content_label.text()
    assert "Body text follows" in screen._content_label.text()


def test_toolbar_controls_stay_a_real_size_when_the_reader_is_narrow(
    qtbot, tmp_path: Path
) -> None:
    """Real bug found via manual use: the toolbar's own natural width
    (~1024px) exceeds the reader pane's real floor (320px) - controls
    marked `Ignored` (font combo, Contents/Copy Citation buttons) used to
    get squeezed toward 0px under that pressure, reading as "vanished"
    rather than just scrolled out of view. Fixed by wrapping the toolbar
    in its own horizontal-scrolling area and dropping the `Ignored`
    policy - every control now keeps its real, non-zero size."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)
    screen.resize(320, 600)
    screen.show()
    qtbot.waitExposed(screen)

    assert screen._font_family_combo.width() > 0
    assert screen._contents_button.width() > 0
    assert screen._copy_citation_button.width() > 0


def test_context_menu_copy_puts_selected_text_on_the_clipboard(qtbot, tmp_path: Path) -> None:
    """`_handle_context_menu_action` is the directly-callable, test-friendly
    seam - a real QMenu popup has no place in a headless test, so these
    tests call it with a synthetic selection instead of driving a real
    right-click menu."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen._handle_context_menu_action("copy", "some selected text")

    assert QGuiApplication.clipboard().text() == "some selected text"


def test_context_menu_copy_with_citation_includes_the_real_citation(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)
    screen.jump_to_page_number(2)

    screen._handle_context_menu_action("copy_citation", "a quoted passage")

    clipboard_text = QGuiApplication.clipboard().text()
    assert "a quoted passage" in clipboard_text
    assert "Book Book of Fiqh, Page 2, Paragraph 1" in clipboard_text


def test_context_menu_save_notes_opens_the_dialog_with_real_context(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Save to Research Notes hands the dialog the real, currently-loaded
    book/page context - no new backend needed, same data Copy Citation
    already uses."""
    import islamic_research_hub.interfaces.desktop_app.viewer_screen as viewer_screen_module

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)
    screen.jump_to_page_number(2)
    calls = []
    monkeypatch.setattr(
        viewer_screen_module,
        "show_save_to_notes_dialog",
        lambda *args: calls.append(args),
    )

    screen._handle_context_menu_action("save_notes", "a quoted passage")

    assert len(calls) == 1
    parent, browser, book_id, title, page_number, selected_text = calls[0]
    assert parent is screen
    assert browser is screen._browser
    assert book_id == 1
    assert title == "Book of Fiqh"
    assert page_number == 2
    assert selected_text == "a quoted passage"


def test_context_menu_open_notes_calls_the_real_entry_point(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    import islamic_research_hub.interfaces.desktop_app.viewer_screen as viewer_screen_module

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)
    calls = []
    monkeypatch.setattr(
        viewer_screen_module, "open_current_notes", lambda parent: calls.append(parent)
    )

    screen._handle_context_menu_action("open_notes", "")

    assert calls == [screen]


def test_toc_shows_a_real_empty_state_when_the_book_has_no_chapters(
    qtbot, tmp_path: Path
) -> None:
    """UI Polish Pass 2: a book with no digitized table of contents shows
    a real message instead of a blank white box."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen.load_book(1)

    assert screen._toc_tree.topLevelItemCount() == 1
    assert "No table of contents" in screen._toc_tree.topLevelItem(0).text(0)


def test_bookmarks_panel_shows_a_real_empty_state_when_there_are_none(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen.load_book(1)

    assert screen._bookmarks_list.count() == 1
    assert "No bookmarks" in screen._bookmarks_list.item(0).text()


def test_bookmarking_a_page_replaces_the_bookmarks_empty_state(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)

    screen.toggle_bookmark()

    assert screen._bookmarks_list.count() == 1
    assert screen._bookmarks_list.item(0).text() == "Book of Fiqh, Page 1"


def test_nav_panel_maximize_grows_it_and_shrinks_the_reader(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.resize(1000, 600)
    screen.load_book(1)
    initial_nav_width = screen._body_splitter.sizes()[0]

    screen._on_nav_maximize_clicked()

    assert screen._nav_panel_toggle.is_maximized is True
    assert screen._body_splitter.sizes()[0] > initial_nav_width

    screen._on_nav_maximize_clicked()

    assert screen._nav_panel_toggle.is_maximized is False
    assert screen._body_splitter.sizes()[0] == initial_nav_width


def test_nav_panel_maximize_expands_it_first_if_collapsed(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.resize(1000, 600)
    screen.load_book(1)
    screen._contents_button.setChecked(False)
    screen._nav_panel_animation.setCurrentTime(1000)
    assert screen._body_splitter.sizes()[0] < 10

    screen._on_nav_maximize_clicked()

    assert screen._contents_button.isChecked() is True
    assert screen._body_splitter.sizes()[0] > 100


def test_bookmark_row_includes_volume_when_the_book_has_one(qtbot, tmp_path: Path) -> None:
    """Real bug reported directly: bookmarks used to show only "Page N" -
    now shows the full citation-style detail (book title, volume if
    real, page)."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)
    screen._current_volume_number = 3  # a real multi-volume series' detected volume

    screen.toggle_bookmark()

    assert screen._bookmarks_list.item(0).text() == "Book of Fiqh, Volume 3, Page 1"


def test_research_notes_list_shows_a_real_empty_state_by_default(
    qtbot, tmp_path: Path
) -> None:
    """No research notes exist for a freshly-opened book - a real message,
    not a blank box. Relies on this file's autouse no-op storage fixture,
    same as every other test that calls load_book()."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen.load_book(1)

    assert screen._research_notes_list.count() == 1
    assert "No research notes" in screen._research_notes_list.item(0).text()


def test_research_notes_list_shows_a_real_matching_document(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """A document with a quotation saved from this book shows up in the
    reader's own Research Notes list."""
    from PySide6.QtCore import QSettings

    from islamic_research_hub.research_notes.research_notes_manager import ResearchNotesManager

    class _FakeStorage:
        def find_documents_mentioning(self, book_title: str) -> tuple:
            return (Path("/fake/Fiqh Research.docx"),) if book_title == "Book of Fiqh" else ()

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    isolated_settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr(
        screen,
        "_build_research_notes_manager",
        lambda: ResearchNotesManager(_FakeStorage(), isolated_settings),
    )

    screen.load_book(1)

    assert screen._research_notes_list.count() == 1
    assert screen._research_notes_list.item(0).text() == "Fiqh Research"


def test_clicking_a_research_notes_item_opens_it(qtbot, tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ViewerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen.load_book(1)
    from PySide6.QtWidgets import QListWidgetItem

    item = QListWidgetItem("Fiqh Research")
    item.setData(Qt.ItemDataRole.UserRole, Path("/fake/Fiqh Research.docx"))
    opened = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.viewer_screen.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()),
    )

    screen._on_research_notes_item_clicked(item)

    assert len(opened) == 1
    assert Path(opened[0]) == Path("/fake/Fiqh Research.docx")


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    """Toolbar, nav-panel headings, bookmarks list, and the current page's
    own empty-content placeholder all re-render in the new language."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    translator = _translator(tmp_path)
    screen = ViewerScreen(database_path, translator)
    qtbot.addWidget(screen)
    screen.load_book(1)
    screen.toggle_bookmark()
    assert screen._contents_button.text() == "Contents"
    assert screen._copy_citation_button.text() == "Copy citation"
    assert screen._bookmark_button.text() == "★ Bookmarked"

    translator.set_language("ur")

    assert screen._contents_button.text() == "مشمولات"
    assert screen._copy_citation_button.text() == "حوالہ کاپی کریں"
    assert screen._bookmarks_heading_label.text() == "نشانیاں"
    assert screen._research_notes_heading_label.text() == "ریسرچ نوٹس"
    assert screen._bookmark_button.text() == "★ نشان زد شدہ"
    assert "صفحہ" in screen._bookmarks_list.item(0).text()
