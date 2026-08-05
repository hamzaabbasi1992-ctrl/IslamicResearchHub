"""Tests for the desktop app's Event Manager screen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402

from islamic_research_hub.application.event_extraction import ExtractedEvent  # noqa: E402
from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import (  # noqa: E402
    EventCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.event_manager_screen import (  # noqa: E402
    EventManagerScreen,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402

_EVENT = ExtractedEvent(
    title="Battle of Badr",
    alternate_names=("Ghazwa Badr",),
    subject="battle",
    date_hijri="17 Ramadan, 2 AH",
    date_gregorian="624 CE",
    location="Badr",
    background="Tensions between Mecca and Medina.",
    summary="The first major battle.",
    key_figures=("Prophet Muhammad",),
    quoted_excerpt="A real verbatim excerpt from the source text.",
    citation="Book of Seerah, Page 12, Paragraph 1",
)


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def _action_button(actions_widget: QPushButton, text: str) -> QPushButton:
    for button in actions_widget.findChildren(QPushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"No {text!r} button found")


def _seed_book_and_event(database_path: Path) -> None:
    book = Book(
        information={"Name": "Book of Seerah"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    EventCandidateRepository(database_path).add_candidate(1, 1, 5, _EVENT)


def test_lists_a_real_candidate_with_bulk_hydrated_book_title(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_event(database_path)

    screen = EventManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._event_table.rowCount() == 1
    assert screen._event_table.item(0, 0).text() == "Book of Seerah"
    assert screen._event_table.item(0, 1).text() == "Battle of Badr"
    assert screen._event_table.item(0, 2).text() == "battle"
    assert screen._event_table.item(0, 3).text() == "Pending"


def test_empty_state_shows_zero_candidates(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (Book(information={"Name": "A Book"}, categories=(), table_of_contents=(), pages=()),),
        (database_path.parent / "a.mjbz",),
    )

    screen = EventManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert "0 candidate(s)" in screen._status_label.text()
    assert screen._event_table.rowCount() == 0


def test_confirm_button_persists_status(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_event(database_path)
    screen = EventManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    actions = screen._event_table.cellWidget(0, 4)
    _action_button(actions, "Confirm").click()

    assert screen._event_table.item(0, 3).text() == "Confirmed"
    assert EventCandidateRepository(database_path).list_candidates()[0].status == "confirmed"


def test_dismiss_button_persists_status(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_event(database_path)
    screen = EventManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    actions = screen._event_table.cellWidget(0, 4)
    _action_button(actions, "Dismiss").click()

    assert screen._event_table.item(0, 3).text() == "Dismissed"


def test_detail_dialog_shows_all_real_extracted_fields(qtbot, tmp_path: Path) -> None:
    """Build the dialog directly (not via a real .exec() click, which
    would block headless) and confirm every field is genuinely present."""
    from PySide6.QtWidgets import QLabel

    from islamic_research_hub.domain.models.event_candidate import EventCandidate
    from islamic_research_hub.interfaces.desktop_app.event_manager_screen import (
        _build_detail_dialog,
    )

    candidate = EventCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, event=_EVENT)

    dialog = _build_detail_dialog(candidate, _translator(tmp_path), None)

    labels = {label.text() for label in dialog.findChildren(QLabel)}
    assert _EVENT.title in labels
    assert _EVENT.background in labels
    assert _EVENT.summary in labels
    assert _EVENT.quoted_excerpt in labels
    assert _EVENT.citation in labels
    assert "Ghazwa Badr" in labels
    assert "Prophet Muhammad" in labels


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_event(database_path)
    translator = _translator(tmp_path)
    screen = EventManagerScreen(database_path, translator)
    qtbot.addWidget(screen)
    assert screen._heading_label.text() == "Event review"
    assert screen._event_table.item(0, 3).text() == "Pending"

    translator.set_language("ur")

    assert screen._heading_label.text() == "واقعات کا جائزہ"
    assert screen._event_table.item(0, 3).text() == "زیرِ التوا"
    actions = screen._event_table.cellWidget(0, 4)
    _action_button(actions, "دیکھیں")
