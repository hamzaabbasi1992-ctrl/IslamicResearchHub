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
from islamic_research_hub.infrastructure.persistence.pdf_match_candidate_repository import (  # noqa: E402
    PdfMatchCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.main_window import (  # noqa: E402
    MainWindow,
    _RAIL_GROUPS,
    _RAIL_KEYS,
    _rail_group_index_for,
)

# A hand-crafted minimal one-page PDF - real-world PDFs always have a correct
# xref table, but Qt's QPdfDocument parses this looser form fine, and it
# avoids depending on a third-party PDF-writing library just for a test.
_MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"%%EOF"
)


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


def test_main_window_constructs_with_home_screen_active(qtbot, tmp_path: Path) -> None:
    """The window opens on the new Home dashboard screen without raising."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    assert window.windowTitle() == "Islamic Research Hub"
    assert window._stack.currentIndex() == 0


def test_ai_quick_ask_expands_the_panel_and_forwards_the_question(
    qtbot, tmp_path: Path
) -> None:
    """The Search screen's quick-ask box reuses the real AI panel's own
    ask() rather than duplicating its lazy-build/pre-flight logic -
    expands the panel if collapsed, then asks the real question there."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    window._ai_panel.set_collapsed(True)
    asked = []
    window._ai_panel.ask = asked.append

    window._on_ai_quick_ask_requested("What does this library say about patience?")

    assert window._ai_panel.is_collapsed is False
    assert asked == ["What does this library say about patience?"]


def test_rail_buttons_switch_the_visible_screen(qtbot, tmp_path: Path) -> None:
    """Clicking a rail button switches the stacked screen and its checked state."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    libraries_button = window._rail_buttons[2]
    qtbot.mouseClick(libraries_button, Qt.MouseButton.LeftButton)

    assert window._stack.currentIndex() == 2
    assert libraries_button.isChecked()
    assert not window._rail_buttons[0].isChecked()


def test_rail_group_index_for_finds_the_right_group() -> None:
    assert _rail_group_index_for(0) == 0  # Home -> Browse
    assert _rail_group_index_for(11) == 2  # Flashcards -> Study
    assert _rail_group_index_for(14) == 3  # Settings -> System


def test_every_real_rail_key_belongs_to_exactly_one_group() -> None:
    """Real safety guard: a rail entry silently missing from every group
    would be unreachable via _show_screen's auto-group-switch."""
    covered = [index for _key, member_indices in _RAIL_GROUPS for index in member_indices]

    assert sorted(covered) == list(range(len(_RAIL_KEYS)))


def test_rail_starts_with_only_the_browse_group_visible(qtbot, tmp_path: Path) -> None:
    """Real fix for 15 rail entries no longer fitting one column: grouped
    into tabs, only one group's icons show at a time."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    assert window._rail_group_widgets[0].isHidden() is False
    for widget in window._rail_group_widgets[1:]:
        assert widget.isHidden() is True
    assert window._rail_group_buttons[0].isChecked()


def test_group_tabs_live_in_the_top_bar_not_the_side_rail(qtbot, tmp_path: Path) -> None:
    """Real user request: the group tabs (Browse/Research Tools/Study/
    System) moved out of the side rail into their own horizontal
    heading-line bar above it, matching Shamila/Jibreel's top-menu
    convention - the rail itself now holds only the icon+text buttons."""
    from PySide6.QtWidgets import QToolButton

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    for group_button in window._rail_group_buttons:
        assert group_button.parentWidget() is window._rail_group_bar

    rail_group_bar_buttons = window._rail_group_bar.findChildren(QToolButton)
    for real_rail_button in window._rail_buttons:
        assert real_rail_button not in rail_group_bar_buttons


def test_rail_buttons_show_a_real_text_label_under_the_icon(qtbot, tmp_path: Path) -> None:
    """Real user request: icon-only buttons weren't enough - every real
    rail button now shows its label as real visible text, not just a
    hover tooltip."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    for button in window._rail_buttons:
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        assert button.text() != ""
        assert button.iconSize().width() >= 24


def test_clicking_a_group_tab_switches_which_icons_are_visible(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._show_rail_group(2)  # "Study" group: Flashcards, MCQs

    assert window._rail_group_widgets[2].isHidden() is False
    assert window._rail_group_widgets[0].isHidden() is True
    assert window._rail_group_buttons[2].isChecked()
    assert not window._rail_group_buttons[0].isChecked()


def test_selecting_a_screen_outside_the_current_group_switches_groups_automatically(
    qtbot, tmp_path: Path
) -> None:
    """Real safety guard: navigating to a screen (e.g. via Quick Open)
    whose icon lives in a currently-hidden group must reveal that group,
    or the active screen's own rail button would be invisible with no
    way to tell which group it's in."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._show_screen(11)  # Flashcards - lives in the "Study" group, index 2

    assert window._rail_group_widgets[2].isHidden() is False
    assert window._rail_group_buttons[2].isChecked()
    assert window._rail_buttons[11].isChecked()


def test_header_shows_a_real_current_location_breadcrumb(qtbot, tmp_path: Path) -> None:
    """Navigation fix: a real 'you are here' indicator, updated on every
    rail switch - the rail alone doesn't make the current screen obvious
    at a glance once there are 7 entries."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    assert "Home" in window._header_bar._location_label.text()

    qtbot.mouseClick(window._rail_buttons[2], Qt.MouseButton.LeftButton)

    assert "Libraries" in window._header_bar._location_label.text()


def test_quick_open_navigates_to_the_requested_screen(
    qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ctrl+P's Quick Open dialog, once a screen is picked, really switches
    to it (dialog `.exec()` is patched out - it would block)."""
    from PySide6.QtWidgets import QDialog

    from islamic_research_hub.interfaces.desktop_app.quick_open_dialog import QuickOpenDialog

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    def _fake_exec(self: QuickOpenDialog) -> int:
        self.screen_requested.emit(2)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QuickOpenDialog, "exec", _fake_exec)

    window.open_quick_open()

    assert window._stack.currentIndex() == 2


def test_settings_screen_is_real_and_shows_real_app_info(qtbot, tmp_path: Path) -> None:
    """Settings is a real screen now, not a placeholder - it reflects the real database."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    settings_screen = window._stack.widget(14)
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
    settings_screen = window._stack.widget(14)

    try:
        ur_index = settings_screen._language_combo.findData("ur")
        settings_screen._language_combo.setCurrentIndex(ur_index)

        assert window._rail_buttons[0].text() == "ہوم"
        assert window._translator.layout_direction == Qt.LayoutDirection.RightToLeft
    finally:
        QApplication.instance().setLayoutDirection(Qt.LayoutDirection.LeftToRight)


def test_search_result_open_in_viewer_switches_screen_and_loads_the_book(
    qtbot, tmp_path: Path
) -> None:
    """Clicking 'Read in app' on a search result opens the Workspace with that
    book loaded in the inline reader - search stays reachable, not replaced."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._search_screen.open_in_viewer_requested.emit(1, 1)

    assert window._stack.currentIndex() == 1
    assert window._rail_buttons[1].isChecked()
    assert window._stack.widget(1) is window._workspace_screen
    assert window._viewer_stack.currentWidget() is window._viewer_screen
    assert window._viewer_screen._title_label.text() == "Book of Fiqh"
    assert window._viewer_screen._content_label.text() == "Some real page content"


def test_open_book_at_page_switches_screen_and_loads_the_book(qtbot, tmp_path: Path) -> None:
    """The public open_book_at_page() entry point (used by a maktaba:// link
    launch, see __main__.py) opens the same as clicking a search result."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window.open_book_at_page(1, 1)

    assert window._stack.currentIndex() == 1
    assert window._workspace_screen is not None
    assert window._stack.widget(1) is window._workspace_screen
    assert window._viewer_screen._title_label.text() == "Book of Fiqh"


def test_stub_book_shows_pdf_fallback_banner_and_opens_the_matched_pdf(
    qtbot, tmp_path: Path
) -> None:
    """A heading-only book offers its fuzzy-matched PDF, and opens it on request."""
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    stub_pages = tuple(Page(i, i, "hd", None) for i in range(1, 26))
    repository.import_books(
        database_path,
        (Book(information={"Name": "Ilm Ul Aasar"}, categories=(), table_of_contents=(), pages=stub_pages),),
        (tmp_path / "stub.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    real_pdf_path = tmp_path / "real_book.pdf"
    real_pdf_path.write_bytes(_MINIMAL_PDF_BYTES)
    repository.import_books(
        database_path,
        (Book(information={"Name": "Ilm Ul Aasar"}, categories=(), table_of_contents=(), pages=()),),
        (real_pdf_path,),
        library_name="Maktaba Jibreel (PDF Archive)",
    )
    PdfMatchCandidateRepository(database_path).detect_and_store()

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    window._search_screen.open_in_viewer_requested.emit(1, 1)

    assert window._viewer_stack.currentWidget() is window._viewer_screen
    assert window._viewer_screen._pdf_fallback_banner.isVisible()

    window._viewer_screen.pdf_fallback_requested.emit()

    assert window._viewer_stack.currentWidget() is window._pdf_viewer_screen
    assert window._pdf_viewer_screen._current_book_id == 2


def test_stub_book_offers_its_own_direct_pdf_before_checking_fuzzy_matches(
    qtbot, tmp_path: Path
) -> None:
    """A stub book in the original Al-Maknoon library offers its own real PDF directly.

    Real production data showed 481 stub books already resolve this way
    via the existing filename-stem lookup, with no fuzzy title matching
    involved at all - the fallback banner has to check this path too, not
    only `PdfMatchCandidateRepository`.
    """
    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    stub_pages = tuple(Page(i, i, "hd", None) for i in range(1, 26))
    maknoon_pdf_folder = tmp_path / "maknoon_pdfs"
    maknoon_pdf_folder.mkdir()
    real_pdf_path = maknoon_pdf_folder / "Book One.pdf"
    real_pdf_path.write_bytes(_MINIMAL_PDF_BYTES)
    stale_source = tmp_path / "extracted" / "Book One.pdf.txt"
    repository.import_books(
        database_path,
        (Book(information={"Name": "Ilm Ul Aasar"}, categories=(), table_of_contents=(), pages=stub_pages),),
        (stale_source,),
        library_name="Maktaba Al-Maknoon",
    )

    window = MainWindow(database_path, maknoon_pdf_folder, _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    window._search_screen.open_in_viewer_requested.emit(1, 1)

    assert window._viewer_stack.currentWidget() is window._viewer_screen
    assert window._viewer_screen._pdf_fallback_banner.isVisible()

    window._viewer_screen.pdf_fallback_requested.emit()

    assert window._viewer_stack.currentWidget() is window._pdf_viewer_screen
    assert window._pdf_viewer_screen._current_book_id == 1


def test_book_with_real_content_never_shows_the_pdf_fallback_banner(
    qtbot, tmp_path: Path
) -> None:
    """A book with real page text never gets the stub fallback banner, matched title or not."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)

    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    window._search_screen.open_in_viewer_requested.emit(1, 1)

    assert not window._viewer_screen._pdf_fallback_banner.isVisible()


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


def test_extract_events_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """The pre-flight check (enabled + a real key) must catch a
    misconfiguration before any real API call is attempted."""
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_extract_events_requested(1)

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Extract Events"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._event_extraction_worker is None  # no worker/API call attempted


def test_extract_events_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_extract_events_requested(1)

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._event_extraction_worker is None


def test_extract_narrators_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Same pre-flight check (enabled + a real key) as Extract Events, for
    the Extract Narrators handler."""
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_extract_narrators_requested(1)

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Extract Narrators"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._narrator_extraction_worker is None  # no worker/API call attempted


def test_extract_narrators_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_extract_narrators_requested(1)

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._narrator_extraction_worker is None


def test_explain_selection_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Same pre-flight check (enabled + a real key) as Extract Events, for
    the reader's "Explain this passage" handler (Phase 13 Milestone 1)."""
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_explain_selection_requested("A real selected passage.")

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Explain this passage"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._explain_worker is None  # no worker/API call attempted


def test_explain_selection_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_explain_selection_requested("A real selected passage.")

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._explain_worker is None


def test_summarize_selection_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_summarize_selection_requested("A real selected passage.")

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Summarize this passage"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._summarize_passage_worker is None


def test_summarize_selection_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_summarize_selection_requested("A real selected passage.")

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._summarize_passage_worker is None


def test_compare_selection_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_compare_selection_requested("A real selected passage.")

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Compare this passage"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._compare_passage_worker is None


def test_compare_selection_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_compare_selection_requested("A real selected passage.")

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._compare_passage_worker is None


def test_generate_flashcards_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Same pre-flight check (enabled + a real key) as Extract Events, for
    the reader's "Generate Flashcards" handler (Phase 15 Milestone 1)."""
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_generate_flashcards_requested(1)

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Generate Flashcards"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._flashcard_extraction_worker is None


def test_generate_flashcards_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_generate_flashcards_requested(1)

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._flashcard_extraction_worker is None


def test_generate_mcqs_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Same pre-flight check (enabled + a real key) as Extract Events, for
    the reader's "Generate MCQs" handler."""
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_generate_mcqs_requested(1)

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Generate MCQs"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._mcq_extraction_worker is None


def test_generate_mcqs_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_generate_mcqs_requested(1)

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._mcq_extraction_worker is None


def test_generate_slide_deck_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Same pre-flight check (enabled + a real key) as Extract Events, for
    the reader's "Generate Slide Deck" handler (Phase 17 Milestone 1)."""
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_generate_slide_deck_requested(1)

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Generate Slide Deck"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._slide_deck_worker is None


def test_generate_slide_deck_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_generate_slide_deck_requested(1)

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._slide_deck_worker is None


def test_generate_lecture_notes_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Same pre-flight check (enabled + a real key) as Extract Events, for
    the reader's "Generate Lecture Notes" handler (Phase 16 Milestone 2)."""
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_generate_lecture_notes_requested(1)

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Generate Lecture Notes"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._lecture_notes_worker is None


def test_generate_lecture_notes_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_generate_lecture_notes_requested(1)

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._lecture_notes_worker is None


def test_generate_podcast_with_ai_agent_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Same pre-flight check (enabled + a real key) as Extract Events, for
    the reader's "Generate Podcast" handler (Phase 17 Milestone 1)."""
    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window._on_generate_podcast_requested(1)

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Generate Podcast"
    assert "not enabled" in popup_calls[0][1].lower()
    assert window._podcast_worker is None


def test_generate_podcast_with_no_api_key_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
        AI_AGENT_PROVIDER_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    settings.setValue(AI_AGENT_PROVIDER_KEY, "anthropic")
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_generate_podcast_requested(1)

    assert len(popup_calls) == 1
    assert "No API key is set" in popup_calls[0][1]
    assert window._podcast_worker is None


def test_generate_podcast_with_tts_not_enabled_shows_the_unavailable_dialog(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """A second, distinct pre-flight check beyond the AI Agent - this
    feature also needs real TTS enabled, since it needs both."""
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        AI_AGENT_ENABLED_KEY,
    )

    popup_calls = []
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.show_ai_unavailable_dialog",
        lambda parent, feature_name, reason: popup_calls.append((feature_name, reason)),
    )
    monkeypatch.setattr(
        "islamic_research_hub.interfaces.desktop_app.main_window.resolve_ai_agent_api_key",
        lambda settings, provider: "a-real-key",
    )
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    settings.setValue(AI_AGENT_ENABLED_KEY, True)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", settings)
    qtbot.addWidget(window)

    window._on_generate_podcast_requested(1)

    assert len(popup_calls) == 1
    assert popup_calls[0][0] == "Generate Podcast"
    assert "text-to-speech" in popup_calls[0][1].lower()
    assert window._podcast_worker is None
