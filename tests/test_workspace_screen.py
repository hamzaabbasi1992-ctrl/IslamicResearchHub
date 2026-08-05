"""Tests for the desktop app's Workspace screen (Search + Reader + AI panel).

`WorkspaceScreen` itself doesn't care what's inside the reader stack - a
plain placeholder widget stands in for `ViewerScreen`/`PdfViewerScreen`
here, keeping these tests focused on the splitter mechanics (show/hide,
sizing) rather than duplicating the Viewer's own test coverage.
"""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QLabel, QStackedWidget  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.ai_panel_screen import AiAssistantPanel  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.workspace_screen import WorkspaceScreen  # noqa: E402


def _isolated_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def _translator(tmp_path: Path) -> Translator:
    return Translator(_isolated_settings(tmp_path))


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


def _build_workspace(qtbot, tmp_path: Path) -> tuple[WorkspaceScreen, QStackedWidget, QLabel]:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    search_screen = SearchScreen(database_path, tmp_path / "maknoon_pdfs", _translator(tmp_path))
    reader_stack = QStackedWidget()
    reader_placeholder = QLabel("reader content")
    reader_stack.addWidget(reader_placeholder)
    ai_panel = AiAssistantPanel(_isolated_settings(tmp_path), _translator(tmp_path))

    workspace = WorkspaceScreen(search_screen, reader_stack, ai_panel)
    qtbot.addWidget(workspace)
    workspace.resize(1200, 800)
    return workspace, reader_stack, reader_placeholder


def _finish(animation) -> None:
    """Scrub an in-progress splitter animation straight to its end value -
    deterministic, no dependency on a real timer/event loop."""
    animation.setCurrentTime(animation.duration())


def test_reader_segment_starts_with_a_real_visible_width(qtbot, tmp_path: Path) -> None:
    """Reader Redesign fix: the reader used to start collapsed to 0px (a
    hidden segment) even with no book open - directly the cause of "the
    center panel is frequently empty." It now starts with a real, visible
    width, showing the reader's own empty state instead of being hidden.
    (Not pinned to the exact `_MIN_READER_WIDTH` constant - real QSplitter
    geometry differs slightly between a shown and an unshown widget; the
    real regression this guards is "was 0, now clearly isn't.")
    """
    workspace, _reader_stack, _placeholder = _build_workspace(qtbot, tmp_path)

    assert workspace._splitter.sizes()[1] > 100


def test_show_reader_expands_the_reader_segment(qtbot, tmp_path: Path) -> None:
    """Showing a widget in the reader expands its segment to a real width."""
    workspace, reader_stack, placeholder = _build_workspace(qtbot, tmp_path)

    workspace.show_reader(placeholder)
    _finish(workspace._reader_animation)

    assert reader_stack.currentWidget() is placeholder
    assert workspace._splitter.sizes()[1] > 0


def test_search_segment_stays_visible_once_the_reader_opens(qtbot, tmp_path: Path) -> None:
    """Opening the reader doesn't hide the search segment - both stay visible."""
    workspace, _reader_stack, placeholder = _build_workspace(qtbot, tmp_path)

    workspace.show_reader(placeholder)
    _finish(workspace._reader_animation)

    assert workspace._splitter.sizes()[0] > 0


def test_show_reader_none_collapses_it_again(qtbot, tmp_path: Path) -> None:
    """Passing None re-collapses the reader segment (e.g. closing a book)."""
    workspace, _reader_stack, placeholder = _build_workspace(qtbot, tmp_path)
    workspace.show_reader(placeholder)
    _finish(workspace._reader_animation)

    workspace.show_reader(None)
    _finish(workspace._reader_animation)

    assert workspace._splitter.sizes()[1] == 0


def test_ai_panel_starts_expanded_by_default(qtbot, tmp_path: Path) -> None:
    """With no stored preference, the AI panel segment takes real width."""
    workspace, _reader_stack, _placeholder = _build_workspace(qtbot, tmp_path)

    assert workspace._splitter.sizes()[2] > 0


def test_collapsing_the_ai_panel_shrinks_its_segment_to_zero(qtbot, tmp_path: Path) -> None:
    """Toggling the panel's own collapse button shrinks its splitter segment."""
    workspace, _reader_stack, _placeholder = _build_workspace(qtbot, tmp_path)

    workspace._ai_panel.toggle_collapsed()
    _finish(workspace._ai_panel_animation)

    assert workspace._splitter.sizes()[2] == 0


def test_expanding_the_ai_panel_again_restores_its_width(qtbot, tmp_path: Path) -> None:
    """Toggling back to expanded restores a real (non-zero) width."""
    workspace, _reader_stack, _placeholder = _build_workspace(qtbot, tmp_path)
    workspace._ai_panel.toggle_collapsed()
    _finish(workspace._ai_panel_animation)

    workspace._ai_panel.toggle_collapsed()
    _finish(workspace._ai_panel_animation)

    assert workspace._splitter.sizes()[2] > 0


def test_show_reader_animates_smoothly_through_intermediate_widths(qtbot, tmp_path: Path) -> None:
    """The reader segment genuinely animates when re-expanding after being
    closed - not just an instant jump. (The reader now starts with a real
    width already, so this exercises the collapse-then-reopen case, the
    scenario where a real size change actually happens.)"""
    workspace, _reader_stack, placeholder = _build_workspace(qtbot, tmp_path)
    workspace.show_reader(None)
    _finish(workspace._reader_animation)

    workspace.show_reader(placeholder)
    animation = workspace._reader_animation
    animation.setCurrentTime(animation.duration() // 2)

    assert 0 < workspace._splitter.sizes()[1] < animation.endValue()


def test_show_reader_without_animation_applies_instantly(qtbot, tmp_path: Path) -> None:
    """`animated=False` (used for the initial layout) skips the animation entirely."""
    workspace, _reader_stack, placeholder = _build_workspace(qtbot, tmp_path)

    workspace.show_reader(placeholder, animated=False)

    assert workspace._splitter.sizes()[1] > 0


def test_ai_panel_maximize_grows_it_and_restores_on_toggle_back(
    qtbot, tmp_path: Path
) -> None:
    workspace, _reader_stack, _placeholder = _build_workspace(qtbot, tmp_path)
    workspace.show()
    qtbot.waitExposed(workspace)
    initial_sizes = workspace._splitter.sizes()

    workspace._ai_panel.maximize_clicked.emit()

    assert workspace._ai_panel_toggle.is_maximized is True

    workspace._ai_panel.maximize_clicked.emit()

    assert workspace._ai_panel_toggle.is_maximized is False
    assert workspace._splitter.sizes() == initial_sizes


def test_ai_panel_maximize_expands_it_first_if_collapsed(qtbot, tmp_path: Path) -> None:
    workspace, _reader_stack, _placeholder = _build_workspace(qtbot, tmp_path)
    workspace._ai_panel.toggle_collapsed()
    _finish(workspace._ai_panel_animation)
    assert workspace._ai_panel.is_collapsed is True

    workspace._ai_panel.maximize_clicked.emit()

    assert workspace._ai_panel.is_collapsed is False
    assert workspace._splitter.sizes()[2] > 100
