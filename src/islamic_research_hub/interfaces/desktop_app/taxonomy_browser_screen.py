"""Taxonomy Browser screen: browse the library by real taxonomy dimension.

New standalone rail screen (Phase 8, priority 3) - not a `SearchScreen`
sub-tab, since it needs to cover every populated taxonomy dimension
(subject/author/language/publisher today), not just Categories. Follows
`DuplicateManagerScreen`'s DI-with-real-defaults constructor pattern and
`SearchScreen`'s `QTreeWidget` tree/search-filter pattern exactly, reusing
`BookBrowserRepository.list_books_by_ids()` (the same bulk-hydration
method `DuplicateManagerScreen` already uses) rather than one query per
book - deliberately avoiding the N+1 pattern fixed there.

Per-node book counts are not shown: unlike `CategoryNode` (which already
carries a real, pre-computed `book_count`), `TaxonomyTerm` doesn't, and
computing one via `list_books_for_term()` per tree node would be exactly
the N+1 query shape already found and fixed once this session - left out
deliberately rather than reintroduced.
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
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.domain.models.book_summary import BookSummary
from islamic_research_hub.domain.models.taxonomy import TaxonomyTerm
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import TAXONOMY_DIMENSIONS
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import TaxonomyRepository
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE, Type
from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text

_DIMENSION_LABELS: dict[str, str] = {
    "subject": "Subject",
    "author": "Author",
    "language": "Language",
    "publisher": "Publisher",
    "madhhab": "Madhhab",
    "region": "Region",
    "personality": "Personality",
    "event": "Event",
    "tag": "Tag",
}
_DIMENSION_COLUMNS = 3


class TaxonomyBrowserScreen(QWidget):
    """Browse and search the library's real taxonomy dimensions."""

    open_in_viewer_requested = Signal(int, int)  # book_id, page_number

    def __init__(
        self,
        database_path: Path,
        taxonomy: TaxonomyRepository | None = None,
        browser: BookBrowserRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._taxonomy = taxonomy or TaxonomyRepository(database_path)
        self._browser = browser or BookBrowserRepository(database_path)
        self._current_dimension = TAXONOMY_DIMENSIONS[0]
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
                "No taxonomy data yet - run the taxonomy population step first."
            )
            self._empty_dimension_label.setVisible(True)

    # -------------------------------------------------------------- left

    def _build_left_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("searchLeftPane")
        pane.setMinimumWidth(260)
        pane.setMaximumWidth(340)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(_heading("Taxonomy"))

        dimension_grid = QGridLayout()
        dimension_grid.setSpacing(4)
        for index, code in enumerate(TAXONOMY_DIMENSIONS):
            button = QPushButton(_DIMENSION_LABELS.get(code, code))
            button.setCheckable(True)
            button.setObjectName("navTab")
            button.clicked.connect(lambda _checked, c=code: self._select_dimension(c))
            dimension_grid.addWidget(button, index // _DIMENSION_COLUMNS, index % _DIMENSION_COLUMNS)
            self._dimension_buttons[code] = button
        layout.addLayout(dimension_grid)

        self._empty_dimension_label = QLabel()
        self._empty_dimension_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._empty_dimension_label.setWordWrap(True)
        self._empty_dimension_label.setVisible(False)
        layout.addWidget(self._empty_dimension_label)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Search within taxonomy...")
        self._filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_edit)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._tree.itemClicked.connect(self._on_term_clicked)
        layout.addWidget(self._tree, stretch=1)

        return pane

    def _load_populated_dimensions(self) -> set[str]:
        """Return the dimension codes that have at least one real term.

        One cheap read per dimension (9 total, run once at screen
        construction) - not a per-tree-node cost, unlike book counts.
        Honestly returns empty (no dimension selectable) rather than
        crashing on a database that hasn't run migration 6 yet - the
        same "not migrated yet" degradation `verify_database_cli.py`
        already uses elsewhere.
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
            button.setToolTip("" if populated else "No data yet for this dimension.")
            button.setChecked(code == self._current_dimension)

    def _select_dimension(self, code: str) -> None:
        if code not in self._populated_dimensions:
            return
        self._current_dimension = code
        self._refresh_dimension_buttons()
        self._filter_edit.clear()
        self._clear_results(f"Pick a {_DIMENSION_LABELS.get(code, code).lower()} to see its books.")

        self._tree.clear()
        tree = self._taxonomy.get_term_tree(code)
        if not tree:
            self._empty_dimension_label.setText("No data yet for this dimension.")
            self._empty_dimension_label.setVisible(True)
            return
        self._empty_dimension_label.setVisible(False)
        for term in tree:
            self._tree.addTopLevelItem(_term_tree_item(term))

    def _apply_filter(self, text: str) -> None:
        needle = (normalize_search_text(text.strip()) or "").casefold()
        root = self._tree.invisibleRootItem()
        for index in range(root.childCount()):
            _filter_term_item(root.child(index), needle)

    def _on_term_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        term_id = item.data(0, Qt.ItemDataRole.UserRole)
        if term_id is None:
            return
        self._show_books_for_term(term_id, item.text(0))

    # ----------------------------------------------------------- results

    def _build_results_pane(self) -> QWidget:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        self._results_layout = QVBoxLayout(content)
        self._results_layout.setContentsMargins(16, 16, 16, 16)
        self._results_layout.setSpacing(10)
        self._status_label = EmptyStateLabel("Pick a term to see its books.", centered=True)
        self._results_layout.addWidget(self._status_label, stretch=1)
        scroll_area.setWidget(content)
        return scroll_area

    def _clear_results(self, status_text: str) -> None:
        # Real UI fix: a plain top-anchored MUTED_LABEL_STYLE QLabel in an
        # otherwise-empty pane read as "broken/blank," not "intentionally
        # empty" - the centered EmptyStateLabel treatment already
        # established elsewhere (the reader's "no book open" state, etc.)
        # makes an empty results pane obviously deliberate.
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
        book_ids = self._taxonomy.list_books_for_term(term_id)
        self._empty_results_layout()
        if not book_ids:
            self._status_label = EmptyStateLabel(
                f'No books linked to "{term_label}".', centered=True
            )
            self._results_layout.addWidget(self._status_label, stretch=1)
            return
        summaries = self._browser.list_books_by_ids(book_ids)
        self._status_label = QLabel(f'Books in "{term_label}" - {len(book_ids)} book(s)')
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

        title = QLabel(summary.title or "(untitled)")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        card_layout.addWidget(title)

        meta = QLabel(" · ".join([summary.author or "Unknown author", summary.library or "Unknown library"]))
        meta.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.BODY_SM}px;")
        card_layout.addWidget(meta)

        open_row = QHBoxLayout()
        read_button = QPushButton("Read in app")
        read_button.setIcon(button_icon("viewer"))
        read_button.setIconSize(button_icon_size())
        read_button.clicked.connect(
            lambda _checked, book_id=summary.book_id: self.open_in_viewer_requested.emit(book_id, 1)
        )
        open_row.addWidget(read_button)
        open_row.addStretch(1)
        card_layout.addLayout(open_row)

        return card


def _term_tree_item(term: TaxonomyTerm) -> QTreeWidgetItem:
    name = term.names.get("ar") or next(iter(term.names.values()), None) or f"#{term.term_id}"
    item = QTreeWidgetItem([name])
    item.setData(0, Qt.ItemDataRole.UserRole, term.term_id)
    for child in term.children:
        item.addChild(_term_tree_item(child))
    return item


def _filter_term_item(item: QTreeWidgetItem, needle: str) -> bool:
    own_name = normalize_search_text(item.text(0)) or ""
    self_matches = needle in own_name.casefold()
    child_matches = False
    for index in range(item.childCount()):
        if _filter_term_item(item.child(index), needle):
            child_matches = True
    visible = not needle or self_matches or child_matches
    item.setHidden(not visible)
    if child_matches and needle:
        item.setExpanded(True)
    return visible
