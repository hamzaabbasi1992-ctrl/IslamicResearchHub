"""PDF Viewer screen: real in-app PDF rendering for metadata-only (PDF-sourced) books.

Roughly 9,172 real books in this corpus have no extracted page text at all
(no OCR has been run) - their only real content is the source PDF itself.
Before this screen existed, the only way to read one was "Open PDF", which
launches the OS's external PDF viewer. This renders the PDF directly in the
app, with real page navigation, using `QtPdf`/`QtPdfWidgets` (no new
dependency - both ship with PySide6).
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE

MIN_ZOOM = 0.5
MAX_ZOOM = 4.0
ZOOM_STEP = 0.25
DEFAULT_ZOOM = 1.0


class PdfViewerScreen(QWidget):
    """Show one PDF's real pages, one at a time, with prev/next/jump/zoom."""

    bookmark_toggled = Signal(int, int, bool)  # book_id, page_number, is_now_bookmarked

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._zoom = DEFAULT_ZOOM
        self._current_book_id: int | None = None
        self._bookmarked_pages: set[int] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._empty_label = QLabel("Open a PDF-only book from Search to read it here.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"{MUTED_LABEL_STYLE} padding: 2rem;")
        layout.addWidget(self._empty_label)

        self._reader = QWidget()
        self._reader.setVisible(False)
        reader_layout = QVBoxLayout(self._reader)
        reader_layout.setContentsMargins(0, 0, 0, 0)
        reader_layout.setSpacing(0)

        header = QVBoxLayout()
        header.setContentsMargins(16, 12, 16, 4)
        self._title_label = QLabel()
        self._title_label.setStyleSheet(f"font-size: 16px; font-weight: 700; {RTL_TEXT_STYLE}")
        self._title_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._author_label = QLabel()
        self._author_label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: 12px;")
        self._author_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        header.addWidget(self._title_label)
        header.addWidget(self._author_label)
        reader_layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 4, 16, 8)
        self._prev_button = QPushButton("< Prev")
        self._prev_button.clicked.connect(self._go_previous)
        toolbar.addWidget(self._prev_button)

        self._page_input = QLineEdit()
        self._page_input.setFixedWidth(50)
        self._page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_input.returnPressed.connect(self._jump_to_entered_page)
        toolbar.addWidget(self._page_input)

        self._page_count_label = QLabel()
        toolbar.addWidget(self._page_count_label)

        self._next_button = QPushButton("Next >")
        self._next_button.clicked.connect(self._go_next)
        toolbar.addWidget(self._next_button)

        toolbar.addStretch(1)

        self._bookmark_button = QPushButton("Bookmark this page")
        self._bookmark_button.clicked.connect(self._toggle_bookmark)
        toolbar.addWidget(self._bookmark_button)

        zoom_out_button = QPushButton("-")
        zoom_out_button.setFixedWidth(28)
        zoom_out_button.clicked.connect(lambda: self._change_zoom(-ZOOM_STEP))
        toolbar.addWidget(zoom_out_button)

        zoom_in_button = QPushButton("+")
        zoom_in_button.setFixedWidth(28)
        zoom_in_button.clicked.connect(lambda: self._change_zoom(ZOOM_STEP))
        toolbar.addWidget(zoom_in_button)

        reader_layout.addLayout(toolbar)

        self._document = QPdfDocument(self)
        self._pdf_view = QPdfView()
        self._pdf_view.setDocument(self._document)
        self._pdf_view.setPageMode(QPdfView.PageMode.SinglePage)
        self._pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self._pdf_view.pageNavigator().currentPageChanged.connect(self._on_current_page_changed)
        reader_layout.addWidget(self._pdf_view, stretch=1)

        layout.addWidget(self._reader, stretch=1)

    def load_pdf(
        self,
        pdf_path: Path,
        title: str | None = None,
        author: str | None = None,
        book_id: int | None = None,
        bookmarked_pages: set[int] | None = None,
    ) -> bool:
        """Load a real PDF file into the viewer. Returns False if it can't be read."""
        error = self._document.load(str(pdf_path))
        if error != QPdfDocument.Error.None_ or self._document.pageCount() < 1:
            return False

        self._current_book_id = book_id
        self._bookmarked_pages = set(bookmarked_pages or ())
        self._title_label.setText(title or pdf_path.stem)
        self._author_label.setText(author or "Unknown author")
        self._empty_label.setVisible(False)
        self._reader.setVisible(True)
        self._zoom = DEFAULT_ZOOM
        self._apply_zoom()
        self.jump_to_page_number(1)
        return True

    def jump_to_page_number(self, page_number: int) -> None:
        """Jump directly to a specific 1-based real PDF page, if it exists."""
        if self._document.pageCount() < 1:
            return
        index = max(0, min(page_number - 1, self._document.pageCount() - 1))
        self._pdf_view.pageNavigator().jump(index, self._pdf_view.pageNavigator().currentLocation())

    def current_page_number(self) -> int:
        """Return the real, currently-shown 1-based page number."""
        return self._pdf_view.pageNavigator().currentPage() + 1

    def current_book_id(self) -> int | None:
        """Return the book id of the currently loaded PDF, if known."""
        return self._current_book_id

    def _go_previous(self) -> None:
        self.jump_to_page_number(self.current_page_number() - 1)

    def _go_next(self) -> None:
        self.jump_to_page_number(self.current_page_number() + 1)

    def _jump_to_entered_page(self) -> None:
        text = self._page_input.text().strip()
        if text.isdigit():
            self.jump_to_page_number(int(text))

    def _on_current_page_changed(self, _index: int) -> None:
        page_number = self.current_page_number()
        self._page_input.setText(str(page_number))
        self._page_count_label.setText(f"/ {self._document.pageCount()}")
        self._prev_button.setEnabled(page_number > 1)
        self._next_button.setEnabled(page_number < self._document.pageCount())
        self._update_bookmark_button()

    def _change_zoom(self, delta: float) -> None:
        self._zoom = max(MIN_ZOOM, min(MAX_ZOOM, self._zoom + delta))
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        self._pdf_view.setZoomFactor(self._zoom)

    def _toggle_bookmark(self) -> None:
        if self._current_book_id is None:
            return
        page_number = self.current_page_number()
        now_bookmarked = page_number not in self._bookmarked_pages
        if now_bookmarked:
            self._bookmarked_pages.add(page_number)
        else:
            self._bookmarked_pages.discard(page_number)
        self._update_bookmark_button()
        self.bookmark_toggled.emit(self._current_book_id, page_number, now_bookmarked)

    def _update_bookmark_button(self) -> None:
        is_bookmarked = self.current_page_number() in self._bookmarked_pages
        self._bookmark_button.setText(
            "★ Bookmarked" if is_bookmarked else "Bookmark this page"
        )

    def bookmarked_pages(self) -> set[int]:
        """Return the real set of page numbers bookmarked in this session."""
        return set(self._bookmarked_pages)
