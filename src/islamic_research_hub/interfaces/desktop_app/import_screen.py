"""Import screen: add new libraries, real library sources, duplicate-candidate review."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
from islamic_research_hub.interfaces.desktop_app.library_import_worker import (
    FORMAT_AUTO,
    FORMAT_MAKNOON,
    FORMAT_MJBZ,
    FORMAT_PDF,
    LibraryImportWorker,
)
from islamic_research_hub.interfaces.desktop_app.theme import INK, MUTED_LABEL_STYLE

_FORMAT_CHOICES = (
    (FORMAT_AUTO, "Auto-detect"),
    (FORMAT_MJBZ, ".mjbz (Jibreel Mobile)"),
    (FORMAT_MAKNOON, "Pre-extracted text"),
    (FORMAT_PDF, "PDF (metadata only)"),
)


class ImportScreen(QWidget):
    """Add new libraries, show real library sources, and review duplicate candidates."""

    library_imported = Signal()

    def __init__(
        self,
        database_path: Path,
        browser: BookBrowserRepository | None = None,
        duplicates: DuplicateCandidateRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._browser = browser or BookBrowserRepository(database_path)
        self._duplicates = duplicates or DuplicateCandidateRepository(database_path)
        self._worker: LibraryImportWorker | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.addWidget(_heading("Library sources"))
        header_row.addStretch(1)
        self._add_library_toggle = QPushButton("+ Add new library")
        self._add_library_toggle.setObjectName("primaryButton")
        self._add_library_toggle.clicked.connect(self._toggle_add_library_form)
        header_row.addWidget(self._add_library_toggle)
        layout.addLayout(header_row)

        self._add_library_form = self._build_add_library_form()
        self._add_library_form.setVisible(False)
        layout.addWidget(self._add_library_form)

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
        self._duplicate_status_label.setStyleSheet(MUTED_LABEL_STYLE)
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

    def _build_add_library_form(self) -> QFrame:
        form = QFrame()
        form.setObjectName("settingsBlock")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(14, 12, 14, 14)
        form_layout.setSpacing(8)

        folder_row = QHBoxLayout()
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._pick_folder)
        folder_row.addWidget(browse_button)
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setPlaceholderText("Folder to scan")
        folder_row.addWidget(self._folder_edit, stretch=1)
        form_layout.addLayout(folder_row)

        options_row = QHBoxLayout()
        self._format_combo = QComboBox()
        for key, label in _FORMAT_CHOICES:
            self._format_combo.addItem(label, userData=key)
        options_row.addWidget(self._format_combo)
        self._library_name_edit = QLineEdit()
        self._library_name_edit.setPlaceholderText("Library name (e.g. Maktaba Ashrafia)")
        options_row.addWidget(self._library_name_edit, stretch=1)
        form_layout.addLayout(options_row)

        action_row = QHBoxLayout()
        self._scan_import_button = QPushButton("Scan && import")
        self._scan_import_button.setObjectName("primaryButton")
        self._scan_import_button.clicked.connect(self._run_import)
        action_row.addWidget(self._scan_import_button)
        self._import_status_label = QLabel(
            "Runs the matching importer automatically, skips already-imported "
            "books, never touches the source folder."
        )
        self._import_status_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._import_status_label.setWordWrap(True)
        action_row.addWidget(self._import_status_label, stretch=1)
        form_layout.addLayout(action_row)

        return form

    def _toggle_add_library_form(self) -> None:
        self._add_library_form.setVisible(not self._add_library_form.isVisible())

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Folder to scan")
        if folder:
            self._folder_edit.setText(folder)

    def _run_import(self) -> None:
        folder_text = self._folder_edit.text().strip()
        library_name = self._library_name_edit.text().strip()
        if not folder_text or not library_name:
            self._import_status_label.setText("Choose a folder and enter a library name first.")
            return

        self._scan_import_button.setEnabled(False)
        self._import_status_label.setText("Scanning...")
        format_key = self._format_combo.currentData()
        self._worker = LibraryImportWorker(
            Path(folder_text), library_name, format_key, self._database_path, self
        )
        self._worker.progress.connect(self._on_import_progress)
        self._worker.import_finished.connect(self._on_import_finished)
        self._worker.import_failed.connect(self._on_import_failed)
        self._worker.start()

    def _on_import_progress(self, completed: int, total: int) -> None:
        self._import_status_label.setText(f"Scanning... {completed}/{total}")

    def _on_import_finished(self, imported: int, skipped: int, failed: int) -> None:
        self._import_status_label.setText(
            f"Imported {imported}, skipped {skipped} already-imported, {failed} failed."
        )
        self._scan_import_button.setEnabled(True)
        self._reload_libraries()
        self.library_imported.emit()

    def _on_import_failed(self, message: str) -> None:
        self._import_status_label.setText(f"Import failed: {message}")
        self._scan_import_button.setEnabled(True)

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
    label.setStyleSheet(f"font-size: 15px; font-weight: 700; margin-top: 6px; color: {INK};")
    return label


def _readonly_item(text: str, rtl: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if rtl:
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item
