"""MCQ Manager screen: review real generated multiple-choice questions,
then quiz yourself on the confirmed ones (Phase 15 deferred scope,
shipped later).

Mirrors `flashcard_manager_screen.py`'s shape (table of candidates,
bulk `list_books_by_ids()` hydration, per-row actions, three-state
review - a generated MCQ asserts a real fact an LLM could hallucinate,
not just a link between two things this library already verifiably
holds). Adds one real thing `flashcard_manager_screen.py`'s flip-
through Study mode doesn't need: a real Quiz mode - pick an option, see
whether it was correct, track a running score, only ever over the
confirmed questions.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.domain.models.mcq_candidate import McqCandidate
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.mcq_candidate_repository import (
    McqCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading, _readonly_item
from islamic_research_hub.interfaces.desktop_app.theme import ACCENT, MUTED_LABEL_STYLE, RTL_TEXT_STYLE

_STATUS_KEYS: dict[str, str] = {
    "pending": "event-manager-status-pending",
    "confirmed": "event-manager-status-confirmed",
    "dismissed": "event-manager-status-dismissed",
}
_CORRECT_OPTION_STYLE = f"background-color: {ACCENT}; color: white; font-weight: 600;"
_WRONG_OPTION_STYLE = "background-color: #c0392b; color: white; font-weight: 600;"


class McqManagerScreen(QWidget):
    """Review real, LLM-generated MCQ candidates before trusting or
    quizzing yourself on any of them."""

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        mcqs: McqCandidateRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._mcqs = mcqs or McqCandidateRepository(database_path)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        self._heading_label = _heading(self._translator.tr("mcq-manager-heading"))
        header_row.addWidget(self._heading_label, stretch=1)
        self._quiz_button = QPushButton(self._translator.tr("mcq-manager-quiz"))
        self._quiz_button.setObjectName("primaryButton")
        self._quiz_button.clicked.connect(self._on_quiz_clicked)
        header_row.addWidget(self._quiz_button)
        layout.addLayout(header_row)

        self._intro_label = QLabel(self._translator.tr("mcq-manager-intro"))
        self._intro_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._intro_label.setWordWrap(True)
        layout.addWidget(self._intro_label)

        self._status_label = QLabel()
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._status_label)

        self._mcq_table = QTableWidget(0, 4)
        self._mcq_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._mcq_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._mcq_table.verticalHeader().setVisible(False)
        self._mcq_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._mcq_table, stretch=1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    def _table_header_labels(self) -> list[str]:
        return [
            self._translator.tr("event-manager-col-book"),
            self._translator.tr("mcq-manager-col-question"),
            self._translator.tr("event-manager-col-status"),
            "",
        ]

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("mcq-manager-heading"))
        self._quiz_button.setText(self._translator.tr("mcq-manager-quiz"))
        self._intro_label.setText(self._translator.tr("mcq-manager-intro"))
        self._mcq_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._reload_candidates()

    def refresh(self) -> None:
        """Reload the MCQ-candidates table from the real database."""
        self._reload_candidates()

    def _reload_candidates(self) -> None:
        candidates = list(self._mcqs.list_candidates(include_dismissed=True))
        self._status_label.setText(
            self._translator.tr("mcq-manager-candidates-count").format(count=len(candidates))
        )
        self._mcq_table.setRowCount(len(candidates))

        book_ids = tuple({candidate.book_id for candidate in candidates})
        summaries = self._browser.list_books_by_ids(book_ids)

        for row, candidate in enumerate(candidates):
            book_summary = summaries.get(candidate.book_id)
            book_title = (
                book_summary.title
                if book_summary
                else self._translator.tr("common-book-number").format(id=candidate.book_id)
            )
            untitled = self._translator.tr("common-untitled")
            self._mcq_table.setItem(row, 0, _readonly_item(book_title or untitled, rtl=True))
            self._mcq_table.setItem(row, 1, _readonly_item(candidate.mcq.question, rtl=True))
            self._mcq_table.setItem(
                row, 2, _readonly_item(self._translator.tr(_STATUS_KEYS.get(candidate.status, candidate.status)))
            )
            self._mcq_table.setCellWidget(row, 3, self._build_candidate_actions(candidate))

    def _build_candidate_actions(self, candidate: McqCandidate) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        view_button = QPushButton(self._translator.tr("common-view"))
        view_button.clicked.connect(lambda _checked, c=candidate: self._show_detail(c))
        layout.addWidget(view_button)

        confirm_button = QPushButton(self._translator.tr("common-confirm"))
        confirm_button.setEnabled(candidate.status != "confirmed")
        confirm_button.clicked.connect(lambda _checked, i=candidate.id: self._confirm_candidate(i))
        layout.addWidget(confirm_button)

        dismiss_button = QPushButton(self._translator.tr("common-dismiss"))
        dismiss_button.setEnabled(candidate.status != "dismissed")
        dismiss_button.clicked.connect(lambda _checked, i=candidate.id: self._dismiss_candidate(i))
        layout.addWidget(dismiss_button)

        return actions

    def _confirm_candidate(self, mcq_candidate_id: int) -> None:
        self._mcqs.confirm(mcq_candidate_id)
        self._reload_candidates()

    def _dismiss_candidate(self, mcq_candidate_id: int) -> None:
        self._mcqs.dismiss(mcq_candidate_id)
        self._reload_candidates()

    def _show_detail(self, candidate: McqCandidate) -> None:
        dialog = _build_detail_dialog(candidate, self._translator, self)
        dialog.exec()

    def _on_quiz_clicked(self) -> None:
        confirmed = self._mcqs.list_candidates(status="confirmed")
        dialog = _build_quiz_dialog(confirmed, self._translator, self)
        dialog.exec()


def _build_detail_dialog(candidate: McqCandidate, translator: Translator, parent: QWidget) -> QDialog:
    """Build a real, read-only dialog showing every generated field."""
    mcq = candidate.mcq
    dialog = QDialog(parent)
    dialog.setWindowTitle(mcq.question)
    dialog.resize(560, 460)
    layout = QVBoxLayout(dialog)

    title = QLabel(mcq.question)
    title.setWordWrap(True)
    title.setStyleSheet(f"font-size: 15px; font-weight: 700; {RTL_TEXT_STYLE}")
    layout.addWidget(title)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    content = QWidget()
    content_layout = QVBoxLayout(content)

    options_heading = QLabel(translator.tr("mcq-manager-detail-options"))
    options_heading.setStyleSheet(f"font-weight: 600; {MUTED_LABEL_STYLE}")
    content_layout.addWidget(options_heading)
    for index, option in enumerate(mcq.options):
        marker = " ✓" if index == mcq.correct_index else ""
        option_label = QLabel(f"{option}{marker}")
        option_label.setWordWrap(True)
        option_label.setStyleSheet(
            _CORRECT_OPTION_STYLE if index == mcq.correct_index else RTL_TEXT_STYLE
        )
        content_layout.addWidget(option_label)

    fields: tuple[tuple[str, str], ...] = (
        (translator.tr("event-manager-detail-quoted-excerpt"), mcq.quoted_excerpt),
        (translator.tr("event-manager-detail-citation"), mcq.citation),
        (translator.tr("event-manager-col-status"), translator.tr(_STATUS_KEYS.get(candidate.status, candidate.status))),
    )
    for label_text, value in fields:
        field_label = QLabel(label_text)
        field_label.setStyleSheet(f"font-weight: 600; {MUTED_LABEL_STYLE}")
        content_layout.addWidget(field_label)
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setStyleSheet(RTL_TEXT_STYLE)
        content_layout.addWidget(value_label)
    content_layout.addStretch(1)
    scroll_area.setWidget(content)
    layout.addWidget(scroll_area, stretch=1)

    close_button = QPushButton(translator.tr("common-close"))
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)

    return dialog


def _build_quiz_dialog(
    confirmed: tuple[McqCandidate, ...], translator: Translator, parent: QWidget
) -> QDialog:
    """A real quiz over only the confirmed MCQs - never an unreviewed or
    dismissed one. Milestone scope: sequential single-attempt questions
    with a running score; real spaced-repetition scheduling (interval
    tracking, due dates) is a separate, later milestone, not built here."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(translator.tr("mcq-manager-quiz"))
    dialog.resize(520, 420)
    layout = QVBoxLayout(dialog)

    if not confirmed:
        layout.addWidget(QLabel(translator.tr("mcq-manager-quiz-empty")))
        close_button = QPushButton(translator.tr("common-close"))
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        return dialog

    state = {"index": 0, "correct_count": 0, "answered": False}

    counter_label = QLabel()
    layout.addWidget(counter_label)

    question_label = QLabel()
    question_label.setWordWrap(True)
    question_label.setStyleSheet(f"font-size: 15px; {RTL_TEXT_STYLE}")
    layout.addWidget(question_label)

    option_buttons: list[QPushButton] = []
    for _ in range(4):
        button = QPushButton()
        button.setStyleSheet(RTL_TEXT_STYLE)
        layout.addWidget(button)
        option_buttons.append(button)

    score_label = QLabel()
    score_label.setStyleSheet(MUTED_LABEL_STYLE)
    layout.addWidget(score_label)

    next_button = QPushButton(translator.tr("common-next"))
    next_button.setEnabled(False)
    layout.addWidget(next_button)

    close_button = QPushButton(translator.tr("common-close"))
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)

    for option_index, button in enumerate(option_buttons):
        button.clicked.connect(
            lambda _checked, i=option_index: _answer_question(
                state, i, confirmed, option_buttons, score_label, next_button, translator
            )
        )
    next_button.clicked.connect(
        lambda: _advance_question(
            state, confirmed, question_label, option_buttons, score_label, next_button,
            counter_label, dialog, translator,
        )
    )

    _render_current_question(state, confirmed, question_label, option_buttons, score_label, counter_label, translator)
    return dialog


def _render_current_question(
    state: dict, confirmed: tuple[McqCandidate, ...], question_label: QLabel,
    option_buttons: list[QPushButton], score_label: QLabel, counter_label: QLabel, translator: Translator,
) -> None:
    state["answered"] = False
    candidate = confirmed[state["index"]]
    question_label.setText(candidate.mcq.question)
    for button, option in zip(option_buttons, candidate.mcq.options, strict=True):
        button.setText(option)
        button.setStyleSheet(RTL_TEXT_STYLE)
        button.setEnabled(True)
    counter_label.setText(
        translator.tr("mcq-manager-quiz-counter").format(current=state["index"] + 1, total=len(confirmed))
    )
    score_label.setText(
        translator.tr("mcq-manager-quiz-score").format(correct=state["correct_count"], total=state["index"])
    )


def _answer_question(
    state: dict, chosen_index: int, confirmed: tuple[McqCandidate, ...],
    option_buttons: list[QPushButton], score_label: QLabel, next_button: QPushButton, translator: Translator,
) -> None:
    if state["answered"]:
        return
    state["answered"] = True
    candidate = confirmed[state["index"]]
    correct_index = candidate.mcq.correct_index
    if chosen_index == correct_index:
        state["correct_count"] += 1
    for index, button in enumerate(option_buttons):
        button.setEnabled(False)
        if index == correct_index:
            button.setStyleSheet(_CORRECT_OPTION_STYLE)
        elif index == chosen_index:
            button.setStyleSheet(_WRONG_OPTION_STYLE)
    score_label.setText(
        translator.tr("mcq-manager-quiz-score").format(
            correct=state["correct_count"], total=state["index"] + 1
        )
    )
    next_button.setEnabled(True)


def _advance_question(
    state: dict, confirmed: tuple[McqCandidate, ...], question_label: QLabel,
    option_buttons: list[QPushButton], score_label: QLabel, next_button: QPushButton,
    counter_label: QLabel, dialog: QDialog, translator: Translator,
) -> None:
    if state["index"] + 1 >= len(confirmed):
        _render_quiz_finished(state, len(confirmed), question_label, option_buttons, score_label, next_button, counter_label, translator)
        return
    state["index"] += 1
    next_button.setEnabled(False)
    _render_current_question(state, confirmed, question_label, option_buttons, score_label, counter_label, translator)


def _render_quiz_finished(
    state: dict, total: int, question_label: QLabel, option_buttons: list[QPushButton],
    score_label: QLabel, next_button: QPushButton, counter_label: QLabel, translator: Translator,
) -> None:
    """Show a real final score instead of just closing the dialog the
    instant the last question is answered."""
    counter_label.setText(translator.tr("mcq-manager-quiz-finished-heading"))
    question_label.setText(
        translator.tr("mcq-manager-quiz-finished-score").format(
            correct=state["correct_count"], total=total
        )
    )
    for button in option_buttons:
        button.setVisible(False)
    score_label.setText("")
    next_button.setEnabled(False)
    next_button.setVisible(False)
