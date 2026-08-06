"""Import screen: add new libraries, real library sources.

Duplicate-candidate review lives in `duplicate_manager_screen.py` (split out
in the desktop UI redesign's Milestone 4) - this screen now covers library
ingestion only.
"""

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
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.library_import_worker import (
    FORMAT_AUTO,
    FORMAT_MAKNOON,
    FORMAT_MJBZ,
    FORMAT_PDF,
    LibraryImportWorker,
)
from islamic_research_hub.interfaces.desktop_app.theme import INK, MUTED_LABEL_STYLE

_FORMAT_CHOICES = (
    (FORMAT_AUTO, "import-format-auto"),
    (FORMAT_MJBZ, "import-format-mjbz"),
    (FORMAT_MAKNOON, "import-format-maknoon"),
    (FORMAT_PDF, "import-format-pdf"),
)


class ImportScreen(QWidget):
    """Add new libraries and show real library sources."""

    library_imported = Signal(str)  # library_name

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._worker: LibraryImportWorker | None = None
        self._pending_library_name: str = ""
        self._status_kind = "default"
        self._status_args: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        self._heading_label = _heading(self._translator.tr("library-sources"))
        header_row.addWidget(self._heading_label)
        header_row.addStretch(1)
        self._add_library_toggle = QPushButton(f"+ {self._translator.tr('add-library')}")
        self._add_library_toggle.setObjectName("primaryButton")
        self._add_library_toggle.clicked.connect(self._toggle_add_library_form)
        header_row.addWidget(self._add_library_toggle)
        layout.addLayout(header_row)

        self._add_library_form = self._build_add_library_form()
        self._add_library_form.setVisible(False)
        layout.addWidget(self._add_library_form)

        self._library_table = QTableWidget(0, 2)
        self._library_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._library_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._library_table.verticalHeader().setVisible(False)
        self._library_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # Real bug fixed here: the table used to get its own small natural
        # sizeHint while a trailing `addStretch(1)` pushed all the real
        # leftover vertical space below it instead of into the table -
        # "the whole page is empty, I still have to scroll the list" even
        # though the outer QScrollArea's viewport had plenty of real room.
        # `stretch=1` here lets the table claim that space and show far
        # more real rows before its own internal scrollbar is needed.
        layout.addWidget(self._library_table, stretch=1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    def _table_header_labels(self) -> list[str]:
        return [self._translator.tr("import-col-library"), self._translator.tr("import-col-books")]

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("library-sources"))
        self._add_library_toggle.setText(f"+ {self._translator.tr('add-library')}")
        self._browse_button.setText(self._translator.tr("browse"))
        self._folder_edit.setPlaceholderText(self._translator.tr("folder-to-scan"))
        self._format_combo.setToolTip(self._translator.tr("format"))
        for index, (_key, label_key) in enumerate(_FORMAT_CHOICES):
            self._format_combo.setItemText(index, self._translator.tr(label_key))
        self._library_name_edit.setPlaceholderText(self._translator.tr("library-name"))
        self._scan_import_button.setText(self._translator.tr("scan-import"))
        self._library_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._render_status()

    def _build_add_library_form(self) -> QFrame:
        form = QFrame()
        form.setObjectName("settingsBlock")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(14, 12, 14, 14)
        form_layout.setSpacing(8)

        folder_row = QHBoxLayout()
        self._browse_button = QPushButton(self._translator.tr("browse"))
        self._browse_button.clicked.connect(self._pick_folder)
        folder_row.addWidget(self._browse_button)
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setPlaceholderText(self._translator.tr("folder-to-scan"))
        folder_row.addWidget(self._folder_edit, stretch=1)
        form_layout.addLayout(folder_row)

        options_row = QHBoxLayout()
        self._format_combo = QComboBox()
        for key, label_key in _FORMAT_CHOICES:
            self._format_combo.addItem(self._translator.tr(label_key), userData=key)
        self._format_combo.setToolTip(self._translator.tr("format"))
        options_row.addWidget(self._format_combo)
        self._library_name_edit = QLineEdit()
        self._library_name_edit.setPlaceholderText(self._translator.tr("library-name"))
        options_row.addWidget(self._library_name_edit, stretch=1)
        form_layout.addLayout(options_row)

        action_row = QHBoxLayout()
        self._scan_import_button = QPushButton(self._translator.tr("scan-import"))
        self._scan_import_button.setObjectName("primaryButton")
        self._scan_import_button.clicked.connect(self._run_import)
        action_row.addWidget(self._scan_import_button)
        self._import_status_label = QLabel(self._translator.tr("import-status-default"))
        self._import_status_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._import_status_label.setWordWrap(True)
        action_row.addWidget(self._import_status_label, stretch=1)
        form_layout.addLayout(action_row)

        return form

    def _set_status(self, kind: str, **args: object) -> None:
        self._status_kind = kind
        self._status_args = args
        self._render_status()

    def _render_status(self) -> None:
        kind = self._status_kind
        args = self._status_args
        if kind == "missing_fields":
            text = self._translator.tr("import-missing-fields")
        elif kind == "scanning":
            text = self._translator.tr("duplicate-manager-scanning")
        elif kind == "progress":
            text = self._translator.tr("import-scanning-progress").format(**args)
        elif kind == "finished":
            text = self._translator.tr("import-finished-summary").format(**args)
        elif kind == "failed":
            text = self._translator.tr("import-failed-prefix").format(**args)
        else:
            text = self._translator.tr("import-status-default")
        self._import_status_label.setText(text)

    def _toggle_add_library_form(self) -> None:
        self._add_library_form.setVisible(not self._add_library_form.isVisible())

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, self._translator.tr("folder-to-scan"))
        if folder:
            self._folder_edit.setText(folder)

    def _run_import(self) -> None:
        folder_text = self._folder_edit.text().strip()
        library_name = self._library_name_edit.text().strip()
        if not folder_text or not library_name:
            self._set_status("missing_fields")
            return

        self._scan_import_button.setEnabled(False)
        self._set_status("scanning")
        self._pending_library_name = library_name
        format_key = self._format_combo.currentData()
        self._worker = LibraryImportWorker(
            Path(folder_text), library_name, format_key, self._database_path, self
        )
        self._worker.progress.connect(self._on_import_progress)
        self._worker.import_finished.connect(self._on_import_finished)
        self._worker.import_failed.connect(self._on_import_failed)
        self._worker.start()

    def _on_import_progress(self, completed: int, total: int) -> None:
        self._set_status("progress", completed=completed, total=total)

    def _on_import_finished(self, imported: int, skipped: int, failed: int) -> None:
        self._set_status("finished", imported=imported, skipped=skipped, failed=failed)
        self._scan_import_button.setEnabled(True)
        self._reload_libraries()
        if imported > 0:
            self.library_imported.emit(self._pending_library_name)

    def _on_import_failed(self, message: str) -> None:
        self._set_status("failed", message=message)
        self._scan_import_button.setEnabled(True)

    def refresh(self) -> None:
        """Reload the library table from the real database."""
        self._reload_libraries()

    def _reload_libraries(self) -> None:
        libraries = self._browser.list_libraries_with_counts()
        self._library_table.setRowCount(len(libraries))
        for row, (name, count) in enumerate(libraries):
            self._library_table.setItem(row, 0, _readonly_item(name, rtl=True))
            self._library_table.setItem(row, 1, _readonly_item(str(count)))


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
