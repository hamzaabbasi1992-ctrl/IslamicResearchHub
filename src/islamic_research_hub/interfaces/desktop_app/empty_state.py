"""Shared empty-state label: consolidates the "nothing here yet" muted,
word-wrapped `QLabel` pattern that seven screens each built independently
(Search's recent-books list, Home's per-item cards, the Viewer/PDF reader's
no-book-open message, Taxonomy's no-linked-books message, ...) into one
place, so the look and behavior stay consistent as new empty states are
added.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE


class EmptyStateLabel(QLabel):
    """A muted, word-wrapped "nothing here yet" message.

    Use `centered=True` for a full-pane empty state (e.g. the reader
    before any book is open); leave it `False` for a compact empty row
    inside a list or card (e.g. "No bookmarks yet").
    """

    def __init__(
        self,
        text: str,
        *,
        centered: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        if centered:
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setStyleSheet(f"{MUTED_LABEL_STYLE} padding: 2rem;")
        else:
            self.setStyleSheet(MUTED_LABEL_STYLE)
