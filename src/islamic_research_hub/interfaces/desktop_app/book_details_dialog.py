"""Book Details dialog: every real catalog field for one book."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QPushButton, QVBoxLayout

from islamic_research_hub.domain.models.book_metadata import BookMetadata


class BookDetailsDialog(QDialog):
    """A simple, read-only dialog showing one book's full catalog metadata."""

    def __init__(self, metadata: BookMetadata, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(metadata.title or "Book details")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        title_label = QLabel(metadata.title or "(untitled)")
        title_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        title_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        form = QFormLayout()
        form.addRow("Author:", _value_label(metadata.author))
        form.addRow("Publisher:", _value_label(metadata.publisher))
        form.addRow("Language:", _value_label(metadata.language))
        form.addRow("Category:", _value_label(metadata.category))
        form.addRow("Library:", _value_label(metadata.library))
        if metadata.series_title:
            series_text = metadata.series_title
            if metadata.volume_number is not None:
                series_text += f" (volume {metadata.volume_number})"
            form.addRow("Series:", _value_label(series_text))
        form.addRow("Pages:", _value_label(str(metadata.page_count)))
        form.addRow("Chapters:", _value_label(str(metadata.chapter_count)))
        layout.addLayout(form)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)


def _value_label(text: str | None) -> QLabel:
    label = QLabel(text or "Unknown")
    label.setWordWrap(True)
    label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    return label
