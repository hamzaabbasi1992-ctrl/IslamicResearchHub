"""Citation Manager screen: review real detected citations between owned books.

Mirrors `duplicate_manager_screen.py` exactly - same table-of-candidates/
Dismiss/Scan shape, backed by `CitationCandidateRepository` instead of
`DuplicateCandidateRepository`. The one real difference: detection is
measured at 15 minutes (warm cache) to 2+ hours (cold cache) against the
full production corpus - far too long for a synchronous button click, so
Scan runs via `CitationDetectionWorker` on a background `QThread` instead
of calling `detect_and_store()` directly on the GUI thread.
"""

from pathlib import Path

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

from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.citation_candidate_repository import (
    CitationCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.citation_detection_worker import (
    CitationDetectionWorker,
)
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading, _readonly_item
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE

PAGE_SIZE = 100
"""Real production scale (329,202+ real candidates found scanning the
full corpus) makes loading everything into one QTableWidget impractical
- confirmed directly, the app took a very long time just to populate the
table on startup. Paged like any real review list at this scale."""


class CitationManagerScreen(QWidget):
    """Review real, literal-phrase citation candidates between owned books."""

    def __init__(
        self,
        database_path: Path,
        browser: BookBrowserRepository | None = None,
        citations: CitationCandidateRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._browser = browser or BookBrowserRepository(database_path)
        self._citations = citations or CitationCandidateRepository(database_path)
        self._scan_worker: CitationDetectionWorker | None = None
        self._page_index = 0

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(_heading("Citation review"))
        self._status_label = QLabel()
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._status_label)

        button_row = QHBoxLayout()
        self._scan_button = QPushButton("Scan for citations")
        self._scan_button.setToolTip(
            "Real measured runtime against the full library: 15 minutes to "
            "2+ hours - runs in the background, the app stays usable."
        )
        self._scan_button.clicked.connect(self._run_scan)
        button_row.addWidget(self._scan_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._citation_table = QTableWidget(0, 5)
        self._citation_table.setHorizontalHeaderLabels(
            ["Citing book", "Library", "Cites", "Library", ""]
        )
        self._citation_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._citation_table.verticalHeader().setVisible(False)
        self._citation_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._citation_table, stretch=1)

        pagination_row = QHBoxLayout()
        self._previous_page_button = QPushButton("Previous")
        self._previous_page_button.clicked.connect(self._go_to_previous_page)
        pagination_row.addWidget(self._previous_page_button)
        self._page_label = QLabel()
        self._page_label.setStyleSheet(MUTED_LABEL_STYLE)
        pagination_row.addWidget(self._page_label)
        self._next_page_button = QPushButton("Next")
        self._next_page_button.clicked.connect(self._go_to_next_page)
        pagination_row.addWidget(self._next_page_button)
        pagination_row.addStretch(1)
        layout.addLayout(pagination_row)

        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()

    def refresh(self) -> None:
        """Reload the citation-candidates table from the real database."""
        self._reload_candidates()

    def _go_to_previous_page(self) -> None:
        if self._page_index > 0:
            self._page_index -= 1
            self._reload_candidates()

    def _go_to_next_page(self) -> None:
        self._page_index += 1
        self._reload_candidates()

    def _reload_candidates(self) -> None:
        total = self._citations.count_candidates()
        page_count = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page_index = min(self._page_index, page_count - 1)
        candidates = list(
            self._citations.list_candidates(limit=PAGE_SIZE, offset=self._page_index * PAGE_SIZE)
        )
        self._status_label.setText(f"{total} candidate(s) awaiting review")
        start = self._page_index * PAGE_SIZE + 1 if candidates else 0
        end = self._page_index * PAGE_SIZE + len(candidates)
        self._page_label.setText(f"{start}-{end} of {total}")
        self._previous_page_button.setEnabled(self._page_index > 0)
        self._next_page_button.setEnabled(end < total)
        self._citation_table.setRowCount(len(candidates))

        # One bulk lookup for every book involved, matching
        # DuplicateManagerScreen's own documented fix for a real ~25s N+1
        # cost against a large candidate table.
        book_ids = tuple(
            {candidate.citing_book_id for candidate in candidates}
            | {candidate.cited_book_id for candidate in candidates}
        )
        summaries = self._browser.list_books_by_ids(book_ids)

        for row, candidate in enumerate(candidates):
            citing_summary = summaries.get(candidate.citing_book_id)
            cited_summary = summaries.get(candidate.cited_book_id)

            citing_title = (
                citing_summary.title if citing_summary else f"Book {candidate.citing_book_id}"
            )
            cited_title = (
                cited_summary.title if cited_summary else f"Book {candidate.cited_book_id}"
            )
            citing_library = citing_summary.library if citing_summary else "Unknown"
            cited_library = cited_summary.library if cited_summary else "Unknown"

            self._citation_table.setItem(row, 0, _readonly_item(citing_title or "(untitled)", rtl=True))
            self._citation_table.setItem(row, 1, _readonly_item(citing_library or "Unknown"))
            self._citation_table.setItem(row, 2, _readonly_item(cited_title or "(untitled)", rtl=True))
            self._citation_table.setItem(row, 3, _readonly_item(cited_library or "Unknown"))
            self._citation_table.setCellWidget(
                row,
                4,
                self._build_candidate_actions(
                    candidate.citing_book_id, candidate.citing_page_no, candidate.cited_book_id
                ),
            )

    def _build_candidate_actions(
        self, citing_book_id: int, citing_page_no: int, cited_book_id: int
    ) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        dismiss_button = QPushButton("Dismiss")
        dismiss_button.setToolTip("Confirm this isn't a real citation (permanent).")
        dismiss_button.clicked.connect(
            lambda _checked, c=citing_book_id, p=citing_page_no, d=cited_book_id: self._dismiss_candidate(
                c, p, d
            )
        )
        layout.addWidget(dismiss_button)

        dismiss_all_button = QPushButton("Dismiss all from this book")
        dismiss_all_button.setToolTip(
            "Dismiss every citation this book makes to the same cited book at once."
        )
        dismiss_all_button.clicked.connect(
            lambda _checked, c=citing_book_id, d=cited_book_id: self._dismiss_pair(c, d)
        )
        layout.addWidget(dismiss_all_button)

        return actions

    def _dismiss_candidate(self, citing_book_id: int, citing_page_no: int, cited_book_id: int) -> None:
        self._citations.dismiss(citing_book_id, citing_page_no, cited_book_id)
        self._reload_candidates()

    def _dismiss_pair(self, citing_book_id: int, cited_book_id: int) -> None:
        self._citations.dismiss_pair(citing_book_id, cited_book_id)
        self._reload_candidates()

    def _run_scan(self) -> None:
        self._scan_button.setEnabled(False)
        self._status_label.setText("Scanning... this can take a while (see the Scan button's tooltip).")
        worker = CitationDetectionWorker(self._citations, self)
        worker.detection_progress.connect(self._on_scan_progress)
        worker.detection_finished.connect(self._on_scan_finished)
        self._scan_worker = worker
        worker.start()

    def _on_scan_progress(self, done: int, total: int) -> None:
        self._status_label.setText(f"Scanning... {done}/{total} anchor(s) processed.")

    def _on_scan_finished(self, count: int) -> None:
        self._scan_button.setEnabled(True)
        self._reload_candidates()
