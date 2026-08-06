"""Collections screen: named research collections grouping real
bookmarked pages together (Phase 14 Milestone 1: personal research
workspace).

Two real panes: a list of collections on the left (create/rename/
delete), and the selected collection's items on the right (remove item,
open in Viewer, export the whole collection as a real .docx document
with real citations).
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.collection_repository import (
    CollectionNameTakenError,
    CollectionRepository,
)
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.import_screen import _heading, _readonly_item
from islamic_research_hub.interfaces.desktop_app.list_row_button import list_row_button
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE
from islamic_research_hub.research_notes.collection_export import (
    CollectionExportItem,
    export_collection_to_docx,
)

_LEFT_PANE_WIDTH = 260


class CollectionsScreen(QWidget):
    """Browse/manage real named collections and their real items."""

    open_in_viewer_requested = Signal(int, int)  # book_id, page_number

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        collections: CollectionRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._collections = collections or CollectionRepository(database_path)
        self._selected_collection_id: int | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_left_pane())
        layout.addWidget(self._build_right_pane(), stretch=1)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    # --------------------------------------------------------------- left

    def _build_left_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("searchLeftPane")
        pane.setFixedWidth(_LEFT_PANE_WIDTH)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self._heading_label = _heading(self._translator.tr("collections-heading"))
        layout.addWidget(self._heading_label)

        self._intro_label = QLabel(self._translator.tr("collections-intro"))
        self._intro_label.setStyleSheet(MUTED_LABEL_STYLE)
        self._intro_label.setWordWrap(True)
        layout.addWidget(self._intro_label)

        self._new_collection_button = QPushButton(
            f"+ {self._translator.tr('collections-new')}"
        )
        self._new_collection_button.setObjectName("primaryButton")
        self._new_collection_button.clicked.connect(self._on_new_collection_clicked)
        layout.addWidget(self._new_collection_button)

        self._collection_list_layout = QVBoxLayout()
        self._collection_list_layout.setSpacing(4)
        layout.addLayout(self._collection_list_layout)
        layout.addStretch(1)
        return pane

    def _on_new_collection_clicked(self) -> None:
        name, confirmed = QInputDialog.getText(
            self, self._translator.tr("collections-new"), self._translator.tr("collections-name-prompt")
        )
        if not confirmed or not name.strip():
            return
        try:
            collection_id = self._collections.create_collection(name)
        except CollectionNameTakenError as error:
            QMessageBox.warning(self, self._translator.tr("collections-new"), str(error))
            return
        self._selected_collection_id = collection_id
        self.refresh()

    # -------------------------------------------------------------- right

    def _build_right_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._selected_name_label = QLabel("")
        self._selected_name_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        header_row.addWidget(self._selected_name_label, stretch=1)
        self._rename_button = QPushButton(self._translator.tr("collections-rename"))
        self._rename_button.clicked.connect(self._on_rename_clicked)
        header_row.addWidget(self._rename_button)
        self._delete_button = QPushButton(self._translator.tr("collections-delete"))
        self._delete_button.clicked.connect(self._on_delete_clicked)
        header_row.addWidget(self._delete_button)
        self._export_button = QPushButton(self._translator.tr("collections-export"))
        self._export_button.setObjectName("primaryButton")
        self._export_button.clicked.connect(self._on_export_clicked)
        header_row.addWidget(self._export_button)
        layout.addLayout(header_row)

        self._empty_state_label = EmptyStateLabel(
            self._translator.tr("collections-empty-state"), centered=True
        )
        layout.addWidget(self._empty_state_label)

        self._items_table = QTableWidget(0, 3)
        self._items_table.setHorizontalHeaderLabels(self._table_header_labels())
        self._items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._items_table.verticalHeader().setVisible(False)
        self._items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._items_table, stretch=1)

        self._show_no_selection_state()
        return pane

    def _table_header_labels(self) -> list[str]:
        return [
            self._translator.tr("collections-col-book"),
            self._translator.tr("collections-col-page"),
            self._translator.tr("collections-col-actions"),
        ]

    # ------------------------------------------------------------ actions

    def _on_rename_clicked(self) -> None:
        if self._selected_collection_id is None:
            return
        name, confirmed = QInputDialog.getText(
            self,
            self._translator.tr("collections-rename"),
            self._translator.tr("collections-name-prompt"),
            text=self._selected_name_label.text(),
        )
        if not confirmed or not name.strip():
            return
        try:
            self._collections.rename_collection(self._selected_collection_id, name)
        except CollectionNameTakenError as error:
            QMessageBox.warning(self, self._translator.tr("collections-rename"), str(error))
            return
        self.refresh()

    def _on_delete_clicked(self) -> None:
        if self._selected_collection_id is None:
            return
        confirmed = QMessageBox.question(
            self,
            self._translator.tr("collections-delete"),
            self._translator.tr("collections-delete-confirm").format(
                name=self._selected_name_label.text()
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._collections.delete_collection(self._selected_collection_id)
        self._selected_collection_id = None
        self.refresh()

    def _on_export_clicked(self) -> None:
        if self._selected_collection_id is None:
            return
        name = self._selected_name_label.text()
        default_path = str(Path.home() / "Documents" / f"{name}.docx")
        output_path_str, _filter = QFileDialog.getSaveFileName(
            self, self._translator.tr("collections-export"), default_path, "Word Document (*.docx)"
        )
        if not output_path_str:
            return
        items = self._collections.list_items(self._selected_collection_id)
        export_items = []
        for item in items:
            metadata = self._browser.get_book_metadata(item.book_id)
            detail = self._browser.get_book_detail(item.book_id)
            content = ""
            if detail is not None:
                _title, _author, pages = detail
                matching = [p for p in pages if p.page_number == item.page_number]
                if matching:
                    content = matching[0].content_f
            export_items.append(
                CollectionExportItem(
                    book_title=item.book_title,
                    author=metadata.author if metadata else None,
                    volume_number=metadata.volume_number if metadata else None,
                    page_number=item.page_number,
                    content=content,
                )
            )
        export_collection_to_docx(name, tuple(export_items), Path(output_path_str))
        QMessageBox.information(
            self,
            self._translator.tr("collections-export"),
            self._translator.tr("collections-export-done").format(path=output_path_str),
        )

    def _on_remove_item_clicked(self, book_id: int, page_number: int) -> None:
        if self._selected_collection_id is None:
            return
        self._collections.remove_item(self._selected_collection_id, book_id, page_number)
        self.refresh()

    def _on_select_collection(self, collection_id: int) -> None:
        self._selected_collection_id = collection_id
        self.refresh()

    # ------------------------------------------------------------- render

    def refresh(self) -> None:
        """Reload both panes from the real database - the collection
        list and, if one is selected, its real items."""
        while self._collection_list_layout.count():
            item = self._collection_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        collections = self._collections.list_collections()
        real_ids = {collection.collection_id for collection in collections}
        if self._selected_collection_id not in real_ids:
            self._selected_collection_id = None

        for collection in collections:
            label = f"{collection.name}  ({collection.item_count})"
            button = list_row_button(label, object_name="authorRow")
            button.setCheckable(True)
            button.setChecked(collection.collection_id == self._selected_collection_id)
            button.clicked.connect(
                lambda _checked, cid=collection.collection_id: self._on_select_collection(cid)
            )
            self._collection_list_layout.addWidget(button)

        if self._selected_collection_id is None:
            self._show_no_selection_state()
            return

        selected = next(
            (c for c in collections if c.collection_id == self._selected_collection_id), None
        )
        if selected is None:
            self._show_no_selection_state()
            return

        self._selected_name_label.setText(selected.name)
        self._rename_button.setEnabled(True)
        self._delete_button.setEnabled(True)
        self._export_button.setEnabled(True)
        self._empty_state_label.setVisible(False)
        self._items_table.setVisible(True)
        self._populate_items_table(self._selected_collection_id)

    def _show_no_selection_state(self) -> None:
        self._selected_name_label.setText("")
        self._rename_button.setEnabled(False)
        self._delete_button.setEnabled(False)
        self._export_button.setEnabled(False)
        self._empty_state_label.setVisible(True)
        self._items_table.setVisible(False)

    def _populate_items_table(self, collection_id: int) -> None:
        items = self._collections.list_items(collection_id)
        self._items_table.setRowCount(len(items))
        for row, item in enumerate(items):
            self._items_table.setItem(row, 0, _readonly_item(item.book_title, rtl=True))
            self._items_table.setItem(row, 1, _readonly_item(str(item.page_number)))

            action_row = QWidget()
            action_layout = QHBoxLayout(action_row)
            action_layout.setContentsMargins(4, 2, 4, 2)
            open_button = QPushButton(self._translator.tr("collections-open-in-viewer"))
            open_button.clicked.connect(
                lambda _checked, bid=item.book_id, page=item.page_number: (
                    self.open_in_viewer_requested.emit(bid, page)
                )
            )
            action_layout.addWidget(open_button)
            remove_button = QPushButton(self._translator.tr("collections-remove-item"))
            remove_button.clicked.connect(
                lambda _checked, bid=item.book_id, page=item.page_number: (
                    self._on_remove_item_clicked(bid, page)
                )
            )
            action_layout.addWidget(remove_button)
            self._items_table.setCellWidget(row, 2, action_row)

    def _retranslate(self, _language: str) -> None:
        self._heading_label.setText(self._translator.tr("collections-heading"))
        self._intro_label.setText(self._translator.tr("collections-intro"))
        self._new_collection_button.setText(f"+ {self._translator.tr('collections-new')}")
        self._rename_button.setText(self._translator.tr("collections-rename"))
        self._delete_button.setText(self._translator.tr("collections-delete"))
        self._export_button.setText(self._translator.tr("collections-export"))
        self._empty_state_label.setText(self._translator.tr("collections-empty-state"))
        self._items_table.setHorizontalHeaderLabels(self._table_header_labels())
        self.refresh()
