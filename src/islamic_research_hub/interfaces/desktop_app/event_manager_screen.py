"""Event Manager screen: review real extracted event candidates.

Mirrors `citation_manager_screen.py`'s shape (table of candidates, bulk
`list_books_by_ids()` hydration, per-row actions), with one real
difference: an extracted event asserts real historical facts an LLM
could hallucinate, not just a link between two things this library
already verifiably holds - so review here is three-state (View the full
record, then Confirm or Dismiss), not just Dismiss.
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

from islamic_research_hub.domain.models.event_candidate import EventCandidate
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import (
    EventCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading, _readonly_item
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE

_STATUS_KEYS: dict[str, str] = {
    "pending": "event-manager-status-pending",
    "confirmed": "event-manager-status-confirmed",
    "dismissed": "event-manager-status-dismissed",
}


class EventManagerScreen(QWidget):
    """Review real, LLM-extracted event candidates before trusting any of them."""

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        events: EventCandidateRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._events = events or EventCandidateRepository(database_path)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._heading_label = _heading(self._translator.tr("event-manager-heading"))
        layout.addWidget(self._heading_label)
        self._status_label = QLabel()
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._status_label)

        self._event_table = QTableWidget(0, 5)
        self._event_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._event_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._event_table.verticalHeader().setVisible(False)
        self._event_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._event_table, stretch=1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    def _table_header_labels(self) -> list[str]:
        return [
            self._translator.tr("event-manager-col-book"),
            self._translator.tr("event-manager-col-event"),
            self._translator.tr("taxonomy-dim-subject"),
            self._translator.tr("event-manager-col-status"),
            "",
        ]

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("event-manager-heading"))
        self._event_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._reload_candidates()

    def refresh(self) -> None:
        """Reload the event-candidates table from the real database."""
        self._reload_candidates()

    def _reload_candidates(self) -> None:
        candidates = list(self._events.list_candidates(include_dismissed=True))
        self._status_label.setText(
            self._translator.tr("event-manager-candidates-count").format(count=len(candidates))
        )
        self._event_table.setRowCount(len(candidates))

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
            self._event_table.setItem(row, 0, _readonly_item(book_title or untitled, rtl=True))
            self._event_table.setItem(row, 1, _readonly_item(candidate.event.title, rtl=True))
            self._event_table.setItem(row, 2, _readonly_item(candidate.event.subject))
            self._event_table.setItem(
                row, 3, _readonly_item(self._translator.tr(_STATUS_KEYS.get(candidate.status, candidate.status)))
            )
            self._event_table.setCellWidget(row, 4, self._build_candidate_actions(candidate))

    def _build_candidate_actions(self, candidate: EventCandidate) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        view_button = QPushButton(self._translator.tr("common-view"))
        view_button.clicked.connect(lambda _checked, c=candidate: self._show_detail(c))
        layout.addWidget(view_button)

        confirm_button = QPushButton(self._translator.tr("common-confirm"))
        confirm_button.setToolTip(self._translator.tr("event-manager-confirm-tooltip"))
        confirm_button.setEnabled(candidate.status != "confirmed")
        confirm_button.clicked.connect(
            lambda _checked, i=candidate.id: self._confirm_candidate(i)
        )
        layout.addWidget(confirm_button)

        dismiss_button = QPushButton(self._translator.tr("common-dismiss"))
        dismiss_button.setToolTip(self._translator.tr("event-manager-dismiss-tooltip"))
        dismiss_button.setEnabled(candidate.status != "dismissed")
        dismiss_button.clicked.connect(
            lambda _checked, i=candidate.id: self._dismiss_candidate(i)
        )
        layout.addWidget(dismiss_button)

        return actions

    def _confirm_candidate(self, event_candidate_id: int) -> None:
        self._events.confirm(event_candidate_id)
        self._reload_candidates()

    def _dismiss_candidate(self, event_candidate_id: int) -> None:
        self._events.dismiss(event_candidate_id)
        self._reload_candidates()

    def _show_detail(self, candidate: EventCandidate) -> None:
        dialog = _build_detail_dialog(candidate, self._translator, self)
        dialog.exec()


def _build_detail_dialog(candidate: EventCandidate, translator: Translator, parent: QWidget) -> QDialog:
    """Build a real, read-only dialog showing every extracted field."""
    event = candidate.event
    dialog = QDialog(parent)
    dialog.setWindowTitle(event.title)
    dialog.resize(560, 520)
    layout = QVBoxLayout(dialog)

    title = QLabel(event.title)
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
        (translator.tr("event-manager-detail-alternate-names"), ", ".join(event.alternate_names) or none_text),
        (translator.tr("taxonomy-dim-subject"), event.subject),
        (translator.tr("event-manager-detail-date-hijri"), event.date_hijri or unknown_text),
        (translator.tr("event-manager-detail-date-gregorian"), event.date_gregorian or unknown_text),
        (translator.tr("event-manager-detail-location"), event.location or unknown_text),
        (translator.tr("event-manager-detail-background"), event.background),
        (translator.tr("event-manager-detail-summary"), event.summary),
        (translator.tr("event-manager-detail-key-figures"), ", ".join(event.key_figures) or none_text),
        (translator.tr("event-manager-detail-quoted-excerpt"), event.quoted_excerpt),
        (translator.tr("event-manager-detail-citation"), event.citation),
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
