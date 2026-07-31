"""Duplicate Manager screen: review real cross-library duplicate candidates.

Split out of `import_screen.py` (desktop UI redesign, Milestone 4). Compare
and the bulk empty-stub cleanup are real, backed by
`DuplicateCandidateRepository`/`BookComparisonRepository` exactly as before.
Skip is a client-side, per-session dismissed-ID set (Milestone 8) - no
persistence-layer change, so it resets on restart, but a skipped pair
stays hidden even across a fresh "Scan for duplicates" within the same
session (skipping is a review decision, not a scan-run artifact). Merge
is a disabled, honestly-labeled button: no merge operation
exists anywhere in the persistence layer, and inventing one client-side
would mean real data-mutation logic living in a UI screen instead of a
repository - out of scope for a UI-only refactor.
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.domain.models.book_comparison import BookComparisonResult
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.book_comparison_repository import (
    BookComparisonRepository,
)
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading, _readonly_item
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE, Type


class DuplicateManagerScreen(QWidget):
    """Review real cross-library duplicate candidates and resolve empty-stub ones."""

    duplicates_resolved = Signal()
    """Emitted after a cleanup actually removes book(s) - listeners (the
    Libraries screen's book counts, the header's live stats) should refresh."""

    def __init__(
        self,
        database_path: Path,
        browser: BookBrowserRepository | None = None,
        duplicates: DuplicateCandidateRepository | None = None,
        comparisons: BookComparisonRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._browser = browser or BookBrowserRepository(database_path)
        self._duplicates = duplicates or DuplicateCandidateRepository(database_path)
        self._comparisons = comparisons or BookComparisonRepository(database_path)
        self._dismissed_this_session: set[tuple[int, int]] = set()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(_heading("Duplicate review"))
        self._duplicate_status_label = QLabel()
        self._duplicate_status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._duplicate_status_label)

        button_row = QHBoxLayout()
        scan_button = QPushButton("Scan for duplicates")
        scan_button.clicked.connect(self._run_scan)
        button_row.addWidget(scan_button)

        self._cleanup_button = QPushButton("Remove empty-stub duplicates")
        self._cleanup_button.clicked.connect(self._run_cleanup)
        button_row.addWidget(self._cleanup_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._duplicate_table = QTableWidget(0, 5)
        self._duplicate_table.setHorizontalHeaderLabels(
            ["Book", "Library", "Possible duplicate of", "Library", ""]
        )
        self._duplicate_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._duplicate_table.verticalHeader().setVisible(False)
        self._duplicate_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._duplicate_table)

        layout.addStretch(1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()

    def refresh(self) -> None:
        """Reload the duplicate-candidates table from the real database."""
        self._reload_duplicates()

    def _reload_duplicates(self) -> None:
        all_candidates = self._duplicates.list_candidates()
        candidates = [
            candidate
            for candidate in all_candidates
            if (candidate.book_id, candidate.duplicate_of_book_id)
            not in self._dismissed_this_session
        ]
        hidden_count = len(all_candidates) - len(candidates)
        status = f"{len(candidates)} candidate(s) awaiting review"
        if hidden_count:
            status += f" ({hidden_count} hidden this session)"
        self._duplicate_status_label.setText(status)
        self._duplicate_table.setRowCount(len(candidates))

        # One bulk lookup for every book involved, instead of calling
        # get_book_source()/get_book_detail() (which fetches a book's
        # *entire* page content) twice per candidate - confirmed as a real
        # ~25s startup cost against the production database (2,302 real
        # candidates x 4 per-book queries each).
        book_ids = tuple(
            {candidate.book_id for candidate in candidates}
            | {candidate.duplicate_of_book_id for candidate in candidates}
        )
        summaries = self._browser.list_books_by_ids(book_ids)

        for row, candidate in enumerate(candidates):
            book_summary = summaries.get(candidate.book_id)
            other_summary = summaries.get(candidate.duplicate_of_book_id)

            book_title = book_summary.title if book_summary else f"Book {candidate.book_id}"
            other_title = (
                other_summary.title if other_summary else f"Book {candidate.duplicate_of_book_id}"
            )
            book_library = book_summary.library if book_summary else "Unknown"
            other_library = other_summary.library if other_summary else "Unknown"

            self._duplicate_table.setItem(row, 0, _readonly_item(book_title or "(untitled)", rtl=True))
            self._duplicate_table.setItem(row, 1, _readonly_item(book_library or "Unknown"))
            self._duplicate_table.setItem(row, 2, _readonly_item(other_title or "(untitled)", rtl=True))
            self._duplicate_table.setItem(row, 3, _readonly_item(other_library or "Unknown"))
            self._duplicate_table.setCellWidget(
                row, 4, self._build_candidate_actions(candidate.book_id, candidate.duplicate_of_book_id)
            )

    def _build_candidate_actions(self, book_id: int, duplicate_of_book_id: int) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        compare_button = QPushButton("Compare")
        compare_button.clicked.connect(
            lambda _checked, a=book_id, b=duplicate_of_book_id: self._show_comparison(a, b)
        )
        layout.addWidget(compare_button)

        skip_button = QPushButton("Skip")
        skip_button.setToolTip("Hide this pair for the rest of this session.")
        skip_button.clicked.connect(
            lambda _checked, a=book_id, b=duplicate_of_book_id: self._dismiss_candidate(a, b)
        )
        layout.addWidget(skip_button)

        merge_button = QPushButton("Merge")
        merge_button.setEnabled(False)
        merge_button.setToolTip("Coming soon - no merge operation exists yet.")
        layout.addWidget(merge_button)

        return actions

    def _dismiss_candidate(self, book_id: int, duplicate_of_book_id: int) -> None:
        """Hide a candidate pair for the rest of this session (no persistence)."""
        self._dismissed_this_session.add((book_id, duplicate_of_book_id))
        self._reload_duplicates()

    def _run_scan(self) -> None:
        self._duplicate_status_label.setText("Scanning...")
        self._duplicates.detect_and_store()
        self._reload_duplicates()

    def _run_cleanup(self) -> None:
        removed = self._duplicates.resolve_empty_stub_duplicates()
        self._reload_duplicates()
        remaining = self._duplicate_status_label.text()
        self._duplicate_status_label.setText(f"Removed {removed} empty-stub duplicate(s). {remaining}")
        if removed:
            self.duplicates_resolved.emit()

    def _show_comparison(self, book_id_a: int, book_id_b: int) -> None:
        """Compute and show a real page-level comparison between two candidates."""
        result = self._comparisons.compare(book_id_a, book_id_b)
        dialog = _build_comparison_dialog(result, self)
        dialog.exec()


def _build_comparison_dialog(result: BookComparisonResult, parent: QWidget) -> QDialog:
    """Build a real, read-only dialog showing a page-level book comparison."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Compare books")
    dialog.resize(640, 520)
    layout = QVBoxLayout(dialog)

    title = QLabel(f"{result.title_a or '(untitled)'}  vs  {result.title_b or '(untitled)'}")
    title.setWordWrap(True)
    title.setStyleSheet(f"font-size: 15px; font-weight: 700; {RTL_TEXT_STYLE}")
    layout.addWidget(title)

    if result.overall_similarity is None:
        summary_text = (
            f"{result.page_count_a} vs {result.page_count_b} page(s) - "
            "no overlapping page numbers, so no direct page-by-page comparison "
            "is possible (these books' pagination doesn't line up)."
        )
    else:
        summary_text = (
            f"{result.page_count_a} vs {result.page_count_b} page(s), "
            f"{result.common_page_count} page(s) in common, "
            f"{result.overall_similarity:.1%} average similarity on those pages, "
            f"{len(result.differing_pages)} page(s) differ meaningfully."
        )
    summary = QLabel(summary_text)
    summary.setWordWrap(True)
    summary.setStyleSheet(MUTED_LABEL_STYLE)
    layout.addWidget(summary)

    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    content = QWidget()
    content_layout = QVBoxLayout(content)
    if not result.differing_pages:
        empty = EmptyStateLabel(
            "No meaningfully differing pages."
            if result.common_page_count
            else "Nothing to compare."
        )
        content_layout.addWidget(empty)
    for entry in result.differing_pages:
        page_frame = QFrame()
        page_frame.setObjectName("settingsBlock")
        page_layout = QVBoxLayout(page_frame)
        header = QLabel(f"Page {entry.page_number} - {entry.similarity:.1%} similar")
        header.setStyleSheet(f"font-weight: 600; {MUTED_LABEL_STYLE}")
        page_layout.addWidget(header)
        text_a = QLabel(entry.content_a or "(empty)")
        text_a.setWordWrap(True)
        text_a.setStyleSheet(f"font-size: {Type.BODY_SM}px; {RTL_TEXT_STYLE}")
        page_layout.addWidget(text_a)
        text_b = QLabel(entry.content_b or "(empty)")
        text_b.setWordWrap(True)
        text_b.setStyleSheet(f"font-size: {Type.BODY_SM}px; {RTL_TEXT_STYLE}")
        page_layout.addWidget(text_b)
        content_layout.addWidget(page_frame)
    content_layout.addStretch(1)
    scroll_area.setWidget(content)
    layout.addWidget(scroll_area, stretch=1)

    close_button = QPushButton("Close")
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)

    return dialog
