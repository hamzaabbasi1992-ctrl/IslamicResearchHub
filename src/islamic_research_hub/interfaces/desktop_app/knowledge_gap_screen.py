"""Knowledge Gap screen: surface real corpus coverage gaps.

"Only N books cover this subject/author/publisher/language" - a real
research signal computed directly from real taxonomy link counts
already in the database (Phase 8's taxonomy population), not a new
data-collection problem. Follows `TaxonomyBrowserScreen`'s left-pane
dimension-buttons / right-pane results-on-click shape closely, since
this is a report *over* the same taxonomy data, not a separate concept.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.application.knowledge_gap_analysis import (
    DEFAULT_LOW_COVERAGE_THRESHOLD,
    TermCoverage,
    find_low_coverage_terms,
)
from islamic_research_hub.domain.models.book_summary import BookSummary
from islamic_research_hub.domain.models.taxonomy import TaxonomyTerm
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import TAXONOMY_DIMENSIONS
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE, Type

_DIMENSION_KEYS: dict[str, str] = {
    "subject": "taxonomy-dim-subject",
    "author": "taxonomy-dim-author",
    "language": "taxonomy-dim-language",
    "publisher": "taxonomy-dim-publisher",
    "madhhab": "taxonomy-dim-madhhab",
    "region": "taxonomy-dim-region",
    "personality": "taxonomy-dim-personality",
    "event": "taxonomy-dim-event",
    "tag": "taxonomy-dim-tag",
}
_DIMENSION_COLUMNS = 3


class KnowledgeGapScreen(QWidget):
    """Show real, low-coverage taxonomy terms per dimension - a research signal, not a judgment."""

    open_in_viewer_requested = Signal(int, int)  # book_id, page_number

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        taxonomy: TaxonomyRepository | None = None,
        browser: BookBrowserRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._taxonomy = taxonomy or TaxonomyRepository(database_path)
        self._browser = browser or BookBrowserRepository(database_path)
        self._current_dimension = TAXONOMY_DIMENSIONS[0]
        self._current_term_id: int | None = None
        self._current_term_label: str | None = None
        self._dimension_buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_pane())
        splitter.addWidget(self._build_results_pane())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        outer.addWidget(splitter)

        self._populated_dimensions = self._load_populated_dimensions()
        self._refresh_dimension_buttons()
        if self._populated_dimensions:
            self._select_dimension(self._first_populated_dimension())
        else:
            self._empty_dimension_label.setText(
                self._translator.tr("taxonomy-no-data-any-dimension")
            )
            self._empty_dimension_label.setVisible(True)

        self._translator.language_changed.connect(self._retranslate)

    # ------------------------------------------------------------- i18n

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("knowledge-gap-heading"))
        self._threshold_label.setText(self._translator.tr("knowledge-gap-threshold-label"))
        for code, button in self._dimension_buttons.items():
            button.setText(self._translator.tr(_DIMENSION_KEYS.get(code, code)))
        self._refresh_dimension_buttons()
        if not self._populated_dimensions:
            self._empty_dimension_label.setText(
                self._translator.tr("taxonomy-no-data-any-dimension")
            )
        else:
            self._reload_gap_list()
        if self._current_term_id is not None and self._current_term_label is not None:
            self._show_books_for_term(self._current_term_id, self._current_term_label)
        else:
            self._clear_results(self._translator.tr("taxonomy-pick-term"))

    # -------------------------------------------------------------- left

    def _build_left_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("searchLeftPane")
        pane.setMinimumWidth(280)
        pane.setMaximumWidth(380)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._heading_label = _heading(self._translator.tr("knowledge-gap-heading"))
        layout.addWidget(self._heading_label)

        layout.addLayout(self._build_dimension_grid())

        threshold_row = QHBoxLayout()
        self._threshold_label = QLabel(self._translator.tr("knowledge-gap-threshold-label"))
        threshold_row.addWidget(self._threshold_label)
        self._threshold_spinbox = QSpinBox()
        self._threshold_spinbox.setMinimum(1)
        self._threshold_spinbox.setMaximum(50)
        self._threshold_spinbox.setValue(DEFAULT_LOW_COVERAGE_THRESHOLD)
        self._threshold_spinbox.valueChanged.connect(lambda _value: self._reload_gap_list())
        threshold_row.addWidget(self._threshold_spinbox)
        threshold_row.addStretch(1)
        layout.addLayout(threshold_row)

        self._empty_dimension_label = QLabel()
        self._empty_dimension_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._empty_dimension_label.setWordWrap(True)
        self._empty_dimension_label.setVisible(False)
        layout.addWidget(self._empty_dimension_label)

        self._gap_list = QListWidget()
        self._gap_list.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._gap_list.itemClicked.connect(self._on_gap_item_clicked)
        layout.addWidget(self._gap_list, stretch=1)

        return pane

    def _build_dimension_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(4)
        for index, code in enumerate(TAXONOMY_DIMENSIONS):
            button = QPushButton(self._translator.tr(_DIMENSION_KEYS.get(code, code)))
            button.setCheckable(True)
            button.setObjectName("navTab")
            button.clicked.connect(lambda _checked, c=code: self._select_dimension(c))
            grid.addWidget(button, index // _DIMENSION_COLUMNS, index % _DIMENSION_COLUMNS)
            self._dimension_buttons[code] = button
        return grid

    def _load_populated_dimensions(self) -> set[str]:
        """Return the dimension codes that have at least one real term.

        Mirrors `TaxonomyBrowserScreen._load_populated_dimensions()`
        exactly - same honest degradation on an unmigrated database.
        """
        if not self._taxonomy_dimensions_table_exists():
            return set()
        return {code for code in TAXONOMY_DIMENSIONS if self._taxonomy.list_terms(code)}

    def _taxonomy_dimensions_table_exists(self) -> bool:
        with closing(sqlite3.connect(self._database_path)) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'TaxonomyDimensions'"
                ).fetchone()
                is not None
            )

    def _first_populated_dimension(self) -> str:
        for code in TAXONOMY_DIMENSIONS:
            if code in self._populated_dimensions:
                return code
        return TAXONOMY_DIMENSIONS[0]

    def _refresh_dimension_buttons(self) -> None:
        for code, button in self._dimension_buttons.items():
            populated = code in self._populated_dimensions
            button.setEnabled(populated)
            button.setToolTip("" if populated else self._translator.tr("taxonomy-no-data-for-dimension"))
            button.setChecked(code == self._current_dimension)

    def _select_dimension(self, code: str) -> None:
        if code not in self._populated_dimensions:
            return
        self._current_dimension = code
        self._current_term_id = None
        self._current_term_label = None
        self._refresh_dimension_buttons()
        self._clear_results(self._translator.tr("taxonomy-pick-term"))
        self._reload_gap_list()

    def _reload_gap_list(self) -> None:
        self._gap_list.clear()
        if self._current_dimension not in self._populated_dimensions:
            return
        term_counts = self._taxonomy.list_term_book_counts(self._current_dimension)
        coverages = tuple(
            _term_coverage(term, count)
            for term, count in term_counts
            if _term_name(term) is not None
        )
        low_coverage = find_low_coverage_terms(coverages, threshold=self._threshold_spinbox.value())
        if not low_coverage:
            self._empty_dimension_label.setText(self._translator.tr("knowledge-gap-no-gaps-found"))
            self._empty_dimension_label.setVisible(True)
            return
        self._empty_dimension_label.setVisible(False)
        for coverage in low_coverage:
            item = QListWidgetItem(
                self._translator.tr("knowledge-gap-list-row").format(
                    name=coverage.name, count=coverage.book_count
                )
            )
            item.setData(Qt.ItemDataRole.UserRole, (coverage.term_id, coverage.name))
            self._gap_list.addItem(item)

    def _on_gap_item_clicked(self, item: QListWidgetItem) -> None:
        term_id, term_label = item.data(Qt.ItemDataRole.UserRole)
        self._show_books_for_term(term_id, term_label)

    # ----------------------------------------------------------- results

    def _build_results_pane(self) -> QWidget:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        self._results_layout = QVBoxLayout(content)
        self._results_layout.setContentsMargins(16, 16, 16, 16)
        self._results_layout.setSpacing(10)
        self._status_label = EmptyStateLabel(
            self._translator.tr("taxonomy-pick-term"), centered=True
        )
        self._results_layout.addWidget(self._status_label, stretch=1)
        scroll_area.setWidget(content)
        return scroll_area

    def _clear_results(self, status_text: str) -> None:
        self._empty_results_layout()
        self._status_label = EmptyStateLabel(status_text, centered=True)
        self._results_layout.addWidget(self._status_label, stretch=1)

    def _empty_results_layout(self) -> None:
        while self._results_layout.count():
            item = self._results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_books_for_term(self, term_id: int, term_label: str) -> None:
        self._current_term_id = term_id
        self._current_term_label = term_label
        book_ids = self._taxonomy.list_books_for_term(term_id)
        self._empty_results_layout()
        if not book_ids:
            self._status_label = EmptyStateLabel(
                self._translator.tr("taxonomy-no-books-linked").format(term=term_label),
                centered=True,
            )
            self._results_layout.addWidget(self._status_label, stretch=1)
            return
        summaries = self._browser.list_books_by_ids(book_ids)
        self._status_label = QLabel(
            self._translator.tr("taxonomy-books-in-term").format(term=term_label, count=len(book_ids))
        )
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._results_layout.addWidget(self._status_label)
        for book_id in book_ids:
            summary = summaries.get(book_id)
            if summary is not None:
                self._results_layout.addWidget(self._build_book_card(summary))
        self._results_layout.addStretch(1)

    def _build_book_card(self, summary: BookSummary) -> QFrame:
        card = QFrame()
        card.setObjectName("resultCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)

        title = QLabel(summary.title or self._translator.tr("common-untitled"))
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        card_layout.addWidget(title)

        meta = QLabel(
            " · ".join(
                [
                    summary.author or self._translator.tr("common-unknown-author"),
                    summary.library or self._translator.tr("common-unknown-library"),
                ]
            )
        )
        meta.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.BODY_SM}px;")
        card_layout.addWidget(meta)

        open_row = QHBoxLayout()
        read_button = QPushButton(self._translator.tr("common-read-in-app"))
        read_button.setIcon(button_icon("viewer"))
        read_button.setIconSize(button_icon_size())
        read_button.clicked.connect(
            lambda _checked, book_id=summary.book_id: self.open_in_viewer_requested.emit(book_id, 1)
        )
        open_row.addWidget(read_button)
        open_row.addStretch(1)
        card_layout.addLayout(open_row)

        return card


def _term_name(term: TaxonomyTerm) -> str | None:
    return term.names.get("ar") or next(iter(term.names.values()), None)


def _term_coverage(term: TaxonomyTerm, count: int) -> TermCoverage:
    name = _term_name(term) or f"#{term.term_id}"
    return TermCoverage(term_id=term.term_id, name=name, book_count=count)
