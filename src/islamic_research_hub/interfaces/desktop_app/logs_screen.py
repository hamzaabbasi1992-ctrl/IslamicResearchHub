"""Logs screen: a friendly recent-activity view for normal users, with the
raw on-disk application log available behind an "Advanced" toggle.
"""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE
from islamic_research_hub.shared.logging_config import get_friendly_log_handler

LOG_FILE_NAME = "islamic_research_hub.log"
MAX_LINES_SHOWN = 500


class LogsScreen(QWidget):
    """Friendly recent-activity view by default; the raw log file is one
    "Advanced" click away, unchanged, for troubleshooting."""

    def __init__(
        self, log_directory: Path, translator: Translator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._log_path = log_directory / LOG_FILE_NAME
        self._translator = translator

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        self._status_label = QLabel()
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        # Real fix: this shows a real absolute log path (which can be long),
        # unwrapped - measured forcing the whole window ~890px wider than
        # needed on this machine's real log path.
        self._status_label.setWordWrap(True)
        header_row.addWidget(self._status_label)
        header_row.addStretch(1)
        self._advanced_toggle = QPushButton(self._translator.tr("logs-advanced"))
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setObjectName("navTab")
        self._advanced_toggle.toggled.connect(self._on_advanced_toggled)
        header_row.addWidget(self._advanced_toggle)
        self._refresh_button = QPushButton(self._translator.tr("logs-refresh"))
        self._refresh_button.clicked.connect(self.refresh)
        header_row.addWidget(self._refresh_button)
        layout.addLayout(header_row)

        self._view_stack = QStackedWidget()

        self._friendly_area = QPlainTextEdit()
        self._friendly_area.setReadOnly(True)
        self._friendly_area.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._view_stack.addWidget(self._friendly_area)

        self._text_area = QPlainTextEdit()
        self._text_area.setReadOnly(True)
        self._text_area.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._text_area.setFont(QFont("Consolas", 9))
        self._view_stack.addWidget(self._text_area)

        layout.addWidget(self._view_stack, stretch=1)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    def _retranslate(self, _language: str) -> None:
        """Update this screen's own labels after the app language changes."""
        self._advanced_toggle.setText(self._translator.tr("logs-advanced"))
        self._refresh_button.setText(self._translator.tr("logs-refresh"))
        self.refresh()

    def _on_advanced_toggled(self, checked: bool) -> None:
        self._view_stack.setCurrentIndex(1 if checked else 0)

    def refresh(self) -> None:
        """Reload both the friendly activity view and the raw log file."""
        self._refresh_friendly_view()
        self._refresh_raw_view()

    def _refresh_friendly_view(self) -> None:
        handler = get_friendly_log_handler()
        messages = handler.messages() if handler is not None else []
        self._friendly_area.setPlainText(
            "\n".join(messages) if messages else self._translator.tr("logs-no-activity")
        )

    def _refresh_raw_view(self) -> None:
        if not self._log_path.is_file():
            self._status_label.setText(
                self._translator.tr("logs-no-log-file").format(path=self._log_path)
            )
            self._text_area.setPlainText("")
            return

        lines = self._log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        shown = lines[-MAX_LINES_SHOWN:]
        newest_first = list(reversed(shown))

        if len(lines) > MAX_LINES_SHOWN:
            self._status_label.setText(
                self._translator.tr("logs-showing-recent").format(
                    shown=MAX_LINES_SHOWN, total=len(lines), path=self._log_path
                )
            )
        else:
            self._status_label.setText(
                self._translator.tr("logs-line-count").format(count=len(lines), path=self._log_path)
            )

        self._text_area.setPlainText("\n".join(newest_first))
