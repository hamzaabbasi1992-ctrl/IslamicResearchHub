"""Tests for the desktop app's Flashcard Manager screen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402

from islamic_research_hub.application.flashcard_extraction import ExtractedFlashcard  # noqa: E402
from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.flashcard_candidate_repository import (  # noqa: E402
    FlashcardCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.flashcard_manager_screen import (  # noqa: E402
    FlashcardManagerScreen,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402

_FLASHCARD = ExtractedFlashcard(
    front="What is the ruling on zakat for gold below the nisab threshold?",
    back="No zakat is due until the nisab threshold is reached.",
    quoted_excerpt="A real verbatim excerpt from the source text.",
    citation="Book of Fiqh, Page 12, Paragraph 1",
)


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def _action_button(actions_widget: QPushButton, text: str) -> QPushButton:
    for button in actions_widget.findChildren(QPushButton):
        if button.text() == text:
            return button
    raise AssertionError(f"No {text!r} button found")


def _seed_book_and_flashcard(database_path: Path) -> None:
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    FlashcardCandidateRepository(database_path).add_candidate(1, 1, 5, _FLASHCARD)


def test_lists_a_real_candidate_with_bulk_hydrated_book_title(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_flashcard(database_path)

    screen = FlashcardManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._flashcard_table.rowCount() == 1
    assert screen._flashcard_table.item(0, 0).text() == "Book of Fiqh"
    assert screen._flashcard_table.item(0, 1).text() == _FLASHCARD.front
    assert screen._flashcard_table.item(0, 2).text() == "Pending"


def test_empty_state_shows_zero_candidates(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (Book(information={"Name": "A Book"}, categories=(), table_of_contents=(), pages=()),),
        (database_path.parent / "a.mjbz",),
    )

    screen = FlashcardManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert "0 flashcard(s)" in screen._status_label.text()
    assert screen._flashcard_table.rowCount() == 0


def test_confirm_button_persists_status(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_flashcard(database_path)
    screen = FlashcardManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    actions = screen._flashcard_table.cellWidget(0, 3)
    _action_button(actions, "Confirm").click()

    assert screen._flashcard_table.item(0, 2).text() == "Confirmed"
    assert FlashcardCandidateRepository(database_path).list_candidates()[0].status == "confirmed"


def test_dismiss_button_persists_status(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_flashcard(database_path)
    screen = FlashcardManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    actions = screen._flashcard_table.cellWidget(0, 3)
    _action_button(actions, "Dismiss").click()

    assert screen._flashcard_table.item(0, 2).text() == "Dismissed"


def test_detail_dialog_shows_all_real_generated_fields(qtbot, tmp_path: Path) -> None:
    from PySide6.QtWidgets import QLabel

    from islamic_research_hub.domain.models.flashcard_candidate import FlashcardCandidate
    from islamic_research_hub.interfaces.desktop_app.flashcard_manager_screen import (
        _build_detail_dialog,
    )

    candidate = FlashcardCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, flashcard=_FLASHCARD)

    dialog = _build_detail_dialog(candidate, _translator(tmp_path), None)

    labels = {label.text() for label in dialog.findChildren(QLabel)}
    assert _FLASHCARD.front in labels
    assert _FLASHCARD.back in labels
    assert _FLASHCARD.quoted_excerpt in labels
    assert _FLASHCARD.citation in labels


def test_study_dialog_with_no_confirmed_cards_shows_the_empty_state(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.interfaces.desktop_app.flashcard_manager_screen import (
        _build_study_dialog,
    )

    dialog = _build_study_dialog((), _translator(tmp_path), None)

    from PySide6.QtWidgets import QLabel

    labels = [label.text() for label in dialog.findChildren(QLabel)]
    assert any("No confirmed flashcards yet" in text for text in labels)


def test_study_dialog_shows_front_first_then_flips_to_back(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.domain.models.flashcard_candidate import FlashcardCandidate
    from islamic_research_hub.interfaces.desktop_app.flashcard_manager_screen import (
        _build_study_dialog,
    )

    confirmed = (
        FlashcardCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, flashcard=_FLASHCARD, status="confirmed"),
    )
    dialog = _build_study_dialog(confirmed, _translator(tmp_path), None)

    from PySide6.QtWidgets import QLabel, QPushButton

    card_label = dialog.findChildren(QLabel)[1]  # [0] is the counter label
    assert card_label.text() == _FLASHCARD.front

    flip_button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Show Answer")
    flip_button.click()

    assert card_label.text() == _FLASHCARD.back
    assert flip_button.text() == "Show Question"


def test_study_dialog_navigates_between_confirmed_cards(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.domain.models.flashcard_candidate import FlashcardCandidate
    from islamic_research_hub.interfaces.desktop_app.flashcard_manager_screen import (
        _build_study_dialog,
    )

    second = ExtractedFlashcard(
        front="A second question", back="A second answer",
        quoted_excerpt="excerpt", citation="Book, Page 2, Paragraph 1",
    )
    confirmed = (
        FlashcardCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, flashcard=_FLASHCARD, status="confirmed"),
        FlashcardCandidate(id=2, book_id=1, chunk_start_page=6, chunk_end_page=10, flashcard=second, status="confirmed"),
    )
    dialog = _build_study_dialog(confirmed, _translator(tmp_path), None)

    from PySide6.QtWidgets import QLabel, QPushButton

    card_label = dialog.findChildren(QLabel)[1]
    next_button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Next")

    next_button.click()

    assert card_label.text() == second.front


def test_only_confirmed_flashcards_are_offered_for_study(qtbot, tmp_path: Path) -> None:
    """Real safety guard: an unreviewed (or dismissed) flashcard must
    never be presented as something to memorize."""
    database_path = tmp_path / "books.db"
    _seed_book_and_flashcard(database_path)  # still "pending"
    screen = FlashcardManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    confirmed = screen._flashcards.list_candidates(status="confirmed")

    assert confirmed == ()


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_flashcard(database_path)
    translator = _translator(tmp_path)
    screen = FlashcardManagerScreen(database_path, translator)
    qtbot.addWidget(screen)
    assert screen._heading_label.text() == "Flashcard review"
    assert screen._flashcard_table.item(0, 2).text() == "Pending"

    translator.set_language("ur")

    assert screen._heading_label.text() == "فلیش کارڈز کا جائزہ"
    assert screen._flashcard_table.item(0, 2).text() == "زیرِ التوا"
