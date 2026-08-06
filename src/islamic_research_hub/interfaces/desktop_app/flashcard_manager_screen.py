"""Flashcard Manager screen: review real generated flashcard candidates,
then study the confirmed ones (Phase 15 Milestone 1: educational features).

Mirrors `event_manager_screen.py`'s shape (table of candidates, bulk
`list_books_by_ids()` hydration, per-row actions, three-state review -
a generated flashcard asserts a real fact an LLM could hallucinate, not
just a link between two things this library already verifiably holds).
Adds one real thing `event_manager_screen.py` doesn't need: a Study
button that flips through only the confirmed flashcards - never the
unreviewed ones, so nothing unverified is ever presented as something
to memorize.
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

from islamic_research_hub.domain.models.flashcard_candidate import FlashcardCandidate
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.flashcard_candidate_repository import (
    FlashcardCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading, _readonly_item
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE

_STATUS_KEYS: dict[str, str] = {
    "pending": "event-manager-status-pending",
    "confirmed": "event-manager-status-confirmed",
    "dismissed": "event-manager-status-dismissed",
}


class FlashcardManagerScreen(QWidget):
    """Review real, LLM-generated flashcard candidates before trusting
    or studying any of them."""

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        flashcards: FlashcardCandidateRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._flashcards = flashcards or FlashcardCandidateRepository(database_path)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        self._heading_label = _heading(self._translator.tr("flashcard-manager-heading"))
        header_row.addWidget(self._heading_label, stretch=1)
        self._study_button = QPushButton(self._translator.tr("flashcard-manager-study"))
        self._study_button.setObjectName("primaryButton")
        self._study_button.clicked.connect(self._on_study_clicked)
        header_row.addWidget(self._study_button)
        layout.addLayout(header_row)

        self._intro_label = QLabel(self._translator.tr("flashcard-manager-intro"))
        self._intro_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._intro_label.setWordWrap(True)
        layout.addWidget(self._intro_label)

        self._status_label = QLabel()
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._status_label)

        self._flashcard_table = QTableWidget(0, 4)
        self._flashcard_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._flashcard_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._flashcard_table.verticalHeader().setVisible(False)
        self._flashcard_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._flashcard_table, stretch=1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    def _table_header_labels(self) -> list[str]:
        return [
            self._translator.tr("event-manager-col-book"),
            self._translator.tr("flashcard-manager-col-front"),
            self._translator.tr("event-manager-col-status"),
            "",
        ]

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("flashcard-manager-heading"))
        self._study_button.setText(self._translator.tr("flashcard-manager-study"))
        self._intro_label.setText(self._translator.tr("flashcard-manager-intro"))
        self._flashcard_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._reload_candidates()

    def refresh(self) -> None:
        """Reload the flashcard-candidates table from the real database."""
        self._reload_candidates()

    def _reload_candidates(self) -> None:
        candidates = list(self._flashcards.list_candidates(include_dismissed=True))
        self._status_label.setText(
            self._translator.tr("flashcard-manager-candidates-count").format(count=len(candidates))
        )
        self._flashcard_table.setRowCount(len(candidates))

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
            self._flashcard_table.setItem(row, 0, _readonly_item(book_title or untitled, rtl=True))
            self._flashcard_table.setItem(row, 1, _readonly_item(candidate.flashcard.front, rtl=True))
            self._flashcard_table.setItem(
                row, 2, _readonly_item(self._translator.tr(_STATUS_KEYS.get(candidate.status, candidate.status)))
            )
            self._flashcard_table.setCellWidget(row, 3, self._build_candidate_actions(candidate))

    def _build_candidate_actions(self, candidate: FlashcardCandidate) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        view_button = QPushButton(self._translator.tr("common-view"))
        view_button.clicked.connect(lambda _checked, c=candidate: self._show_detail(c))
        layout.addWidget(view_button)

        confirm_button = QPushButton(self._translator.tr("common-confirm"))
        confirm_button.setEnabled(candidate.status != "confirmed")
        confirm_button.clicked.connect(
            lambda _checked, i=candidate.id: self._confirm_candidate(i)
        )
        layout.addWidget(confirm_button)

        dismiss_button = QPushButton(self._translator.tr("common-dismiss"))
        dismiss_button.setEnabled(candidate.status != "dismissed")
        dismiss_button.clicked.connect(
            lambda _checked, i=candidate.id: self._dismiss_candidate(i)
        )
        layout.addWidget(dismiss_button)

        return actions

    def _confirm_candidate(self, flashcard_candidate_id: int) -> None:
        self._flashcards.confirm(flashcard_candidate_id)
        self._reload_candidates()

    def _dismiss_candidate(self, flashcard_candidate_id: int) -> None:
        self._flashcards.dismiss(flashcard_candidate_id)
        self._reload_candidates()

    def _show_detail(self, candidate: FlashcardCandidate) -> None:
        dialog = _build_detail_dialog(candidate, self._translator, self)
        dialog.exec()

    def _on_study_clicked(self) -> None:
        confirmed = self._flashcards.list_candidates(status="confirmed")
        dialog = _build_study_dialog(confirmed, self._translator, self)
        dialog.exec()


def _build_detail_dialog(
    candidate: FlashcardCandidate, translator: Translator, parent: QWidget
) -> QDialog:
    """Build a real, read-only dialog showing every generated field."""
    flashcard = candidate.flashcard
    dialog = QDialog(parent)
    dialog.setWindowTitle(flashcard.front)
    dialog.resize(560, 420)
    layout = QVBoxLayout(dialog)

    title = QLabel(flashcard.front)
    title.setWordWrap(True)
    title.setStyleSheet(f"font-size: 15px; font-weight: 700; {RTL_TEXT_STYLE}")
    layout.addWidget(title)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    content = QWidget()
    content_layout = QVBoxLayout(content)

    fields: tuple[tuple[str, str], ...] = (
        (translator.tr("flashcard-manager-detail-back"), flashcard.back),
        (translator.tr("event-manager-detail-quoted-excerpt"), flashcard.quoted_excerpt),
        (translator.tr("event-manager-detail-citation"), flashcard.citation),
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


def _build_study_dialog(
    confirmed: tuple[FlashcardCandidate, ...], translator: Translator, parent: QWidget
) -> QDialog:
    """A real, sequential flip-through review of only the confirmed
    flashcards - never an unreviewed or dismissed one. Milestone 1 scope:
    a simple front-then-back flip and Previous/Next; real spaced-
    repetition scheduling (interval tracking, due dates) is a separate,
    later milestone, not built here."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(translator.tr("flashcard-manager-study"))
    dialog.resize(480, 360)
    layout = QVBoxLayout(dialog)

    if not confirmed:
        layout.addWidget(QLabel(translator.tr("flashcard-manager-study-empty")))
        close_button = QPushButton(translator.tr("common-close"))
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        return dialog

    state = {"index": 0, "showing_back": False}

    counter_label = QLabel()
    layout.addWidget(counter_label)

    card_label = QLabel()
    card_label.setWordWrap(True)
    card_label.setStyleSheet(f"font-size: 15px; {RTL_TEXT_STYLE}")
    layout.addWidget(card_label, stretch=1)

    flip_button = QPushButton()
    flip_button.clicked.connect(lambda: _toggle_flip(state, card_label, flip_button, confirmed, translator))
    layout.addWidget(flip_button)

    nav_row = QHBoxLayout()
    previous_button = QPushButton(translator.tr("common-previous"))
    previous_button.clicked.connect(
        lambda: _navigate(state, -1, confirmed, card_label, flip_button, counter_label, translator)
    )
    nav_row.addWidget(previous_button)
    next_button = QPushButton(translator.tr("common-next"))
    next_button.clicked.connect(
        lambda: _navigate(state, 1, confirmed, card_label, flip_button, counter_label, translator)
    )
    nav_row.addWidget(next_button)
    layout.addLayout(nav_row)

    close_button = QPushButton(translator.tr("common-close"))
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)

    _render_current_card(state, confirmed, card_label, flip_button, counter_label, translator)
    return dialog


def _render_current_card(
    state: dict, confirmed: tuple[FlashcardCandidate, ...], card_label: QLabel,
    flip_button: QPushButton, counter_label: QLabel, translator: Translator,
) -> None:
    state["showing_back"] = False
    card = confirmed[state["index"]]
    card_label.setText(card.flashcard.front)
    flip_button.setText(translator.tr("flashcard-manager-show-answer"))
    counter_label.setText(
        translator.tr("flashcard-manager-study-counter").format(
            current=state["index"] + 1, total=len(confirmed)
        )
    )


def _toggle_flip(
    state: dict, card_label: QLabel, flip_button: QPushButton,
    confirmed: tuple[FlashcardCandidate, ...], translator: Translator,
) -> None:
    card = confirmed[state["index"]]
    state["showing_back"] = not state["showing_back"]
    if state["showing_back"]:
        card_label.setText(card.flashcard.back)
        flip_button.setText(translator.tr("flashcard-manager-show-question"))
    else:
        card_label.setText(card.flashcard.front)
        flip_button.setText(translator.tr("flashcard-manager-show-answer"))


def _navigate(
    state: dict, delta: int, confirmed: tuple[FlashcardCandidate, ...], card_label: QLabel,
    flip_button: QPushButton, counter_label: QLabel, translator: Translator,
) -> None:
    state["index"] = (state["index"] + delta) % len(confirmed)
    _render_current_card(state, confirmed, card_label, flip_button, counter_label, translator)
