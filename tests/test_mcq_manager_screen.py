"""Tests for the desktop app's MCQ Manager screen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QPushButton  # noqa: E402

from islamic_research_hub.application.mcq_extraction import ExtractedMcq  # noqa: E402
from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.mcq_candidate_repository import (  # noqa: E402
    McqCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.mcq_manager_screen import (  # noqa: E402
    McqManagerScreen,
)

_MCQ = ExtractedMcq(
    question="What is the ruling on zakat for gold below the nisab threshold?",
    options=("It is obligatory", "No zakat is due", "It is recommended", "It is forbidden"),
    correct_index=1,
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


def _seed_book_and_mcq(database_path: Path) -> None:
    book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", None),),
    )
    MasterBookRepository().import_books(database_path, (book,), (database_path.parent / "a.mjbz",))
    McqCandidateRepository(database_path).add_candidate(1, 1, 5, _MCQ)


def test_lists_a_real_candidate_with_bulk_hydrated_book_title(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_mcq(database_path)

    screen = McqManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._mcq_table.rowCount() == 1
    assert screen._mcq_table.item(0, 0).text() == "Book of Fiqh"
    assert screen._mcq_table.item(0, 1).text() == _MCQ.question
    assert screen._mcq_table.item(0, 2).text() == "Pending"


def test_empty_state_shows_zero_candidates(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (Book(information={"Name": "A Book"}, categories=(), table_of_contents=(), pages=()),),
        (database_path.parent / "a.mjbz",),
    )

    screen = McqManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert "0 question(s)" in screen._status_label.text()
    assert screen._mcq_table.rowCount() == 0


def test_confirm_button_persists_status(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_mcq(database_path)
    screen = McqManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    actions = screen._mcq_table.cellWidget(0, 3)
    _action_button(actions, "Confirm").click()

    assert screen._mcq_table.item(0, 2).text() == "Confirmed"
    assert McqCandidateRepository(database_path).list_candidates()[0].status == "confirmed"


def test_dismiss_button_persists_status(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_mcq(database_path)
    screen = McqManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    actions = screen._mcq_table.cellWidget(0, 3)
    _action_button(actions, "Dismiss").click()

    assert screen._mcq_table.item(0, 2).text() == "Dismissed"


def test_detail_dialog_shows_all_real_generated_fields(qtbot, tmp_path: Path) -> None:
    from PySide6.QtWidgets import QLabel

    from islamic_research_hub.domain.models.mcq_candidate import McqCandidate
    from islamic_research_hub.interfaces.desktop_app.mcq_manager_screen import (
        _build_detail_dialog,
    )

    candidate = McqCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, mcq=_MCQ)

    dialog = _build_detail_dialog(candidate, _translator(tmp_path), None)

    labels = {label.text() for label in dialog.findChildren(QLabel)}
    assert _MCQ.question in labels
    assert any(option in text for text in labels for option in _MCQ.options)
    assert _MCQ.quoted_excerpt in labels
    assert _MCQ.citation in labels


def test_quiz_dialog_with_no_confirmed_questions_shows_the_empty_state(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.interfaces.desktop_app.mcq_manager_screen import _build_quiz_dialog

    dialog = _build_quiz_dialog((), _translator(tmp_path), None)

    from PySide6.QtWidgets import QLabel

    labels = [label.text() for label in dialog.findChildren(QLabel)]
    assert any("No confirmed questions yet" in text for text in labels)


def test_quiz_dialog_shows_the_first_question_and_its_options(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.domain.models.mcq_candidate import McqCandidate
    from islamic_research_hub.interfaces.desktop_app.mcq_manager_screen import _build_quiz_dialog

    confirmed = (
        McqCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, mcq=_MCQ, status="confirmed"),
    )
    dialog = _build_quiz_dialog(confirmed, _translator(tmp_path), None)

    from PySide6.QtWidgets import QLabel

    question_label = dialog.findChildren(QLabel)[1]  # [0] is the counter label
    assert question_label.text() == _MCQ.question
    option_texts = {b.text() for b in dialog.findChildren(QPushButton)}
    for option in _MCQ.options:
        assert option in option_texts


def test_choosing_the_correct_option_increments_the_score(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.domain.models.mcq_candidate import McqCandidate
    from islamic_research_hub.interfaces.desktop_app.mcq_manager_screen import _build_quiz_dialog

    confirmed = (
        McqCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, mcq=_MCQ, status="confirmed"),
    )
    dialog = _build_quiz_dialog(confirmed, _translator(tmp_path), None)
    correct_button = next(
        b for b in dialog.findChildren(QPushButton) if b.text() == _MCQ.options[_MCQ.correct_index]
    )

    correct_button.click()

    from PySide6.QtWidgets import QLabel

    score_label = next(
        label for label in dialog.findChildren(QLabel) if label.text().startswith("Score:")
    )
    assert score_label.text() == "Score: 1/1"
    next_button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Next")
    assert next_button.isEnabled()


def test_choosing_a_wrong_option_does_not_increment_the_score(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.domain.models.mcq_candidate import McqCandidate
    from islamic_research_hub.interfaces.desktop_app.mcq_manager_screen import _build_quiz_dialog

    confirmed = (
        McqCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, mcq=_MCQ, status="confirmed"),
    )
    dialog = _build_quiz_dialog(confirmed, _translator(tmp_path), None)
    wrong_index = 0 if _MCQ.correct_index != 0 else 1
    wrong_button = next(
        b for b in dialog.findChildren(QPushButton) if b.text() == _MCQ.options[wrong_index]
    )

    wrong_button.click()

    from PySide6.QtWidgets import QLabel

    score_label = next(
        label for label in dialog.findChildren(QLabel) if label.text().startswith("Score:")
    )
    assert score_label.text() == "Score: 0/1"


def test_answering_twice_does_not_double_count_the_score(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.domain.models.mcq_candidate import McqCandidate
    from islamic_research_hub.interfaces.desktop_app.mcq_manager_screen import _build_quiz_dialog

    confirmed = (
        McqCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, mcq=_MCQ, status="confirmed"),
    )
    dialog = _build_quiz_dialog(confirmed, _translator(tmp_path), None)
    correct_button = next(
        b for b in dialog.findChildren(QPushButton) if b.text() == _MCQ.options[_MCQ.correct_index]
    )

    correct_button.click()
    correct_button.click()  # options are disabled after the first click, but guard directly too

    from PySide6.QtWidgets import QLabel

    score_label = next(
        label for label in dialog.findChildren(QLabel) if label.text().startswith("Score:")
    )
    assert score_label.text() == "Score: 1/1"


def test_finishing_the_last_question_shows_the_real_final_score(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.domain.models.mcq_candidate import McqCandidate
    from islamic_research_hub.interfaces.desktop_app.mcq_manager_screen import _build_quiz_dialog

    confirmed = (
        McqCandidate(id=1, book_id=1, chunk_start_page=1, chunk_end_page=5, mcq=_MCQ, status="confirmed"),
    )
    dialog = _build_quiz_dialog(confirmed, _translator(tmp_path), None)
    correct_button = next(
        b for b in dialog.findChildren(QPushButton) if b.text() == _MCQ.options[_MCQ.correct_index]
    )
    correct_button.click()
    next_button = next(b for b in dialog.findChildren(QPushButton) if b.text() == "Next")

    next_button.click()

    from PySide6.QtWidgets import QLabel

    question_label = dialog.findChildren(QLabel)[1]
    assert question_label.text() == "You scored 1 out of 1."


def test_only_confirmed_mcqs_are_offered_for_the_quiz(qtbot, tmp_path: Path) -> None:
    """Real safety guard: an unreviewed (or dismissed) MCQ must never be
    presented as something to quiz on."""
    database_path = tmp_path / "books.db"
    _seed_book_and_mcq(database_path)  # still "pending"
    screen = McqManagerScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    confirmed = screen._mcqs.list_candidates(status="confirmed")

    assert confirmed == ()


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_book_and_mcq(database_path)
    translator = _translator(tmp_path)
    screen = McqManagerScreen(database_path, translator)
    qtbot.addWidget(screen)
    assert screen._heading_label.text() == "MCQ review"
    assert screen._mcq_table.item(0, 2).text() == "Pending"

    translator.set_language("ur")

    assert screen._heading_label.text() == "کثیر انتخابی سوالات کا جائزہ"
    assert screen._mcq_table.item(0, 2).text() == "زیرِ التوا"
