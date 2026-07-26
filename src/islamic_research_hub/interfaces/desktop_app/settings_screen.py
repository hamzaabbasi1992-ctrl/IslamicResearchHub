"""Settings screen: app language, default reading font size, and app info."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import LANGUAGES, Translator
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE
from islamic_research_hub.interfaces.desktop_app.viewer_screen import DEFAULT_FONT_PX

FONT_SIZE_KEY = "viewer/font_size"
FONT_SIZE_CHOICES = (14, 16, 18, 20, 22, 24, 28)


class SettingsScreen(QWidget):
    """Change the app language and default reading font size; show real app info."""

    def __init__(
        self,
        database_path: Path,
        settings: QSettings,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._database_path = database_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._build_language_block())
        layout.addWidget(self._build_reading_block())
        layout.addWidget(self._build_about_block())
        layout.addStretch(1)

        self._translator.language_changed.connect(self._retranslate)

    def _retranslate(self, _language: str) -> None:
        """Update this screen's own labels after the app language changes."""
        self._language_heading.setText(self._translator.tr("settings-language"))
        self._language_note.setText(self._translator.tr("settings-language-note"))
        self._reading_heading.setText(self._translator.tr("settings-reading"))
        self._font_size_label.setText(self._translator.tr("settings-default-font-size"))
        self._about_heading.setText(self._translator.tr("settings-about"))

    def _build_language_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._language_heading = QLabel(self._translator.tr("settings-language"))
        self._language_heading.setStyleSheet("font-weight: 700; font-size: 14px;")
        block_layout.addWidget(self._language_heading)

        self._language_note = QLabel(self._translator.tr("settings-language-note"))
        self._language_note.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: 11px;")
        block_layout.addWidget(self._language_note)

        row = QHBoxLayout()
        self._language_combo = QComboBox()
        for code, label in LANGUAGES.items():
            self._language_combo.addItem(label, userData=code)
        current_index = self._language_combo.findData(self._translator.language)
        self._language_combo.setCurrentIndex(max(current_index, 0))
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        row.addWidget(self._language_combo)
        row.addStretch(1)
        block_layout.addLayout(row)
        return block

    def _build_reading_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._reading_heading = QLabel(self._translator.tr("settings-reading"))
        self._reading_heading.setStyleSheet("font-weight: 700; font-size: 14px;")
        block_layout.addWidget(self._reading_heading)

        row = QHBoxLayout()
        self._font_size_label = QLabel(self._translator.tr("settings-default-font-size"))
        row.addWidget(self._font_size_label)
        row.addStretch(1)
        self._font_size_combo = QComboBox()
        for size in FONT_SIZE_CHOICES:
            self._font_size_combo.addItem(f"{size}px", userData=size)
        current_size = self.default_font_size()
        size_index = self._font_size_combo.findData(current_size)
        self._font_size_combo.setCurrentIndex(size_index if size_index >= 0 else 2)
        self._font_size_combo.currentIndexChanged.connect(self._on_font_size_changed)
        row.addWidget(self._font_size_combo)
        block_layout.addLayout(row)
        return block

    def _build_about_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._about_heading = QLabel(self._translator.tr("settings-about"))
        self._about_heading.setStyleSheet("font-weight: 700; font-size: 14px;")
        block_layout.addWidget(self._about_heading)

        libraries = self._browser.list_libraries_with_counts()
        total_books = sum(count for _name, count in libraries)
        info = QLabel(
            f"Database: {self._database_path}\n"
            f"{total_books} books across {len(libraries)} libraries"
        )
        info.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: 11px;")
        info.setWordWrap(True)
        block_layout.addWidget(info)
        return block

    def default_font_size(self) -> int:
        """Return the persisted default reading font size, or the built-in default."""
        return int(self._settings.value(FONT_SIZE_KEY, DEFAULT_FONT_PX))

    def _on_language_changed(self, _index: int) -> None:
        code = self._language_combo.currentData()
        self._translator.set_language(code)

    def _on_font_size_changed(self, _index: int) -> None:
        size = self._font_size_combo.currentData()
        self._settings.setValue(FONT_SIZE_KEY, size)


def _block() -> QFrame:
    # Scoped to #settingsBlock (an ID selector), not the QFrame type selector -
    # a type selector would cascade into any QFrame-based internals of child
    # widgets (e.g. a QComboBox's popup frame), drawing a border around them too.
    # The actual colors live in the shared app-wide stylesheet (theme.py).
    frame = QFrame()
    frame.setObjectName("settingsBlock")
    return frame
