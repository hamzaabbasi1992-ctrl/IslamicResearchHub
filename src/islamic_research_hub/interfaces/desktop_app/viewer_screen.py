"""Viewer screen: read one book's pages in-app, with page navigation."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

MIN_FONT_PX = 13
MAX_FONT_PX = 30
DEFAULT_FONT_PX = 19
FONT_STEP_PX = 1.5


class ViewerScreen(QWidget):
    """Show one book's pages, one at a time, with prev/next/jump navigation."""

    def __init__(
        self,
        database_path: Path,
        browser: BookBrowserRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._browser = browser or BookBrowserRepository(database_path)
        self._pages: tuple = ()
        self._current_index = 0
        self._font_px = DEFAULT_FONT_PX

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._empty_label = QLabel("Open a book from Search to read it here.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet("color: #7a7264; padding: 2rem;")
        layout.addWidget(self._empty_label)

        self._reader = QWidget()
        self._reader.setVisible(False)
        reader_layout = QVBoxLayout(self._reader)
        reader_layout.setContentsMargins(0, 0, 0, 0)
        reader_layout.setSpacing(0)

        header = QVBoxLayout()
        header.setContentsMargins(16, 12, 16, 4)
        self._title_label = QLabel()
        self._title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        self._title_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._author_label = QLabel()
        self._author_label.setStyleSheet("color: #7a7264; font-size: 12px;")
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
        self._content_label.setStyleSheet("padding: 16px 24px;")
        scroll_area.setWidget(self._content_label)
        reader_layout.addWidget(scroll_area, stretch=1)

        layout.addWidget(self._reader, stretch=1)
        self._apply_font_size()

    def load_book(self, book_id: int) -> bool:
        """Load one book's pages into the viewer. Returns False if not found."""
        detail = self._browser.get_book_detail(book_id)
        if detail is None:
            return False
        title, author, pages = detail
        self._pages = pages
        self._current_index = 0
        self._title_label.setText(title or "(untitled)")
        self._author_label.setText(author or "Unknown author")
        self._empty_label.setVisible(False)
        self._reader.setVisible(True)
        self._render_current_page()
        return True

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

    def _apply_font_size(self) -> None:
        self._content_label.setStyleSheet(
            f"padding: 16px 24px; font-size: {self._font_px}px; line-height: 160%;"
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
