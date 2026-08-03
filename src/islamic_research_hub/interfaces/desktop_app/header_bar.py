"""Header bar: wordmark, real live corpus stats, and the language switcher.

Matches the Phase 4 design preview's top chrome bar. The language switcher
also exists in Settings - both write through the same `Translator`, so
either one changes the language everywhere.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import LANGUAGES, Translator
from islamic_research_hub.interfaces.desktop_app.theme import ACCENT, INK_FAINT, Type

_STAT_KEYS = ("stat-books", "stat-libraries", "stat-authors", "stat-categories", "stat-series")


class HeaderBar(QWidget):
    """Top chrome: wordmark + tagline, live stats, and language pills."""

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(20)

        wordmark_column = QVBoxLayout()
        wordmark_column.setSpacing(0)
        self._wordmark_label = QLabel("Islamic Research Hub")
        self._wordmark_label.setStyleSheet(
            f"font-family: Georgia, serif; font-size: 18px; font-weight: 700; color: {ACCENT};"
        )
        wordmark_column.addWidget(self._wordmark_label)
        self._tagline_label = QLabel(self._translator.tr("tagline"))
        self._tagline_label.setStyleSheet(f"font-size: 10px; color: {INK_FAINT};")
        wordmark_column.addWidget(self._tagline_label)
        layout.addLayout(wordmark_column)

        # Navigation fix: a real "where am I" indicator - the rail alone
        # doesn't make the current screen obvious at a glance once there
        # are 7 entries plus a 3-panel workspace inside "Search".
        self._location_label = QLabel()
        self._location_label.setStyleSheet(f"font-size: {Type.BODY_SM}px; color: {INK_FAINT};")
        layout.addWidget(self._location_label)

        self._stats_labels: list[QLabel] = []
        stats_row = QHBoxLayout()
        stats_row.setSpacing(18)
        for _ in _STAT_KEYS:
            label = QLabel()
            label.setStyleSheet(f"font-size: {Type.BODY_SM}px;")
            # Real fix: 5 stat labels side by side with no wrapping measured
            # a real ~1250px minimum on their own - the direct cause of the
            # whole window being forced open wider than the screen. Ignored
            # stops this informational row from dictating that minimum;
            # each label still shows its full real count.
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            stats_row.addWidget(label)
            self._stats_labels.append(label)
        layout.addLayout(stats_row)
        layout.addStretch(1)

        self._language_buttons: dict[str, QPushButton] = {}
        lang_row = QHBoxLayout()
        lang_row.setSpacing(2)
        for code, label_text in LANGUAGES.items():
            button = QPushButton(label_text)
            button.setCheckable(True)
            button.setObjectName("langPill")
            button.clicked.connect(lambda _checked, c=code: self._translator.set_language(c))
            lang_row.addWidget(button)
            self._language_buttons[code] = button
        layout.addLayout(lang_row)

        self._translator.language_changed.connect(self._retranslate)
        self.refresh_stats()
        self._sync_language_buttons()

    def set_current_location(self, location: str) -> None:
        """Show a real "You are here" breadcrumb for the active rail screen."""
        self._location_label.setText(f"› {location}")

    def refresh_stats(self) -> None:
        """Reload the live corpus stats from the real database."""
        stats = self._browser.get_header_stats()
        values = (
            stats.book_count,
            stats.library_count,
            stats.author_count,
            stats.category_count,
            stats.series_count,
        )
        for index, (label, key, value) in enumerate(
            zip(self._stats_labels, _STAT_KEYS, values, strict=True)
        ):
            prefix = "• " if index > 0 else ""
            label.setText(f"{prefix}{value:,} {self._translator.tr(key)}")

    def _retranslate(self, _language: str) -> None:
        self._tagline_label.setText(self._translator.tr("tagline"))
        self.refresh_stats()
        self._sync_language_buttons()

    def _sync_language_buttons(self) -> None:
        for code, button in self._language_buttons.items():
            button.setChecked(code == self._translator.language)
