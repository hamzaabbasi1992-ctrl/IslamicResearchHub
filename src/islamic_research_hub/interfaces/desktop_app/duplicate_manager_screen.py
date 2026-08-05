"""Duplicate Manager screen: review real cross-library duplicate candidates.

Split out of `import_screen.py` (desktop UI redesign, Milestone 4). Compare
and the bulk empty-stub cleanup are real, backed by
`DuplicateCandidateRepository`/`BookComparisonRepository` exactly as before.
Dismiss persists to `DuplicateCandidates.Status` (originally a client-side,
per-session-only set - Milestone 8 - upgraded once the repository grew a
real `Status` column): a dismissed pair stays hidden across restarts and
future "Scan for duplicates" re-runs, since it's a real review decision,
not a scan-run artifact. Merge is a disabled, honestly-labeled button: no
merge operation exists anywhere in the persistence layer, and inventing
one client-side would mean real data-mutation logic living in a UI screen
instead of a repository - out of scope for a UI-only refactor.
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
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
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
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        duplicates: DuplicateCandidateRepository | None = None,
        comparisons: BookComparisonRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._duplicates = duplicates or DuplicateCandidateRepository(database_path)
        self._comparisons = comparisons or BookComparisonRepository(database_path)
        self._scanning = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self._heading_label = _heading(self._translator.tr("duplicate-review"))
        layout.addWidget(self._heading_label)
        self._duplicate_status_label = QLabel()
        self._duplicate_status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._duplicate_status_label)

        button_row = QHBoxLayout()
        self._scan_button = QPushButton(self._translator.tr("duplicate-manager-scan"))
        self._scan_button.clicked.connect(self._run_scan)
        button_row.addWidget(self._scan_button)

        self._cleanup_button = QPushButton(self._translator.tr("duplicate-manager-cleanup"))
        self._cleanup_button.clicked.connect(self._run_cleanup)
        button_row.addWidget(self._cleanup_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._duplicate_table = QTableWidget(0, 5)
        self._duplicate_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._duplicate_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._duplicate_table.verticalHeader().setVisible(False)
        self._duplicate_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # Real UI fix: without a stretch factor, the table only claimed its
        # own natural (short) height, leaving a large dead gray area below
        # it on any real window - the table now claims the remaining
        # vertical space instead.
        layout.addWidget(self._duplicate_table, stretch=1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    def _table_header_labels(self) -> list[str]:
        return [
            self._translator.tr("event-manager-col-book"),
            self._translator.tr("citation-manager-col-library"),
            self._translator.tr("duplicate-manager-col-possible-duplicate"),
            self._translator.tr("citation-manager-col-library"),
            "",
        ]

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("duplicate-review"))
        self._scan_button.setText(self._translator.tr("duplicate-manager-scan"))
        self._cleanup_button.setText(self._translator.tr("duplicate-manager-cleanup"))
        self._duplicate_table.setHorizontalHeaderLabels(self._table_header_labels())
        if self._scanning:
            self._duplicate_status_label.setText(self._translator.tr("duplicate-manager-scanning"))
        else:
            self._reload_duplicates()

    def refresh(self) -> None:
        """Reload the duplicate-candidates table from the real database."""
        self._reload_duplicates()

    def _reload_duplicates(self) -> None:
        candidates = list(self._duplicates.list_candidates())
        self._duplicate_status_label.setText(
            self._translator.tr("citation-manager-candidates-awaiting").format(total=len(candidates))
        )
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

            book_title = book_summary.title if book_summary else self._translator.tr(
                "common-book-number"
            ).format(id=candidate.book_id)
            other_title = other_summary.title if other_summary else self._translator.tr(
                "common-book-number"
            ).format(id=candidate.duplicate_of_book_id)
            book_library = book_summary.library if book_summary else self._translator.tr("common-unknown")
            other_library = other_summary.library if other_summary else self._translator.tr("common-unknown")

            untitled = self._translator.tr("common-untitled")
            unknown = self._translator.tr("common-unknown")
            self._duplicate_table.setItem(row, 0, _readonly_item(book_title or untitled, rtl=True))
            self._duplicate_table.setItem(row, 1, _readonly_item(book_library or unknown))
            self._duplicate_table.setItem(row, 2, _readonly_item(other_title or untitled, rtl=True))
            self._duplicate_table.setItem(row, 3, _readonly_item(other_library or unknown))
            self._duplicate_table.setCellWidget(
                row, 4, self._build_candidate_actions(candidate.book_id, candidate.duplicate_of_book_id)
            )

    def _build_candidate_actions(self, book_id: int, duplicate_of_book_id: int) -> QWidget:
        actions = QWidget()
        layout = QHBoxLayout(actions)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        compare_button = QPushButton(self._translator.tr("duplicate-manager-compare"))
        compare_button.clicked.connect(
            lambda _checked, a=book_id, b=duplicate_of_book_id: self._show_comparison(a, b)
        )
        layout.addWidget(compare_button)

        dismiss_button = QPushButton(self._translator.tr("common-dismiss"))
        dismiss_button.setToolTip(self._translator.tr("duplicate-manager-dismiss-tooltip"))
        dismiss_button.clicked.connect(
            lambda _checked, a=book_id, b=duplicate_of_book_id: self._dismiss_candidate(a, b)
        )
        layout.addWidget(dismiss_button)

        merge_button = QPushButton(self._translator.tr("duplicate-manager-merge"))
        merge_button.setEnabled(False)
        merge_button.setToolTip(self._translator.tr("duplicate-manager-merge-tooltip"))
        layout.addWidget(merge_button)

        return actions

    def _dismiss_candidate(self, book_id: int, duplicate_of_book_id: int) -> None:
        """Persist a candidate pair as reviewed-and-not-a-duplicate."""
        self._duplicates.dismiss(book_id, duplicate_of_book_id)
        self._reload_duplicates()

    def _run_scan(self) -> None:
        self._scanning = True
        self._duplicate_status_label.setText(self._translator.tr("duplicate-manager-scanning"))
        self._duplicates.detect_and_store()
        self._scanning = False
        self._reload_duplicates()

    def _run_cleanup(self) -> None:
        removed = self._duplicates.resolve_empty_stub_duplicates()
        self._reload_duplicates()
        remaining = self._duplicate_status_label.text()
        self._duplicate_status_label.setText(
            self._translator.tr("duplicate-manager-cleanup-result").format(
                removed=removed, remaining=remaining
            )
        )
        if removed:
            self.duplicates_resolved.emit()

    def _show_comparison(self, book_id_a: int, book_id_b: int) -> None:
        """Compute and show a real page-level comparison between two candidates."""
        result = self._comparisons.compare(book_id_a, book_id_b)
        dialog = _build_comparison_dialog(result, self._translator, self)
        dialog.exec()


def _build_comparison_dialog(result: BookComparisonResult, translator: Translator, parent: QWidget) -> QDialog:
    """Build a real, read-only dialog showing a page-level book comparison."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(translator.tr("duplicate-manager-compare-title"))
    dialog.resize(640, 520)
    layout = QVBoxLayout(dialog)

    untitled = translator.tr("common-untitled")
    title = QLabel(
        translator.tr("duplicate-manager-compare-vs").format(
            a=result.title_a or untitled, b=result.title_b or untitled
        )
    )
    title.setWordWrap(True)
    title.setStyleSheet(f"font-size: 15px; font-weight: 700; {RTL_TEXT_STYLE}")
    layout.addWidget(title)

    if result.overall_similarity is None:
        summary_text = translator.tr("duplicate-manager-compare-no-overlap").format(
            a=result.page_count_a, b=result.page_count_b
        )
    else:
        summary_text = translator.tr("duplicate-manager-compare-summary").format(
            a=result.page_count_a,
            b=result.page_count_b,
            common=result.common_page_count,
            similarity=f"{result.overall_similarity:.1%}",
            differing=len(result.differing_pages),
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
            translator.tr("duplicate-manager-compare-no-differences")
            if result.common_page_count
            else translator.tr("duplicate-manager-compare-nothing")
        )
        content_layout.addWidget(empty)
    empty_content_text = translator.tr("duplicate-manager-compare-empty-content")
    for entry in result.differing_pages:
        page_frame = QFrame()
        page_frame.setObjectName("settingsBlock")
        page_layout = QVBoxLayout(page_frame)
        header = QLabel(
            translator.tr("duplicate-manager-compare-page-header").format(
                page=entry.page_number, similarity=f"{entry.similarity:.1%}"
            )
        )
        header.setStyleSheet(f"font-weight: 600; {MUTED_LABEL_STYLE}")
        page_layout.addWidget(header)
        text_a = QLabel(entry.content_a or empty_content_text)
        text_a.setWordWrap(True)
        text_a.setStyleSheet(f"font-size: {Type.BODY_SM}px; {RTL_TEXT_STYLE}")
        page_layout.addWidget(text_a)
        text_b = QLabel(entry.content_b or empty_content_text)
        text_b.setWordWrap(True)
        text_b.setStyleSheet(f"font-size: {Type.BODY_SM}px; {RTL_TEXT_STYLE}")
        page_layout.addWidget(text_b)
        content_layout.addWidget(page_frame)
    content_layout.addStretch(1)
    scroll_area.setWidget(content)
    layout.addWidget(scroll_area, stretch=1)

    close_button = QPushButton(translator.tr("common-close"))
    close_button.clicked.connect(dialog.accept)
    layout.addWidget(close_button)

    return dialog
