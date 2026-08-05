"""Digital Preservation Report screen: real duplicate/incompleteness gaps.

A report over already-built detection infrastructure
(`DuplicateCandidateRepository`, `PdfMatchCandidateRepository`), not new
detection logic - see `preservation_report_repository.py`'s own
docstring for what's deliberately out of scope (corrupted-file
tracking). Generation runs on a background `PreservationReportWorker`
(real, measured cost against the full corpus: well over two minutes),
mirroring `CitationManagerScreen`'s Scan button pattern - never
auto-computed on screen open.
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.infrastructure.persistence.preservation_report_repository import (
    REASON_NO_TEXT_NO_PDF,
    REASON_SPARSE_TEXT_NO_PDF_MATCH,
    IncompleteBook,
    PreservationReportRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading, _readonly_item
from islamic_research_hub.interfaces.desktop_app.preservation_report_worker import (
    PreservationReportWorker,
)
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE

_REASON_KEYS: dict[str, str] = {
    REASON_NO_TEXT_NO_PDF: "preservation-report-reason-no-text-no-pdf",
    REASON_SPARSE_TEXT_NO_PDF_MATCH: "preservation-report-reason-sparse-text-no-pdf-match",
}


class PreservationReportScreen(QWidget):
    """Show real duplicate/incompleteness gaps, generated on demand."""

    review_duplicates_requested = Signal()

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        repository: PreservationReportRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._repository = repository or PreservationReportRepository(database_path)
        self._worker: PreservationReportWorker | None = None
        self._pending_duplicates: int | None = None
        self._incomplete_books: tuple[IncompleteBook, ...] = ()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._heading_label = _heading(self._translator.tr("preservation-report-heading"))
        layout.addWidget(self._heading_label)

        button_row = QHBoxLayout()
        self._generate_button = QPushButton(self._translator.tr("preservation-report-generate"))
        self._generate_button.setToolTip(self._translator.tr("preservation-report-generate-tooltip"))
        self._generate_button.clicked.connect(self._run_generate)
        button_row.addWidget(self._generate_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._status_label = QLabel(self._translator.tr("preservation-report-idle"))
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._status_label)

        duplicates_row = QHBoxLayout()
        self._duplicates_summary_label = QLabel()
        self._duplicates_summary_label.setStyleSheet(MUTED_LABEL_STYLE)
        duplicates_row.addWidget(self._duplicates_summary_label)
        self._review_duplicates_button = QPushButton(
            self._translator.tr("preservation-report-review-duplicates")
        )
        self._review_duplicates_button.setVisible(False)
        self._review_duplicates_button.clicked.connect(self.review_duplicates_requested)
        duplicates_row.addWidget(self._review_duplicates_button)
        duplicates_row.addStretch(1)
        layout.addLayout(duplicates_row)

        self._incomplete_heading_label = _heading(
            self._translator.tr("preservation-report-incomplete-heading")
        )
        layout.addWidget(self._incomplete_heading_label)
        self._incomplete_count_label = QLabel()
        self._incomplete_count_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._incomplete_count_label.setWordWrap(True)
        layout.addWidget(self._incomplete_count_label)

        self._incomplete_table = QTableWidget(0, 4)
        self._incomplete_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._incomplete_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._incomplete_table.verticalHeader().setVisible(False)
        self._incomplete_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._incomplete_table, stretch=1)

        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self._translator.language_changed.connect(self._retranslate)

    def _table_header_labels(self) -> list[str]:
        return [
            self._translator.tr("event-manager-col-book"),
            self._translator.tr("search-detail-author"),
            self._translator.tr("citation-manager-col-library"),
            self._translator.tr("preservation-report-col-reason"),
        ]

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("preservation-report-heading"))
        self._generate_button.setText(self._translator.tr("preservation-report-generate"))
        self._generate_button.setToolTip(self._translator.tr("preservation-report-generate-tooltip"))
        self._review_duplicates_button.setText(
            self._translator.tr("preservation-report-review-duplicates")
        )
        self._incomplete_heading_label.setText(
            self._translator.tr("preservation-report-incomplete-heading")
        )
        self._incomplete_table.setHorizontalHeaderLabels(self._table_header_labels())
        if self._pending_duplicates is None:
            self._status_label.setText(self._translator.tr("preservation-report-idle"))
        else:
            self._render_report()

    def _run_generate(self) -> None:
        self._generate_button.setEnabled(False)
        self._status_label.setText(self._translator.tr("preservation-report-generating"))
        worker = PreservationReportWorker(self._repository, self)
        worker.report_ready.connect(self._on_report_ready)
        self._worker = worker
        worker.start()

    def _on_report_ready(self, pending_duplicates: int, incomplete_books: tuple) -> None:
        self._pending_duplicates = pending_duplicates
        self._incomplete_books = incomplete_books
        self._generate_button.setEnabled(True)
        self._status_label.setText("")
        self._render_report()

    def _render_report(self) -> None:
        tr = self._translator.tr
        self._duplicates_summary_label.setText(
            tr("preservation-report-duplicates-summary").format(count=self._pending_duplicates)
        )
        self._review_duplicates_button.setVisible(bool(self._pending_duplicates))

        if not self._incomplete_books:
            self._incomplete_count_label.setText(tr("preservation-report-incomplete-none"))
        else:
            self._incomplete_count_label.setText(
                tr("preservation-report-incomplete-count").format(count=len(self._incomplete_books))
            )
        self._incomplete_table.setRowCount(len(self._incomplete_books))
        untitled = tr("common-untitled")
        unknown_author = tr("common-unknown-author")
        unknown_library = tr("common-unknown-library")
        for row, book in enumerate(self._incomplete_books):
            self._incomplete_table.setItem(row, 0, _readonly_item(book.title or untitled, rtl=True))
            self._incomplete_table.setItem(row, 1, _readonly_item(book.author or unknown_author, rtl=True))
            self._incomplete_table.setItem(row, 2, _readonly_item(book.library or unknown_library))
            self._incomplete_table.setItem(
                row, 3, _readonly_item(tr(_REASON_KEYS.get(book.reason, book.reason)))
            )
