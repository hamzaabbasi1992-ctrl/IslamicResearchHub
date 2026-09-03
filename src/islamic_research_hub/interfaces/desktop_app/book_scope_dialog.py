"""Multi-book search scope picker.

Allows users to restrict searches to zero, one, or several specific books by title
with live filtering and quick toggle options.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import normalize_search_text


class BookScopeDialog(QDialog):
    """Pick zero, one, or several books to restrict a search to."""

    def __init__(
        self,
        books_with_ids: tuple[tuple[int, str], ...],
        currently_selected: tuple[int, ...] | None,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._books_with_ids = books_with_ids
        tr = translator.tr
        self.setWindowTitle("Select Specific Books")
        self.resize(440, 480)

        layout = QVBoxLayout(self)
        hint = QLabel("Select specific books to search within:")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter books by title...")
        self._filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_edit)

        button_row = QHBoxLayout()
        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        button_row.addWidget(select_all_button)

        clear_all_button = QPushButton("Clear All")
        clear_all_button.clicked.connect(lambda: self._set_all_checked(False))
        button_row.addWidget(clear_all_button)
        layout.addLayout(button_row)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self._checkbox_layout = QVBoxLayout(scroll_content)
        self._checkbox_layout.setContentsMargins(4, 4, 4, 4)
        self._checkbox_layout.setSpacing(4)

        initial_selected_set = set(currently_selected) if currently_selected is not None else None
        self._checkboxes: list[tuple[int, str, QCheckBox]] = []

        for book_id, title in books_with_ids:
            box = QCheckBox(title)
            is_checked = (
                initial_selected_set is None or book_id in initial_selected_set
            )
            box.setChecked(is_checked)
            self._checkbox_layout.addWidget(box)
            self._checkboxes.append((book_id, title, box))

        self._checkbox_layout.addStretch(1)
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area, stretch=1)

        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)
        layout.addWidget(dialog_buttons)

    def _apply_filter(self, text: str) -> None:
        needle = (normalize_search_text(text.strip()) or "").casefold()
        for _, title, box in self._checkboxes:
            norm_title = (normalize_search_text(title) or "").casefold()
            box.setVisible(not needle or needle in norm_title)

    def _set_all_checked(self, checked: bool) -> None:
        for _, _, box in self._checkboxes:
            if box.isVisible():
                box.setChecked(checked)

    def selected_book_ids(self) -> tuple[int, ...] | None:
        """Return selected book IDs or None if all/none selected (meaning no filter)."""
        checked = tuple(book_id for book_id, _, box in self._checkboxes if box.isChecked())
        if not checked or len(checked) == len(self._checkboxes):
            return None
        return checked
