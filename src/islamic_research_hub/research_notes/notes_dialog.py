"""Desktop UI for the Research Notes feature: the document picker/creator
dialog, and the "Open Current Notes" entry point - the only files in this
feature allowed to know about Qt widgets or this project's other screens.
"""

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.domain.models.book import Chapter
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.research_notes.docx_writer import LocalDocxStorage, NoteFileLockedError
from islamic_research_hub.research_notes.research_notes_manager import (
    Quotation,
    ResearchNotesManager,
)


def show_save_to_notes_dialog(
    parent: QWidget,
    browser: BookBrowserRepository,
    book_id: int,
    book_title: str,
    page_number: int,
    selected_text: str,
) -> None:
    """Entry point for the reader's "Save to Research Notes" right-click
    action: gathers the real citation details (author, volume, chapter)
    itself, shows the document picker/creator, then appends the quotation
    to whichever document was chosen - showing a friendly message instead
    of crashing if that document is currently open in Word.
    """
    metadata = browser.get_book_metadata(book_id)
    chapter_title = _find_current_chapter_title(browser.list_chapters(book_id), page_number)
    quotation = Quotation(
        book_title=book_title,
        author=metadata.author if metadata else None,
        volume=metadata.volume_number if metadata else None,
        chapter=chapter_title,
        page_number=page_number,
        selected_text=selected_text,
    )
    manager = ResearchNotesManager(LocalDocxStorage())
    dialog = _SaveToNotesDialog(parent, manager)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    path = dialog.chosen_path()
    if path is None:
        return
    try:
        manager.save_quotation(path, quotation)
    except NoteFileLockedError as error:
        QMessageBox.warning(parent, "Notes File Open", str(error))


def open_current_notes(parent: QWidget) -> None:
    """Open the most recently used note document in Word (the OS default
    handler for .docx) - lets research stay a tight loop: read a book,
    save a quotation, jump straight into Word to keep writing, come back.
    """
    manager = ResearchNotesManager(LocalDocxStorage())
    path = manager.current_document()
    if path is None:
        QMessageBox.information(
            parent, "No Notes Yet", "Save a quotation to Research Notes first."
        )
        return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


class _SaveToNotesDialog(QDialog):
    """Pick an existing note document, or create a new one - the exact
    shape the feature spec asks for: a plain list of real .docx files
    plus a "+ Create New Notes" action, always available."""

    def __init__(self, parent: QWidget, manager: ResearchNotesManager) -> None:
        super().__init__(parent)
        self.setWindowTitle("Research Notes")
        self._manager = manager
        self._selected_path: Path | None = None

        layout = QVBoxLayout(self)
        self._list = QListWidget()
        self._reload_documents()
        self._list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._list)

        create_button = QPushButton("+ Create New Notes")
        create_button.clicked.connect(self._on_create_clicked)
        layout.addWidget(create_button)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_open_clicked)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen_path(self) -> Path | None:
        """Return the note document the user picked or created, if any."""
        return self._selected_path

    def _reload_documents(self) -> None:
        self._list.clear()
        for path in self._manager.list_documents():
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            self._list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._selected_path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.accept()

    def _on_open_clicked(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        self._selected_path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.accept()

    def _on_create_clicked(self) -> None:
        name, ok = QInputDialog.getText(self, "Create New Notes", "Document name:")
        if not ok or not name.strip():
            return
        self._selected_path = self._manager.create_document(name.strip())
        self.accept()


def _find_current_chapter_title(chapters: tuple[Chapter, ...], page_number: int) -> str | None:
    """Return the title of whichever chapter contains `page_number` - the
    last chapter (across the whole real TOC, flattened) whose own page
    starts at or before it. None if the book has no TOC, or the page
    comes before every chapter's start.
    """
    candidates = [
        chapter
        for chapter in _flatten_chapters(chapters)
        if chapter.page_number is not None and chapter.page_number <= page_number
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda chapter: chapter.page_number).title


def _flatten_chapters(chapters: tuple[Chapter, ...]) -> list[Chapter]:
    flat: list[Chapter] = []
    for chapter in chapters:
        flat.append(chapter)
        flat.extend(_flatten_chapters(chapter.children))
    return flat
