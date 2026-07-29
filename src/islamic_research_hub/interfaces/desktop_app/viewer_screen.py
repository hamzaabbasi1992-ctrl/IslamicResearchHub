"""Viewer screen: read one book's pages in-app, with page navigation."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.reading_fonts import (
    DEFAULT_FONT_CHOICE,
    FONT_CHOICES,
    resolve_installed_font_family,
)
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, RTL_TEXT_STYLE

MIN_FONT_PX = 13
MAX_FONT_PX = 30
DEFAULT_FONT_PX = 19
FONT_STEP_PX = 1.5


class ViewerScreen(QWidget):
    """Show one book's pages, one at a time, with prev/next/jump navigation."""

    bookmark_toggled = Signal(int, int, bool)  # book_id, page_number, is_now_bookmarked
    pdf_fallback_requested = Signal()

    def __init__(
        self,
        database_path: Path,
        browser: BookBrowserRepository | None = None,
        initial_font_px: float | None = None,
        initial_font_family: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._browser = browser or BookBrowserRepository(database_path)
        self._pages: tuple = ()
        self._current_index = 0
        self._font_px = initial_font_px or DEFAULT_FONT_PX
        self._font_family = initial_font_family or DEFAULT_FONT_CHOICE
        self._current_book_id: int | None = None
        self._bookmarked_pages: set[int] = set()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._empty_label = QLabel("Open a book from Search to read it here.")
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

        self._pdf_fallback_banner = QWidget()
        self._pdf_fallback_banner.setVisible(False)
        banner_layout = QHBoxLayout(self._pdf_fallback_banner)
        banner_layout.setContentsMargins(16, 0, 16, 8)
        banner_label = QLabel(
            "This book's digitized text may be limited to headings - a scanned PDF is available."
        )
        banner_label.setStyleSheet(MUTED_LABEL_STYLE)
        banner_label.setWordWrap(True)
        banner_layout.addWidget(banner_label, stretch=1)
        pdf_fallback_button = QPushButton("Open scanned PDF")
        pdf_fallback_button.setIcon(button_icon("open-pdf"))
        pdf_fallback_button.setIconSize(button_icon_size())
        pdf_fallback_button.clicked.connect(self.pdf_fallback_requested)
        banner_layout.addWidget(pdf_fallback_button)
        reader_layout.addWidget(self._pdf_fallback_banner)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(16, 4, 16, 8)
        self._prev_button = QPushButton("Prev")
        self._prev_button.setIcon(button_icon("prev"))
        self._prev_button.setIconSize(button_icon_size())
        self._prev_button.clicked.connect(self._go_previous)
        toolbar.addWidget(self._prev_button)

        self._page_input = QLineEdit()
        self._page_input.setFixedWidth(50)
        self._page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_input.returnPressed.connect(self._jump_to_entered_page)
        toolbar.addWidget(self._page_input)

        self._page_count_label = QLabel()
        toolbar.addWidget(self._page_count_label)

        self._next_button = QPushButton("Next")
        self._next_button.setIcon(button_icon("next"))
        self._next_button.setIconSize(button_icon_size())
        self._next_button.clicked.connect(self._go_next)
        toolbar.addWidget(self._next_button)

        toolbar.addStretch(1)

        self._bookmark_button = QPushButton("Bookmark this page")
        self._bookmark_button.setIcon(button_icon("bookmark"))
        self._bookmark_button.setIconSize(button_icon_size())
        self._bookmark_button.clicked.connect(self._toggle_bookmark)
        toolbar.addWidget(self._bookmark_button)

        self._font_family_combo = QComboBox()
        for display_name, _font_stack in FONT_CHOICES:
            self._font_family_combo.addItem(display_name)
        initial_index = self._font_family_combo.findText(self._font_family)
        self._font_family_combo.setCurrentIndex(max(initial_index, 0))
        self._font_family_combo.currentTextChanged.connect(self._change_font_family)
        toolbar.addWidget(self._font_family_combo)

        smaller_button = QPushButton("A-")
        smaller_button.setFixedWidth(32)
        smaller_button.clicked.connect(lambda: self._change_font_size(-FONT_STEP_PX))
        toolbar.addWidget(smaller_button)

        larger_button = QPushButton("A+")
        larger_button.setFixedWidth(32)
        larger_button.clicked.connect(lambda: self._change_font_size(FONT_STEP_PX))
        toolbar.addWidget(larger_button)

        reader_layout.addLayout(toolbar)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self._content_label = QLabel()
        self._content_label.setWordWrap(True)
        self._content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._content_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._content_label.setStyleSheet(f"padding: 16px 24px; {RTL_TEXT_STYLE}")
        scroll_area.setWidget(self._content_label)
        reader_layout.addWidget(scroll_area, stretch=1)

        layout.addWidget(self._reader, stretch=1)
        self._apply_font_size()

    def load_book(self, book_id: int, bookmarked_pages: set[int] | None = None) -> bool:
        """Load one book's pages into the viewer. Returns False if not found."""
        detail = self._browser.get_book_detail(book_id)
        if detail is None:
            return False
        title, author, pages = detail
        self._pages = pages
        self._current_index = 0
        self._current_book_id = book_id
        self._bookmarked_pages = set(bookmarked_pages or ())
        self._title_label.setText(title or "(untitled)")
        self._author_label.setText(author or "Unknown author")
        self._empty_label.setVisible(False)
        self._reader.setVisible(True)
        self._pdf_fallback_banner.setVisible(False)
        self._render_current_page()
        return True

    def set_pdf_fallback_available(self, available: bool) -> None:
        """Show or hide the "a scanned PDF may be available" banner for the loaded book."""
        self._pdf_fallback_banner.setVisible(available)

    def jump_to_page_number(self, page_number: int) -> None:
        """Jump directly to a specific page number, if it exists among the loaded pages."""
        for index, page in enumerate(self._pages):
            if page.page_number == page_number:
                self._current_index = index
                self._render_current_page()
                return

    def _go_previous(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._render_current_page()

    def _go_next(self) -> None:
        if self._current_index < len(self._pages) - 1:
            self._current_index += 1
            self._render_current_page()

    def _jump_to_entered_page(self) -> None:
        text = self._page_input.text().strip()
        if text.isdigit():
            target = int(text) - 1
            if 0 <= target < len(self._pages):
                self._current_index = target
                self._render_current_page()

    def _change_font_size(self, delta: float) -> None:
        self._font_px = max(MIN_FONT_PX, min(MAX_FONT_PX, self._font_px + delta))
        self._apply_font_size()

    def _change_font_family(self, display_name: str) -> None:
        self._font_family = display_name
        self._apply_font_size()

    def _apply_font_size(self) -> None:
        font_stack = _font_stack_for(self._font_family)
        resolved_family = resolve_installed_font_family(font_stack)
        self._content_label.setStyleSheet(
            f"padding: 16px 24px; font-size: {self._font_px}px; line-height: 160%; "
            f"font-family: '{resolved_family}';"
        )

    def selected_font_family(self) -> str:
        """Return the currently selected reading font's display name."""
        return self._font_family

    def has_content(self) -> bool:
        """Return whether the loaded book has any real extracted page text.

        `load_book()` returns True as soon as a matching `Books` row
        exists, even for the ~9,172 real PDF-only books with `PageCount=0`
        (no OCR has been run on them) - this is the real signal callers
        need to decide whether to fall back to `PdfViewerScreen` instead.
        """
        return len(self._pages) > 0

    def current_page_number(self) -> int | None:
        """Return the real page number currently shown, or None if nothing is loaded."""
        if not self._pages:
            return None
        return self._pages[self._current_index].page_number

    def current_book_id(self) -> int | None:
        """Return the book id of the currently loaded book, if any."""
        return self._current_book_id

    def _toggle_bookmark(self) -> None:
        page_number = self.current_page_number()
        if self._current_book_id is None or page_number is None:
            return
        now_bookmarked = page_number not in self._bookmarked_pages
        if now_bookmarked:
            self._bookmarked_pages.add(page_number)
        else:
            self._bookmarked_pages.discard(page_number)
        self._update_bookmark_button()
        self.bookmark_toggled.emit(self._current_book_id, page_number, now_bookmarked)

    def _update_bookmark_button(self) -> None:
        page_number = self.current_page_number()
        is_bookmarked = page_number is not None and page_number in self._bookmarked_pages
        self._bookmark_button.setText(
            "★ Bookmarked" if is_bookmarked else "Bookmark this page"
        )

    def _render_current_page(self) -> None:
        if not self._pages:
            return
        page = self._pages[self._current_index]
        self._content_label.setText(page.content_f or "(no content)")
        self._page_input.setText(str(self._current_index + 1))
        self._page_count_label.setText(f"/ {len(self._pages)}")
        self._prev_button.setEnabled(self._current_index > 0)
        self._next_button.setEnabled(self._current_index < len(self._pages) - 1)
        self._update_bookmark_button()


def _font_stack_for(display_name: str) -> str:
    """Return the CSS-style font-family fallback chain for a chosen font's display name."""
    for name, font_stack in FONT_CHOICES:
        if name == display_name:
            return font_stack
    return FONT_CHOICES[0][1]
