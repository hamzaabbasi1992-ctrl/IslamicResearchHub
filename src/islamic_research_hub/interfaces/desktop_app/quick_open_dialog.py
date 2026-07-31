"""Quick Open: a keyboard-triggered fuzzy jump to a rail screen or a recent book.

New UI wiring only, no new backend - fans out to `MainWindow._show_screen()`
(existing) and `RecentBookRepository.list_recent()` (existing, already
real data). Navigation-discoverability fix: every rail screen and every
recent book becomes reachable from anywhere in the app via one shortcut
and a few keystrokes, instead of always going through the rail/Home.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from islamic_research_hub.infrastructure.persistence.recent_book_repository import (
    RecentBookRepository,
)
from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text

_MAX_RECENT_BOOKS_SHOWN = 10


class QuickOpenDialog(QDialog):
    """A filterable list of rail screens + recent books - Enter opens the
    highlighted entry, Escape (native `QDialog` behavior) cancels."""

    screen_requested = Signal(int)  # rail index
    book_requested = Signal(int, int)  # book_id, page_number

    def __init__(
        self,
        rail_labels: tuple[str, ...],
        recent_books: RecentBookRepository,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quick Open")
        self.resize(440, 360)
        self._rail_labels = rail_labels
        self._recent_books = recent_books.list_recent(limit=_MAX_RECENT_BOOKS_SHOWN)

        layout = QVBoxLayout(self)
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Type a screen name or a recent book title...")
        layout.addWidget(self._filter_edit)
        self._list = QListWidget()
        layout.addWidget(self._list, stretch=1)

        self._filter_edit.textChanged.connect(self._populate)
        self._filter_edit.returnPressed.connect(self._open_first_match)
        self._list.itemActivated.connect(self._open_item)

        self._filter_edit.setFocus()
        self._populate("")

    def _populate(self, text: str) -> None:
        self._list.clear()
        needle = (normalize_search_text(text.strip()) or "").casefold()
        for index, label in enumerate(self._rail_labels):
            if not needle or needle in (normalize_search_text(label) or "").casefold():
                item = QListWidgetItem(f"Go to {label}")
                item.setData(Qt.ItemDataRole.UserRole, ("screen", index))
                self._list.addItem(item)
        for summary in self._recent_books:
            title = summary.title or "(untitled)"
            if not needle or needle in (normalize_search_text(title) or "").casefold():
                item = QListWidgetItem(f"Open: {title}")
                item.setData(Qt.ItemDataRole.UserRole, ("book", summary.book_id))
                self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _open_first_match(self) -> None:
        if self._list.count():
            self._open_item(self._list.item(0))

    def _open_item(self, item: QListWidgetItem) -> None:
        kind, value = item.data(Qt.ItemDataRole.UserRole)
        if kind == "screen":
            self.screen_requested.emit(value)
        else:
            self.book_requested.emit(value, 1)
        self.accept()
