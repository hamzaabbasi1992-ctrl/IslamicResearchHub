"""Search screen: category/author browsing, query+filters+results, an inline detail panel."""

from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.pdf_source_resolver import resolve_pdf_path
from islamic_research_hub.domain.models.book_metadata import BookMetadata
from islamic_research_hub.domain.models.category_node import CategoryNode
from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
    BookSearchError,
    SqliteBookSearchRepository,
)
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE
from islamic_research_hub.shared.excerpt_highlighting import highlight_excerpt_html

DEFAULT_LIMIT = 30
ALL_LIBRARIES_LABEL = "All libraries"
LEFT_PANE_WIDTH = 230
RIGHT_PANE_WIDTH = 260


class SearchScreen(QWidget):
    """Browse categories/authors, search the master database, view a result's details."""

    open_in_viewer_requested = Signal(int, int)  # book_id, page_number

    def __init__(
        self,
        database_path: Path,
        maknoon_pdf_folder: Path,
        search_service: BookSearchService | None = None,
        browser: BookBrowserRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._maknoon_pdf_folder = maknoon_pdf_folder
        self._search_service = search_service or BookSearchService(
            SqliteBookSearchRepository(database_path)
        )
        self._browser = browser or BookBrowserRepository(database_path)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_left_pane())
        layout.addWidget(self._build_middle_pane(), stretch=1)
        layout.addWidget(self._build_right_pane())

    # ---------------------------------------------------------------- left

    def _build_left_pane(self) -> QWidget:
        # A plain (non-scrolling) fixed-width pane: the category tree and the
        # author list both scroll themselves internally (a QTreeWidget always
        # does; the author list is wrapped in its own QScrollArea below) - an
        # outer QScrollArea around the whole pane would fight that, since
        # QScrollArea gives its content exactly the height its sizeHint
        # wants, and a QTreeWidget's sizeHint wants to show every row at once.
        pane = QWidget()
        pane.setObjectName("searchLeftPane")
        pane.setFixedWidth(LEFT_PANE_WIDTH)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 14, 12, 8)
        layout.setSpacing(6)

        tab_row = QHBoxLayout()
        self._categories_tab_button = QPushButton("Categories")
        self._categories_tab_button.setCheckable(True)
        self._categories_tab_button.setChecked(True)
        self._categories_tab_button.setObjectName("navTab")
        self._categories_tab_button.clicked.connect(lambda: self._show_browse_tab(0))
        tab_row.addWidget(self._categories_tab_button)

        self._authors_tab_button = QPushButton("Authors")
        self._authors_tab_button.setCheckable(True)
        self._authors_tab_button.setObjectName("navTab")
        self._authors_tab_button.clicked.connect(lambda: self._show_browse_tab(1))
        tab_row.addWidget(self._authors_tab_button)
        layout.addLayout(tab_row)

        self._browse_stack = QStackedWidget()
        self._category_tree = self._build_category_tree()
        self._browse_stack.addWidget(self._category_tree)
        self._author_list = self._build_author_list()
        self._browse_stack.addWidget(self._author_list)
        layout.addWidget(self._browse_stack, stretch=1)

        layout.addWidget(_pane_title("Libraries"))
        self._library_chip_layout = QVBoxLayout()
        self._library_chip_layout.setSpacing(4)
        self._rebuild_library_chips()
        layout.addLayout(self._library_chip_layout)

        return pane

    def _build_category_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        for node in self._browser.get_category_tree():
            tree.addTopLevelItem(_category_tree_item(node))
        tree.itemClicked.connect(self._on_category_clicked)
        return tree

    def _build_author_list(self) -> QScrollArea:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        for name, count in self._browser.list_authors_with_counts():
            button = QPushButton(f"{name}  ({count})")
            button.setObjectName("authorRow")
            button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            button.clicked.connect(lambda _checked, n=name: self._filter_by_author(n))
            layout.addWidget(button)
        layout.addStretch(1)

        scroll_area.setWidget(container)
        return scroll_area

    def _rebuild_library_chips(self) -> None:
        while self._library_chip_layout.count():
            item = self._library_chip_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        all_chip = QPushButton(f"{ALL_LIBRARIES_LABEL}  ({self._browser.get_header_stats().book_count})")
        all_chip.setObjectName("libraryChip")
        all_chip.clicked.connect(lambda: self._filter_by_library(ALL_LIBRARIES_LABEL))
        self._library_chip_layout.addWidget(all_chip)
        for name, count in self._browser.list_libraries_with_counts():
            chip = QPushButton(f"{name}  ({count})")
            chip.setObjectName("libraryChip")
            chip.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            chip.clicked.connect(lambda _checked, n=name: self._filter_by_library(n))
            self._library_chip_layout.addWidget(chip)

    def _show_browse_tab(self, index: int) -> None:
        self._browse_stack.setCurrentIndex(index)
        self._categories_tab_button.setChecked(index == 0)
        self._authors_tab_button.setChecked(index == 1)

    def _on_category_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if name:
            self._category_edit.setText(name)
            self._run_search()

    def _filter_by_author(self, name: str) -> None:
        self._author_edit.setText(name)
        self._run_search()

    def _filter_by_library(self, name: str) -> None:
        index = self._library_combo.findText(name)
        if index >= 0:
            self._library_combo.setCurrentIndex(index)
        self._run_search()

    # -------------------------------------------------------------- middle

    def _build_middle_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        filter_row = QHBoxLayout()
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText(
            'Search the library... (supports AND / OR / NOT, "phrases")'
        )
        self._query_edit.returnPressed.connect(self._run_search)
        filter_row.addWidget(self._query_edit, stretch=1)

        self._library_combo = QComboBox()
        self._library_combo.addItem(ALL_LIBRARIES_LABEL)
        for library in self._browser.list_libraries():
            self._library_combo.addItem(library)
        filter_row.addWidget(self._library_combo)

        self._author_edit = QLineEdit()
        self._author_edit.setPlaceholderText("Author (exact)")
        self._author_edit.setMaximumWidth(200)
        filter_row.addWidget(self._author_edit)

        self._category_edit = QLineEdit()
        self._category_edit.setPlaceholderText("Category (exact)")
        self._category_edit.setMaximumWidth(200)
        filter_row.addWidget(self._category_edit)

        search_button = QPushButton("Search")
        search_button.setObjectName("primaryButton")
        search_button.setDefault(True)
        search_button.clicked.connect(self._run_search)
        filter_row.addWidget(search_button)
        layout.addLayout(filter_row)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._status_label)

        self._results_area = QScrollArea()
        self._results_area.setWidgetResizable(True)
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch(1)
        self._results_area.setWidget(self._results_container)
        layout.addWidget(self._results_area, stretch=1)
        return pane

    def _run_search(self) -> None:
        query = self._query_edit.text().strip()
        self._clear_results()
        if not query:
            self._status_label.setText("")
            return

        library = self._library_combo.currentText()
        library = None if library == ALL_LIBRARIES_LABEL else library
        author = self._author_edit.text().strip() or None
        category = self._category_edit.text().strip() or None

        try:
            results = self._search_service.search(
                query, DEFAULT_LIMIT, library, author, category
            )
        except BookSearchError:
            self._status_label.setText("That search couldn't be run - check your query and try again.")
            return
        except ValueError:
            self._status_label.setText("Enter a search term.")
            return

        if not results:
            self._status_label.setText(f'No matches found for "{query}".')
            return

        self._status_label.setText(f"{len(results)} result(s)")
        for result in results:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, self._build_result_card(result)
            )

    def _clear_results(self) -> None:
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_result_card(self, result: SearchResult) -> QFrame:
        card = QFrame()
        card.setObjectName("resultCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)

        title = QLabel(result.title or "(untitled)")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [result.author or "Unknown author", result.library or "Unknown library"]
        if result.page_number is not None:
            meta_bits.append(f"page {result.page_number}")
        meta = QLabel(" · ".join(meta_bits))
        meta.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: 12px;")
        card_layout.addWidget(meta)

        excerpt = QLabel(highlight_excerpt_html(result.excerpt))
        excerpt.setTextFormat(Qt.TextFormat.RichText)
        excerpt.setWordWrap(True)
        excerpt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        excerpt.setStyleSheet(f"font-size: 13px; line-height: 150%; {RTL_TEXT_STYLE}")
        _enable_height_for_width(excerpt)
        card_layout.addWidget(excerpt)

        card.mousePressEvent = lambda _event, r=result: self._show_details(r.book_id, r.page_number)

        open_row = self._build_open_row(result)
        if open_row is not None:
            card_layout.addWidget(open_row)

        return card

    def _build_open_row(self, result: SearchResult) -> QWidget | None:
        source = self._browser.get_book_source(result.book_id)
        if source is None:
            return None
        pdf_path = resolve_pdf_path(source[1], source[0], self._maknoon_pdf_folder)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 0)
        if pdf_path is not None:
            pdf_button = QPushButton("Open PDF")
            pdf_button.clicked.connect(lambda: QDesktopServices.openUrl(_file_url(pdf_path)))
            row_layout.addWidget(pdf_button)

        book_id = result.book_id
        page_number = result.page_number or 1
        read_button = QPushButton("Read in app")
        read_button.clicked.connect(
            lambda: self.open_in_viewer_requested.emit(book_id, page_number)
        )
        row_layout.addWidget(read_button)

        details_button = QPushButton("Details")
        details_button.clicked.connect(lambda: self._show_details(book_id, page_number))
        row_layout.addWidget(details_button)

        row_layout.addStretch(1)
        return row

    # --------------------------------------------------------------- right

    def _build_right_pane(self) -> QWidget:
        pane = QScrollArea()
        pane.setObjectName("resultCard")
        pane.setFixedWidth(RIGHT_PANE_WIDTH)
        pane.setWidgetResizable(True)

        self._detail_content = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_content)
        self._detail_layout.setContentsMargins(14, 14, 14, 14)
        self._detail_layout.setSpacing(6)
        self._detail_layout.addStretch(1)
        pane.setWidget(self._detail_content)
        return pane

    def _show_details(self, book_id: int, page_number: int | None = None) -> None:
        metadata = self._browser.get_book_metadata(book_id)
        if metadata is None:
            return
        self._clear_detail_panel()
        self._populate_detail_panel(metadata, page_number)

    def _clear_detail_panel(self) -> None:
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_detail_panel(self, metadata: BookMetadata, page_number: int | None) -> None:
        title = QLabel(metadata.title or "(untitled)")
        title.setWordWrap(True)
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; {RTL_TEXT_STYLE}")
        self._detail_layout.addWidget(title)

        rows: list[tuple[str, str | None]] = [
            ("Author", metadata.author),
            ("Publisher", metadata.publisher),
            ("Language", metadata.language),
            ("Category", metadata.category),
            ("Library", metadata.library),
        ]
        if metadata.series_title:
            series_text = metadata.series_title
            if metadata.volume_number is not None:
                series_text += f" (volume {metadata.volume_number})"
            rows.append(("Series", series_text))
        rows.append(("Pages", str(metadata.page_count)))
        rows.append(("Chapters", str(metadata.chapter_count)))
        if page_number is not None:
            rows.append(("Matched page", str(page_number)))

        for label_text, value in rows:
            self._detail_layout.addWidget(_detail_row(label_text, value))

        open_viewer_button = QPushButton("Open in Viewer")
        open_viewer_button.setObjectName("primaryButton")
        target_page = page_number or 1
        open_viewer_button.clicked.connect(
            lambda: self.open_in_viewer_requested.emit(metadata.book_id, target_page)
        )
        self._detail_layout.addWidget(open_viewer_button)

        source = self._browser.get_book_source(metadata.book_id)
        if source is not None:
            pdf_path = resolve_pdf_path(source[1], source[0], self._maknoon_pdf_folder)
            if pdf_path is not None:
                pdf_button = QPushButton("Open source PDF")
                pdf_button.clicked.connect(lambda: QDesktopServices.openUrl(_file_url(pdf_path)))
                self._detail_layout.addWidget(pdf_button)

        self._detail_layout.addStretch(1)


def _pane_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: 11px; font-weight: 600; margin-top: 6px;")
    return label


def _detail_row(label_text: str, value: str | None) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    caption = QLabel(label_text)
    caption.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: 10px;")
    layout.addWidget(caption)
    value_label = QLabel(value or "Unknown")
    value_label.setWordWrap(True)
    value_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    layout.addWidget(value_label)
    return row


def _category_tree_item(node: CategoryNode) -> QTreeWidgetItem:
    item = QTreeWidgetItem([f"{node.name}  ({node.book_count})"])
    item.setData(0, Qt.ItemDataRole.UserRole, node.name)
    for child in node.children:
        item.addChild(_category_tree_item(child))
    return item


def _file_url(path: Path) -> QUrl:
    return QUrl.fromLocalFile(str(path))


def _enable_height_for_width(label: QLabel) -> None:
    """Make a word-wrapped rich-text QLabel report its real wrapped height to the layout.

    Without this, Qt's QVBoxLayout sizes such a label using its unwrapped
    sizeHint (a single line) instead of the multi-line height it actually
    needs at its assigned width, clipping the excerpt to one line's height.
    """
    policy = label.sizePolicy()
    policy.setHeightForWidth(True)
    label.setSizePolicy(policy)
