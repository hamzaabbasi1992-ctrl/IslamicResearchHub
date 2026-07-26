"""Import screen: real library sources and duplicate-candidate review."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
    DuplicateCandidateRepository,
)


class ImportScreen(QWidget):
    """Show real library sources and let the user review/clean duplicate candidates."""

    def __init__(
        self,
        database_path: Path,
        browser: BookBrowserRepository | None = None,
        duplicates: DuplicateCandidateRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._browser = browser or BookBrowserRepository(database_path)
        self._duplicates = duplicates or DuplicateCandidateRepository(database_path)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        layout.addWidget(_heading("Library sources"))
        self._library_table = QTableWidget(0, 2)
        self._library_table.setHorizontalHeaderLabels(["Library", "Books"])
        self._library_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._library_table.verticalHeader().setVisible(False)
        self._library_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._library_table)

        layout.addWidget(_heading("Duplicate review"))
        self._duplicate_status_label = QLabel()
        self._duplicate_status_label.setStyleSheet("color: #7a7264;")
        layout.addWidget(self._duplicate_status_label)

        button_row = QHBoxLayout()
        scan_button = QPushButton("Scan for duplicates")
        scan_button.clicked.connect(self._run_scan)
        button_row.addWidget(scan_button)

        self._cleanup_button = QPushButton("Remove empty-stub duplicates")
        self._cleanup_button.clicked.connect(self._run_cleanup)
        button_row.addWidget(self._cleanup_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._duplicate_table = QTableWidget(0, 4)
        self._duplicate_table.setHorizontalHeaderLabels(
            ["Book", "Library", "Possible duplicate of", "Library"]
        )
        self._duplicate_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._duplicate_table.verticalHeader().setVisible(False)
        self._duplicate_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._duplicate_table)

        layout.addStretch(1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()

    def refresh(self) -> None:
        """Reload both tables from the real database."""
        self._reload_libraries()
        self._reload_duplicates()

    def _reload_libraries(self) -> None:
        libraries = self._browser.list_libraries_with_counts()
        self._library_table.setRowCount(len(libraries))
        for row, (name, count) in enumerate(libraries):
            self._library_table.setItem(row, 0, _readonly_item(name, rtl=True))
            self._library_table.setItem(row, 1, _readonly_item(str(count)))

    def _reload_duplicates(self) -> None:
        candidates = self._duplicates.list_candidates()
        self._duplicate_status_label.setText(f"{len(candidates)} candidate(s) awaiting review")
        self._duplicate_table.setRowCount(len(candidates))
        for row, candidate in enumerate(candidates):
            book_source = self._browser.get_book_source(candidate.book_id)
            other_source = self._browser.get_book_source(candidate.duplicate_of_book_id)
            book_detail = self._browser.get_book_detail(candidate.book_id)
            other_detail = self._browser.get_book_detail(candidate.duplicate_of_book_id)

            book_title = book_detail[0] if book_detail else f"Book {candidate.book_id}"
            other_title = (
                other_detail[0] if other_detail else f"Book {candidate.duplicate_of_book_id}"
            )
            book_library = book_source[1] if book_source else "Unknown"
            other_library = other_source[1] if other_source else "Unknown"

            self._duplicate_table.setItem(row, 0, _readonly_item(book_title or "(untitled)", rtl=True))
            self._duplicate_table.setItem(row, 1, _readonly_item(book_library))
            self._duplicate_table.setItem(row, 2, _readonly_item(other_title or "(untitled)", rtl=True))
            self._duplicate_table.setItem(row, 3, _readonly_item(other_library))

    def _run_scan(self) -> None:
        self._duplicate_status_label.setText("Scanning...")
        self._duplicates.detect_and_store()
        self._reload_duplicates()

    def _run_cleanup(self) -> None:
        removed = self._duplicates.resolve_empty_stub_duplicates()
        self._reload_libraries()
        self._reload_duplicates()
        remaining = self._duplicate_status_label.text()
        self._duplicate_status_label.setText(f"Removed {removed} empty-stub duplicate(s). {remaining}")


def _heading(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size: 15px; font-weight: 700; margin-top: 6px;")
    return label


def _readonly_item(text: str, rtl: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if rtl:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item
