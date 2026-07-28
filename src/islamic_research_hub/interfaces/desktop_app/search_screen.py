"""Search screen: category/author browsing, query+filters+results, an inline detail panel."""

from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
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
from islamic_research_hub.domain.models.book_summary import BookSummary
from islamic_research_hub.domain.models.category_node import CategoryNode
from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    MAX_BROWSE_RESULTS,
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
    BookSearchError,
    SqliteBookSearchRepository,
)
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE
from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text
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

        # 691 real categories and 650 real authors are too many to scroll
        # through blindly - a live filter narrows either list as you type.
        self._browse_filter_edit = QLineEdit()
        self._browse_filter_edit.setPlaceholderText("Filter...")
        self._browse_filter_edit.textChanged.connect(self._apply_browse_filter)
        layout.addWidget(self._browse_filter_edit)

        self._browse_stack = QStackedWidget()
        self._category_tree = self._build_category_tree()
        self._browse_stack.addWidget(self._category_tree)
        self._author_list, self._author_row_buttons = self._build_author_list()
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

    def _build_author_list(self) -> tuple[QScrollArea, list[tuple[str, QPushButton]]]:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        row_buttons: list[tuple[str, QPushButton]] = []
        for name, count in self._browser.list_authors_with_counts():
            button = QPushButton(f"{name}  ({count})")
            button.setObjectName("authorRow")
            button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            button.clicked.connect(lambda _checked, n=name: self._filter_by_author(n))
            layout.addWidget(button)
            row_buttons.append((name, button))
        layout.addStretch(1)

        scroll_area.setWidget(container)
        return scroll_area, row_buttons

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
        self._browse_filter_edit.clear()

    def _apply_browse_filter(self, text: str) -> None:
        """Narrow whichever browse list (categories or authors) is currently shown."""
        needle = (normalize_search_text(text.strip()) or "").casefold()
        if self._browse_stack.currentIndex() == 0:
            root = self._category_tree.invisibleRootItem()
            for index in range(root.childCount()):
                self._filter_category_item(root.child(index), needle)
        else:
            for name, button in self._author_row_buttons:
                button.setVisible(needle in (normalize_search_text(name) or "").casefold())

    def _filter_category_item(self, item: QTreeWidgetItem, needle: str) -> bool:
        """Hide a category node unless it or a real descendant matches; return match state."""
        own_name = normalize_search_text(item.data(0, Qt.ItemDataRole.UserRole) or "") or ""
        self_matches = needle in own_name.casefold()
        child_matches = False
        for index in range(item.childCount()):
            if self._filter_category_item(item.child(index), needle):
                child_matches = True
        visible = not needle or self_matches or child_matches
        item.setHidden(not visible)
        if child_matches and needle:
            item.setExpanded(True)
        return visible

    def _on_category_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if not name:
            return
        self._category_edit.setText(name)
        if self._query_edit.text().strip():
            self._run_search()
        else:
            self._browse(self._browser.list_books_in_category(name), f'Books in "{name}"')

    def _filter_by_author(self, name: str) -> None:
        self._author_edit.setText(name)
        if self._query_edit.text().strip():
            self._run_search()
        else:
            self._browse(self._browser.list_books_by_author(name), f"Books by {name}")

    def _filter_by_library(self, name: str) -> None:
        index = self._library_combo.findText(name)
        if index >= 0:
            self._library_combo.setCurrentIndex(index)
        if self._query_edit.text().strip():
            self._run_search()
        elif name != ALL_LIBRARIES_LABEL:
            self._browse(self._browser.list_books_in_library(name), f"Books in {name}")
        else:
            self._clear_results()
            self._status_label.setText(
                "Type a search, or pick a specific category/author/library to browse."
            )

    def _browse(self, summaries: tuple[BookSummary, ...], heading: str) -> None:
        """Show a directly-openable list of books - no search query, no excerpts."""
        self._clear_results()
        if not summaries:
            self._status_label.setText(f"{heading}: no books found.")
            return
        suffix = f" (showing first {len(summaries)})" if len(summaries) == MAX_BROWSE_RESULTS else ""
        self._status_label.setText(f"{heading} - {len(summaries)} book(s){suffix}")
        for summary in summaries:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, self._build_summary_card(summary)
            )

    # -------------------------------------------------------------- middle

    def _build_middle_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # The query box is the primary action on this screen, so it gets its
        # own full-width row with a visibly larger height/font, instead of
        # competing for space in a single crowded row with every filter.
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText(
            "Search by content, title, author... "
            '(content search supports AND / OR / NOT, "phrases")'
        )
        self._query_edit.setObjectName("mainSearchBox")
        self._query_edit.setMinimumHeight(40)
        self._query_edit.returnPressed.connect(self._run_search)
        search_row.addWidget(self._query_edit, stretch=1)

        search_button = QPushButton("Search")
        search_button.setObjectName("primaryButton")
        search_button.setMinimumHeight(40)
        search_button.setDefault(True)
        search_button.clicked.connect(self._run_search)
        search_row.addWidget(search_button)
        layout.addLayout(search_row)

        filter_row = QHBoxLayout()
        self._library_combo = QComboBox()
        self._library_combo.addItem(ALL_LIBRARIES_LABEL)
        for library in self._browser.list_libraries():
            self._library_combo.addItem(library)
        filter_row.addWidget(self._library_combo)

        self._author_edit = QLineEdit()
        self._author_edit.setPlaceholderText("Author (exact)")
        filter_row.addWidget(self._author_edit)

        self._category_edit = QLineEdit()
        self._category_edit.setPlaceholderText("Category (exact)")
        filter_row.addWidget(self._category_edit)

        filter_row.addStretch(1)
        self._exact_match_checkbox = QCheckBox("Exact match")
        self._exact_match_checkbox.setToolTip(
            "On: literal spelling only.\n"
            "Off (default): tolerant of real spelling/keyboard variants "
            "(e.g. علي/علی, ك/ک)."
        )
        self._exact_match_checkbox.toggled.connect(self._on_exact_match_toggled)
        filter_row.addWidget(self._exact_match_checkbox)
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

    def _on_exact_match_toggled(self, _checked: bool) -> None:
        if self._query_edit.text().strip():
            self._run_search()

    def _run_search(self) -> None:
        query = self._query_edit.text().strip()
        self._clear_results()

        library = self._library_combo.currentText()
        library = None if library == ALL_LIBRARIES_LABEL else library
        author = self._author_edit.text().strip() or None
        category = self._category_edit.text().strip() or None
        exact = self._exact_match_checkbox.isChecked()

        if not query:
            # No search text - the Author/Category/Library filters can still
            # be used on their own (e.g. typed directly into the Author or
            # Category box, then Search clicked) to browse straight to the
            # matching books, same as clicking a name in the left pane does.
            if author or category or library:
                self._browse_by_filters(library, author, category)
            else:
                self._status_label.setText("")
            return

        # Book-name search runs alongside content search (not instead of it):
        # the same query can be a real title match, a real content match, or
        # both - shown as two clearly labeled groups, title matches first
        # since that's usually what a name-shaped query means.
        title_matches = self._browser.search_by_title(
            query, DEFAULT_LIMIT, library, author, category, exact
        )

        try:
            results = self._search_service.search(
                query, DEFAULT_LIMIT, library, author, category, exact
            )
        except BookSearchError:
            self._status_label.setText("That search couldn't be run - check your query and try again.")
            return
        except ValueError:
            self._status_label.setText("Enter a search term.")
            return

        if not results and not title_matches:
            self._status_label.setText(f'No matches found for "{query}".')
            return

        status_bits = []
        if title_matches:
            status_bits.append(f"{len(title_matches)} title match(es)")
        status_bits.append(f"{len(results)} content result(s)")
        self._status_label.setText(", ".join(status_bits))

        if title_matches:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, _pane_title("Matching titles")
            )
            for summary in title_matches:
                self._results_layout.insertWidget(
                    self._results_layout.count() - 1, self._build_summary_card(summary)
                )
        for result in results:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, self._build_result_card(result)
            )

    def _browse_by_filters(
        self, library: str | None, author: str | None, category: str | None
    ) -> None:
        """Browse straight to books matching Author/Category/Library filters alone."""
        summaries = self._browser.list_books_by_filters(library, author, category)
        heading_bits = []
        if author:
            heading_bits.append(f"author {author}")
        if category:
            heading_bits.append(f'category "{category}"')
        if library:
            heading_bits.append(f"library {library}")
        self._browse(summaries, "Books matching " + ", ".join(heading_bits))

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

        open_row = self._build_open_row(result.book_id, result.page_number)
        if open_row is not None:
            card_layout.addWidget(open_row)

        return card

    def _build_summary_card(self, summary: BookSummary) -> QFrame:
        """A directly-openable book card for browse results - no search excerpt."""
        card = QFrame()
        card.setObjectName("resultCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)

        title = QLabel(summary.title or "(untitled)")
        title.setStyleSheet(f"font-size: 15px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [summary.author or "Unknown author", summary.library or "Unknown library"]
        meta = QLabel(" · ".join(meta_bits))
        meta.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: 12px;")
        card_layout.addWidget(meta)

        card.mousePressEvent = lambda _event, s=summary: self._show_details(s.book_id)

        open_row = self._build_open_row(summary.book_id, None)
        if open_row is not None:
            card_layout.addWidget(open_row)

        return card

    def _build_open_row(self, book_id: int, page_number: int | None) -> QWidget | None:
        source = self._browser.get_book_source(book_id)
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

        target_page = page_number or 1
        read_button = QPushButton("Read in app")
        read_button.clicked.connect(
            lambda: self.open_in_viewer_requested.emit(book_id, target_page)
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
