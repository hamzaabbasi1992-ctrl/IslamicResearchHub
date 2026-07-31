"""AI assistant panel: a permanent, collapsible workspace segment.

No generative AI/LLM backend exists anywhere in this codebase (confirmed:
no OpenAI/Anthropic/completion client anywhere) - only a local embedding
model used for search similarity. This panel ships its real, working
chrome now (header, collapse/expand, persisted state); real "Similar
books" content, reusing that existing embedder, is wired in a later
milestone. The question input is present but disabled and honestly
labeled "coming soon" - not faked.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.theme import Type

COLLAPSED_KEY = "appearance/ai_panel_collapsed"

_PLACEHOLDER_BODY_TEXT = "Suggestions related to the book you're reading will appear here."
_NOTES_PLACEHOLDER_TEXT = "Notes - coming soon."
_REFERENCES_PLACEHOLDER_TEXT = "References - coming soon."


class AiAssistantPanel(QWidget):
    """Collapsible AI-assistant panel: real chrome, honest placeholder content."""

    collapsed_changed = Signal(bool)

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("aiPanel")
        self._settings = settings
        self._collapsed = bool(settings.value(COLLAPSED_KEY, False, type=bool))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Assistant")
        title.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        header.addWidget(title)
        header.addStretch(1)
        self._collapse_button = QPushButton()
        self._collapse_button.setFlat(True)
        self._collapse_button.setIconSize(button_icon_size())
        self._collapse_button.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._collapse_button)
        layout.addLayout(header)

        self._body_label = EmptyStateLabel(_PLACEHOLDER_BODY_TEXT)
        layout.addWidget(self._body_label)

        self._question_edit = QLineEdit()
        self._question_edit.setPlaceholderText("Ask a question - coming soon")
        self._question_edit.setEnabled(False)
        layout.addWidget(self._question_edit)

        # Honest placeholders (Reader Redesign): real section headings so
        # the panel's future shape is visible now, disabled/labeled
        # "coming soon" rather than faked - no Notes/References backend
        # exists anywhere in this project yet.
        notes_heading = QLabel("Notes")
        notes_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_SM}px; margin-top: 8px;")
        layout.addWidget(notes_heading)
        notes_body = EmptyStateLabel(_NOTES_PLACEHOLDER_TEXT)
        layout.addWidget(notes_body)

        references_heading = QLabel("References")
        references_heading.setStyleSheet(
            f"font-weight: 700; font-size: {Type.BODY_SM}px; margin-top: 8px;"
        )
        layout.addWidget(references_heading)
        references_body = EmptyStateLabel(_REFERENCES_PLACEHOLDER_TEXT)
        layout.addWidget(references_body)

        layout.addStretch(1)

        self._update_collapse_icon()

    @property
    def is_collapsed(self) -> bool:
        """Whether the panel is currently collapsed."""
        return self._collapsed

    def toggle_collapsed(self) -> None:
        """Flip the collapsed state."""
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state, persist it, and notify listeners (the
        owning `WorkspaceScreen`'s splitter) if it actually changed."""
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._settings.setValue(COLLAPSED_KEY, collapsed)
        self._update_collapse_icon()
        self.collapsed_changed.emit(collapsed)

    def _update_collapse_icon(self) -> None:
        # Reuses the existing prev/next chevrons rather than adding a
        # dedicated collapse/expand icon pair - same visual language.
        self._collapse_button.setIcon(button_icon("next" if self._collapsed else "prev"))
