"""Narrator Manager screen: review real extracted narrator candidates.

Mirrors `event_manager_screen.py`'s shape exactly (table of candidates,
bulk `list_books_by_ids()` hydration, three-state View/Confirm/Dismiss
review) - a narrator mention asserts a real fact (this name appears at
this hadith reference) an LLM could hallucinate, the same reasoning
`EventCandidate` uses for its own 3-state status.
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

from islamic_research_hub.domain.models.narrator_candidate import NarratorCandidate
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.narrator_candidate_repository import (
    NarratorCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading, _readonly_item
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE

_STATUS_KEYS: dict[str, str] = {
    "pending": "event-manager-status-pending",
    "confirmed": "event-manager-status-confirmed",
    "dismissed": "event-manager-status-dismissed",
}


class NarratorManagerScreen(QWidget):
    """Review real, LLM-extracted narrator candidates before trusting any of them."""

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        narrators: NarratorCandidateRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._narrators = narrators or NarratorCandidateRepository(database_path)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._heading_label = _heading(self._translator.tr("narrator-manager-heading"))
        layout.addWidget(self._heading_label)
        self._safety_note_label = QLabel(self._translator.tr("narrator-manager-safety-note"))
        self._safety_note_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._safety_note_label.setWordWrap(True)
        layout.addWidget(self._safety_note_label)
        self._status_label = QLabel()
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._status_label)

        self._narrator_table = QTableWidget(0, 5)
        self._narrator_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._narrator_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._narrator_table.verticalHeader().setVisible(False)
        self._narrator_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._narrator_table, stretch=1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    def _table_header_labels(self) -> list[str]:
        return [
            self._translator.tr("event-manager-col-book"),
            self._translator.tr("narrator-manager-col-name"),
            self._translator.tr("narrator-manager-col-hadith-reference"),
            self._translator.tr("event-manager-col-status"),
            "",
        ]

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("narrator-manager-heading"))
        self._safety_note_label.setText(self._translator.tr("narrator-manager-safety-note"))
        self._narrator_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._reload_candidates()

    def refresh(self) -> None:
        """Reload the narrator-candidates table from the real database."""
        self._reload_candidates()

    def _reload_candidates(self) -> None:
        candidates = list(self._narrators.list_candidates(include_dismissed=True))
        self._status_label.setText(
            self._translator.tr("narrator-manager-candidates-count").format(count=len(candidates))
        )
        self._narrator_table.setRowCount(len(candidates))

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
            self._narrator_table.setItem(row, 0, _readonly_item(book_title or untitled, rtl=True))
            self._narrator_table.setItem(row, 1, _readonly_item(candidate.narrator.name, rtl=True))
            self._narrator_table.setItem(
                row, 2, _readonly_item(candidate.narrator.hadith_reference, rtl=True)
            )
            self._narrator_table.setItem(
                row, 3, _readonly_item(self._translator.tr(_STATUS_KEYS.get(candidate.status, candidate.status)))
            )
            self._narrator_table.setCellWidget(row, 4, self._build_candidate_actions(candidate))

    def _build_candidate_actions(self, candidate: NarratorCandidate) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        view_button = QPushButton(self._translator.tr("common-view"))
        view_button.clicked.connect(lambda _checked, c=candidate: self._show_detail(c))
        layout.addWidget(view_button)

        confirm_button = QPushButton(self._translator.tr("common-confirm"))
        confirm_button.setToolTip(self._translator.tr("narrator-manager-confirm-tooltip"))
        confirm_button.setEnabled(candidate.status != "confirmed")
        confirm_button.clicked.connect(
            lambda _checked, i=candidate.id: self._confirm_candidate(i)
        )
        layout.addWidget(confirm_button)

        dismiss_button = QPushButton(self._translator.tr("common-dismiss"))
        dismiss_button.setToolTip(self._translator.tr("narrator-manager-dismiss-tooltip"))
        dismiss_button.setEnabled(candidate.status != "dismissed")
        dismiss_button.clicked.connect(
            lambda _checked, i=candidate.id: self._dismiss_candidate(i)
        )
        layout.addWidget(dismiss_button)

        return actions

    def _confirm_candidate(self, narrator_candidate_id: int) -> None:
        self._narrators.confirm(narrator_candidate_id)
        self._reload_candidates()

    def _dismiss_candidate(self, narrator_candidate_id: int) -> None:
        self._narrators.dismiss(narrator_candidate_id)
        self._reload_candidates()

    def _show_detail(self, candidate: NarratorCandidate) -> None:
        dialog = _build_detail_dialog(candidate, self._translator, self)
        dialog.exec()


def _build_detail_dialog(
    candidate: NarratorCandidate, translator: Translator, parent: QWidget
) -> QDialog:
    """Build a real, read-only dialog showing every extracted field."""
    narrator = candidate.narrator
    dialog = QDialog(parent)
    dialog.setWindowTitle(narrator.name)
    dialog.resize(560, 520)
    layout = QVBoxLayout(dialog)

    title = QLabel(narrator.name)
    title.setWordWrap(True)
    title.setStyleSheet(f"font-size: 15px; font-weight: 700; {RTL_TEXT_STYLE}")
    layout.addWidget(title)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    content = QWidget()
    content_layout = QVBoxLayout(content)

    none_text = translator.tr("event-manager-detail-none")
    unknown_text = translator.tr("event-manager-detail-unknown")
    fields: tuple[tuple[str, str], ...] = (
        (
            translator.tr("event-manager-detail-alternate-names"),
            ", ".join(narrator.alternate_names) or none_text,
        ),
        (translator.tr("narrator-manager-detail-kunya-nasab"), narrator.kunya_nasab or unknown_text),
        (translator.tr("narrator-manager-detail-generation"), narrator.generation or unknown_text),
        (translator.tr("narrator-manager-col-hadith-reference"), narrator.hadith_reference),
        (translator.tr("event-manager-detail-quoted-excerpt"), narrator.quoted_excerpt),
        (translator.tr("event-manager-detail-citation"), narrator.citation),
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
