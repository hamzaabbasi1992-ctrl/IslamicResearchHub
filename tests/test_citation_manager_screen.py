"""Tests for the desktop app's Citation Manager screen."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QPushButton  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.citation_candidate_repository import (  # noqa: E402
    CitationCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.interfaces.desktop_app.citation_manager_screen import (  # noqa: E402
    CitationManagerScreen,
)

_DISTINCTIVE_TITLE = "A Real Distinctive Citation Target Title"


def _action_button(actions_widget: QPushButton, text: str) -> QPushButton:
    for button in actions_widget.findChildren(QPushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"No {text!r} button found")


def _seed_real_citation(database_path: Path) -> None:
    MasterBookRepository().import_books(
        database_path,
        (
            Book(
                information={"Name": _DISTINCTIVE_TITLE},
                categories=(),
                table_of_contents=(),
                pages=(Page(1, 1, "front matter", None),),
            ),
            Book(
                information={"Name": "A Citing Book"},
                categories=(),
                table_of_contents=(),
                pages=(Page(1, 1, f"as mentioned in {_DISTINCTIVE_TITLE} earlier", None),),
            ),
        ),
        (database_path.parent / "a.mjbz", database_path.parent / "b.mjbz"),
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)


def test_empty_state_shows_zero_candidates(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_real_citation(database_path)
    screen = CitationManagerScreen(database_path)
    qtbot.addWidget(screen)

    assert "0 candidate(s)" in screen._status_label.text()
    assert screen._citation_table.rowCount() == 0


def test_scan_button_detects_and_lists_a_real_citation(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_real_citation(database_path)
    screen = CitationManagerScreen(database_path)
    qtbot.addWidget(screen)

    screen._scan_button.click()
    with qtbot.waitSignal(screen._scan_worker.finished, timeout=5000):
        pass
    qtbot.wait(50)

    assert "1 candidate(s)" in screen._status_label.text()
    assert screen._citation_table.rowCount() == 1
    assert screen._citation_table.item(0, 0).text() == "A Citing Book"
    assert screen._citation_table.item(0, 2).text() == _DISTINCTIVE_TITLE
    assert screen._scan_button.isEnabled()


def test_dismiss_button_persists_and_removes_the_row(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_real_citation(database_path)
    CitationCandidateRepository(database_path).detect_and_store()
    screen = CitationManagerScreen(database_path)
    qtbot.addWidget(screen)
    assert screen._citation_table.rowCount() == 1

    actions = screen._citation_table.cellWidget(0, 4)
    _action_button(actions, "Dismiss").click()

    assert screen._citation_table.rowCount() == 0
    assert CitationCandidateRepository(database_path).list_candidates() == ()
    assert len(CitationCandidateRepository(database_path).list_candidates(include_dismissed=True)) == 1


def test_dismiss_all_from_this_book_dismisses_every_row_for_the_pair(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (
            Book(
                information={"Name": _DISTINCTIVE_TITLE},
                categories=(),
                table_of_contents=(),
                pages=(Page(1, 1, "front matter", None),),
            ),
            Book(
                information={"Name": "A Heavily Citing Book"},
                categories=(),
                table_of_contents=(),
                pages=(
                    Page(1, 1, f"first mention of {_DISTINCTIVE_TITLE}", None),
                    Page(2, 2, f"second mention of {_DISTINCTIVE_TITLE}", None),
                ),
            ),
        ),
        (database_path.parent / "a.mjbz", database_path.parent / "b.mjbz"),
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    CitationCandidateRepository(database_path).detect_and_store()
    screen = CitationManagerScreen(database_path)
    qtbot.addWidget(screen)
    assert screen._citation_table.rowCount() == 2

    actions = screen._citation_table.cellWidget(0, 4)
    _action_button(actions, "Dismiss all from this book").click()

    assert screen._citation_table.rowCount() == 0


def test_pagination_controls_page_through_a_large_real_result_set(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Real production scale (329,202+ real candidates) makes loading
    everything into one table impractical - confirmed directly running
    against the actual corpus. Previous/Next must page through real
    results without duplicating or skipping any."""
    from islamic_research_hub.interfaces.desktop_app import citation_manager_screen as module

    monkeypatch.setattr(module, "PAGE_SIZE", 2)
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (
            Book(
                information={"Name": _DISTINCTIVE_TITLE},
                categories=(),
                table_of_contents=(),
                pages=(Page(1, 1, "front matter", None),),
            ),
            Book(
                information={"Name": "A Heavily Citing Book"},
                categories=(),
                table_of_contents=(),
                pages=(
                    Page(1, 1, f"first mention of {_DISTINCTIVE_TITLE}", None),
                    Page(2, 2, f"second mention of {_DISTINCTIVE_TITLE}", None),
                    Page(3, 3, f"third mention of {_DISTINCTIVE_TITLE}", None),
                ),
            ),
        ),
        (database_path.parent / "a.mjbz", database_path.parent / "b.mjbz"),
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    CitationCandidateRepository(database_path).detect_and_store()

    screen = CitationManagerScreen(database_path)
    qtbot.addWidget(screen)

    assert screen._citation_table.rowCount() == 2
    assert "1-2 of 3" in screen._page_label.text()
    assert not screen._previous_page_button.isEnabled()
    assert screen._next_page_button.isEnabled()

    screen._next_page_button.click()

    assert screen._citation_table.rowCount() == 1
    assert "3-3 of 3" in screen._page_label.text()
    assert screen._previous_page_button.isEnabled()
    assert not screen._next_page_button.isEnabled()

    screen._previous_page_button.click()

    assert "1-2 of 3" in screen._page_label.text()
