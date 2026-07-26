"""Search screen: query box, filters, and results, wired to the real search service."""

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
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.pdf_source_resolver import resolve_pdf_path
from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.interfaces.desktop_app.book_details_dialog import BookDetailsDialog
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
    BookSearchError,
    SqliteBookSearchRepository,
)
from islamic_research_hub.shared.excerpt_highlighting import highlight_excerpt_html

DEFAULT_LIMIT = 30
ALL_LIBRARIES_LABEL = "All libraries"


class SearchScreen(QWidget):
    """Search the master database and browse ranked, highlighted results."""

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        filter_row = QHBoxLayout()
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText("Search the library... (supports AND / OR / NOT, \"phrases\")")
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
        search_button.setDefault(True)
        search_button.clicked.connect(self._run_search)
        filter_row.addWidget(search_button)
        layout.addLayout(filter_row)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #7a7264;")
        layout.addWidget(self._status_label)

        self._results_area = QScrollArea()
        self._results_area.setWidgetResizable(True)
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setSpacing(8)
        self._results_layout.addStretch(1)
        self._results_area.setWidget(self._results_container)
        layout.addWidget(self._results_area, stretch=1)

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
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            "QFrame { background: #ffffff; border: 1px solid #e6dfcc; border-radius: 8px; }"
        )
        card_layout = QVBoxLayout(card)

        title = QLabel(result.title or "(untitled)")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [result.author or "Unknown author", result.library or "Unknown library"]
        if result.page_number is not None:
            meta_bits.append(f"page {result.page_number}")
        meta = QLabel(" · ".join(meta_bits))
        meta.setStyleSheet("color: #7a7264; font-size: 12px;")
        card_layout.addWidget(meta)

        excerpt = QLabel(highlight_excerpt_html(result.excerpt))
        excerpt.setTextFormat(Qt.TextFormat.RichText)
        excerpt.setWordWrap(True)
        excerpt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        excerpt.setStyleSheet("font-size: 13px; line-height: 150%;")
        card_layout.addWidget(excerpt)

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
        details_button.clicked.connect(lambda: self._show_details(book_id))
        row_layout.addWidget(details_button)

        row_layout.addStretch(1)
        return row

    def _show_details(self, book_id: int) -> None:
        metadata = self._browser.get_book_metadata(book_id)
        if metadata is not None:
            BookDetailsDialog(metadata, self).exec()


def _file_url(path: Path) -> QUrl:
    return QUrl.fromLocalFile(str(path))
