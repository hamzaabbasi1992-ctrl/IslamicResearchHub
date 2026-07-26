"""Logs screen: show the real, on-disk application log, most recent first."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LOG_FILE_NAME = "islamic_research_hub.log"
MAX_LINES_SHOWN = 500


class LogsScreen(QWidget):
    """Read-only view of the app's own log file, newest entries first."""

    def __init__(self, log_directory: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._log_path = log_directory / LOG_FILE_NAME

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._status_label = QLabel()
        self._status_label.setStyleSheet("color: #7a7264;")
        header_row.addWidget(self._status_label)
        header_row.addStretch(1)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh)
        header_row.addWidget(refresh_button)
        layout.addLayout(header_row)

        self._text_area = QPlainTextEdit()
        self._text_area.setReadOnly(True)
        self._text_area.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._text_area.setFont(QFont("Consolas", 9))
        layout.addWidget(self._text_area, stretch=1)

        self.refresh()

    def refresh(self) -> None:
        """Reload the log file from disk."""
        if not self._log_path.is_file():
            self._status_label.setText(f"No log file yet at {self._log_path}")
            self._text_area.setPlainText("")
            return

        lines = self._log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        shown = lines[-MAX_LINES_SHOWN:]
        newest_first = list(reversed(shown))

        if len(lines) > MAX_LINES_SHOWN:
            self._status_label.setText(
                f"Showing the most recent {MAX_LINES_SHOWN} of {len(lines)} lines - {self._log_path}"
            )
        else:
            self._status_label.setText(f"{len(lines)} line(s) - {self._log_path}")

        self._text_area.setPlainText("\n".join(newest_first))
