"""Application-facing orchestration for the Research Notes feature.

Storage-agnostic by design: depends only on the `NotesStorage` Protocol
below, never on python-docx or any filesystem detail directly (see
`docx_writer.py` for the one storage backend this feature ships with). A
future cloud backend (Google Docs, Google Drive, OneDrive, Dropbox) would
be a second class implementing the same three methods, swapped in here
without any change to this file.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QSettings

from islamic_research_hub.interfaces.desktop_app.i18n import (
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
)

CURRENT_NOTE_FILE_KEY = "research_notes/current_file"


@dataclass(frozen=True, slots=True)
class Quotation:
    """One real selected passage, with the citation details to append alongside it."""

    book_title: str
    author: str | None
    volume: int | None
    chapter: str | None
    page_number: int | None
    selected_text: str


class NotesStorage(Protocol):
    """Contract for where note documents actually live and how a
    quotation gets appended to one - the seam a future cloud backend
    would implement instead of `docx_writer.LocalDocxStorage`."""

    def list_documents(self) -> tuple[Path, ...]:
        """Return every real note document available right now, in a stable order."""

    def create_document(self, name: str) -> Path:
        """Create a new, empty note document and return its real path."""

    def append_quotation(self, path: Path, quotation: Quotation) -> None:
        """Append one quotation to the end of an existing document - must
        never overwrite what's already there."""


class ResearchNotesManager:
    """Coordinate listing/creating note documents and appending
    quotations, plus remembering the most recently used document so
    "Open Current Notes" has something real to open."""

    def __init__(self, storage: NotesStorage, settings: QSettings | None = None) -> None:
        self._storage = storage
        self._settings = settings or QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)

    def list_documents(self) -> tuple[Path, ...]:
        """Return every real note document available right now."""
        return self._storage.list_documents()

    def create_document(self, name: str) -> Path:
        """Create a new note document and remember it as the current one."""
        path = self._storage.create_document(name)
        self._remember_current(path)
        return path

    def save_quotation(self, path: Path, quotation: Quotation) -> None:
        """Append a quotation to `path` and remember it as the current document."""
        self._storage.append_quotation(path, quotation)
        self._remember_current(path)

    def current_document(self) -> Path | None:
        """Return the most recently used note document, or None if no
        document has ever been chosen, or the remembered one was since
        deleted/moved."""
        value = self._settings.value(CURRENT_NOTE_FILE_KEY, None, type=str)
        if not value:
            return None
        path = Path(value)
        return path if path.is_file() else None

    def _remember_current(self, path: Path) -> None:
        self._settings.setValue(CURRENT_NOTE_FILE_KEY, str(path))
