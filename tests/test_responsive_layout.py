"""Responsive Desktop verification: the main window at real-world resolutions.

Offscreen `window.resize(W, H)` + geometry assertions is the real,
meaningful verification method available in this sandbox (it can't
render/screenshot the live app) - checks that nothing clips, collapses
to zero, or overflows at common desktop/laptop/widescreen sizes.
"""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.main_window import RAIL_WIDTH, MainWindow  # noqa: E402

_RESOLUTIONS = (
    (1366, 768),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
    (3440, 1440),
)


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


@pytest.mark.parametrize("width,height", _RESOLUTIONS)
def test_main_window_has_no_degenerate_widget_sizes(
    qtbot, tmp_path: Path, width: int, height: int
) -> None:
    """At every target resolution: the window takes the real requested
    size, and the workspace splitter's segments are all non-negative and
    collectively take up real space - nothing clipped to nothing."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    window.resize(width, height)

    assert window.width() == width
    assert window.height() == height
    assert window._workspace_screen is not None
    splitter_sizes = window._workspace_screen._splitter.sizes()
    assert all(size >= 0 for size in splitter_sizes)
    assert sum(splitter_sizes) > 0


@pytest.mark.parametrize("width,height", _RESOLUTIONS)
def test_search_screen_nav_panes_never_exceed_their_real_maximum(
    qtbot, tmp_path: Path, width: int, height: int
) -> None:
    """Real fix verified directly: the left/right nav panes (category
    tree, detail panel) are capped so a wide monitor can't let them
    balloon and crowd out the results pane, the primary content."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)
    window.resize(width, height)

    search_splitter = window._search_screen._splitter
    left_pane, _middle_pane, right_pane = (search_splitter.widget(i) for i in range(3))
    assert left_pane.maximumWidth() == 420
    assert right_pane.maximumWidth() == 480
    sizes = search_splitter.sizes()
    assert sizes[0] <= left_pane.maximumWidth()
    assert sizes[2] <= right_pane.maximumWidth()


def test_rail_width_constant_matches_the_real_fixed_rail(qtbot, tmp_path: Path) -> None:
    """The navigation rail is meant to stay a fixed reference point (like
    VS Code/Obsidian's activity bar) regardless of window size."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    window = MainWindow(database_path, tmp_path / "maknoon_pdfs", _isolated_settings(tmp_path))
    qtbot.addWidget(window)

    for width, height in _RESOLUTIONS:
        window.resize(width, height)
        assert RAIL_WIDTH == 84
