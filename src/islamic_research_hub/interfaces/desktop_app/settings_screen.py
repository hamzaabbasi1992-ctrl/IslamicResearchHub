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
from islamic_research_hub.interfaces.desktop_app.reading_fonts import (
    DEFAULT_FONT_CHOICE,
    FONT_CHOICES,
)
from islamic_research_hub.interfaces.desktop_app.shortcuts import SHORTCUTS
from islamic_research_hub.interfaces.desktop_app.theme import (
    DENSITY_COMFORTABLE,
    DENSITY_COMPACT,
    MUTED_LABEL_STYLE,
    Type,
)
from islamic_research_hub.interfaces.desktop_app.theme_controller import ThemeController
from islamic_research_hub.interfaces.desktop_app.viewer_screen import DEFAULT_FONT_PX

FONT_SIZE_KEY = "viewer/font_size"
FONT_FAMILY_KEY = "viewer/font_family"
FONT_SIZE_CHOICES = (14, 16, 18, 20, 22, 24, 28)
FONT_SCALE_CHOICES = (0.9, 1.0, 1.1, 1.25, 1.5)
_THEME_NAME_KEYS = (("light", "theme-light"), ("dark", "theme-dark"), ("high_contrast", "theme-high-contrast"))
_DENSITY_CHOICES = ((DENSITY_COMFORTABLE, "Comfortable"), (DENSITY_COMPACT, "Compact"))
"""Compact Research Mode: independent of the accessibility theme/font-scale
settings above - any theme x any density x any font-scale composes freely."""


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
        self._theme_controller = ThemeController(settings)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._build_language_block())
        layout.addWidget(self._build_reading_block())
        layout.addWidget(self._build_appearance_block())
        layout.addWidget(self._build_shortcuts_block())
        layout.addWidget(self._build_about_block())
        layout.addStretch(1)

        self._translator.language_changed.connect(self._retranslate)

    def _retranslate(self, _language: str) -> None:
        """Update this screen's own labels after the app language changes."""
        self._language_heading.setText(self._translator.tr("settings-language"))
        self._language_note.setText(self._translator.tr("settings-language-note"))
        self._reading_heading.setText(self._translator.tr("settings-reading"))
        self._font_size_label.setText(self._translator.tr("settings-default-font-size"))
        self._font_family_label.setText(self._translator.tr("settings-default-font-family"))
        self._appearance_heading.setText(self._translator.tr("settings-appearance"))
        self._theme_label.setText(self._translator.tr("settings-theme"))
        self._font_scale_label.setText(self._translator.tr("settings-font-scale"))
        self._density_label.setText(self._translator.tr("settings-density"))
        for row, (_theme_name, translation_key) in enumerate(_THEME_NAME_KEYS):
            self._theme_combo.setItemText(row, self._translator.tr(translation_key))
        self._shortcuts_heading.setText(self._translator.tr("settings-shortcuts"))
        self._about_heading.setText(self._translator.tr("settings-about"))

    def _build_language_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._language_heading = QLabel(self._translator.tr("settings-language"))
        self._language_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        block_layout.addWidget(self._language_heading)

        self._language_note = QLabel(self._translator.tr("settings-language-note"))
        self._language_note.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px;")
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
        self._reading_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
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

        font_row = QHBoxLayout()
        self._font_family_label = QLabel(self._translator.tr("settings-default-font-family"))
        font_row.addWidget(self._font_family_label)
        font_row.addStretch(1)
        self._font_family_combo = QComboBox()
        for display_name, _font_stack in FONT_CHOICES:
            self._font_family_combo.addItem(display_name)
        current_family = self.default_font_family()
        family_index = self._font_family_combo.findText(current_family)
        self._font_family_combo.setCurrentIndex(max(family_index, 0))
        self._font_family_combo.currentTextChanged.connect(self._on_font_family_changed)
        font_row.addWidget(self._font_family_combo)
        block_layout.addLayout(font_row)
        return block

    def _build_appearance_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._appearance_heading = QLabel(self._translator.tr("settings-appearance"))
        self._appearance_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        block_layout.addWidget(self._appearance_heading)

        theme_row = QHBoxLayout()
        self._theme_label = QLabel(self._translator.tr("settings-theme"))
        theme_row.addWidget(self._theme_label)
        theme_row.addStretch(1)
        self._theme_combo = QComboBox()
        for theme_name, translation_key in _THEME_NAME_KEYS:
            self._theme_combo.addItem(self._translator.tr(translation_key), userData=theme_name)
        theme_index = self._theme_combo.findData(self._theme_controller.theme_name)
        self._theme_combo.setCurrentIndex(max(theme_index, 0))
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self._theme_combo)
        block_layout.addLayout(theme_row)

        font_scale_row = QHBoxLayout()
        self._font_scale_label = QLabel(self._translator.tr("settings-font-scale"))
        font_scale_row.addWidget(self._font_scale_label)
        font_scale_row.addStretch(1)
        self._font_scale_combo = QComboBox()
        for scale in FONT_SCALE_CHOICES:
            self._font_scale_combo.addItem(f"{round(scale * 100)}%", userData=scale)
        scale_index = self._font_scale_combo.findData(self._theme_controller.font_scale)
        self._font_scale_combo.setCurrentIndex(scale_index if scale_index >= 0 else 1)
        self._font_scale_combo.currentIndexChanged.connect(self._on_font_scale_changed)
        font_scale_row.addWidget(self._font_scale_combo)
        block_layout.addLayout(font_scale_row)

        density_row = QHBoxLayout()
        self._density_label = QLabel(self._translator.tr("settings-density"))
        density_row.addWidget(self._density_label)
        density_row.addStretch(1)
        self._density_combo = QComboBox()
        for density_value, label in _DENSITY_CHOICES:
            self._density_combo.addItem(label, userData=density_value)
        density_index = self._density_combo.findData(self._theme_controller.density)
        self._density_combo.setCurrentIndex(density_index if density_index >= 0 else 0)
        self._density_combo.currentIndexChanged.connect(self._on_density_changed)
        density_row.addWidget(self._density_combo)
        block_layout.addLayout(density_row)
        return block

    def _build_shortcuts_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._shortcuts_heading = QLabel(self._translator.tr("settings-shortcuts"))
        self._shortcuts_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        block_layout.addWidget(self._shortcuts_heading)

        for key, description in SHORTCUTS:
            row = QHBoxLayout()
            description_label = QLabel(description)
            row.addWidget(description_label)
            row.addStretch(1)
            key_label = QLabel(key)
            key_label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-weight: 600;")
            row.addWidget(key_label)
            block_layout.addLayout(row)
        return block

    def _build_about_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._about_heading = QLabel(self._translator.tr("settings-about"))
        self._about_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        block_layout.addWidget(self._about_heading)

        libraries = self._browser.list_libraries_with_counts()
        total_books = sum(count for _name, count in libraries)
        info = QLabel(
            f"Database: {self._database_path}\n"
            f"{total_books} books across {len(libraries)} libraries"
        )
        info.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px;")
        info.setWordWrap(True)
        block_layout.addWidget(info)
        return block

    def default_font_size(self) -> int:
        """Return the persisted default reading font size, or the built-in default."""
        return int(self._settings.value(FONT_SIZE_KEY, DEFAULT_FONT_PX))

    def default_font_family(self) -> str:
        """Return the persisted default reading font family, or the built-in default."""
        return str(self._settings.value(FONT_FAMILY_KEY, DEFAULT_FONT_CHOICE))

    def _on_language_changed(self, _index: int) -> None:
        code = self._language_combo.currentData()
        self._translator.set_language(code)

    def _on_font_size_changed(self, _index: int) -> None:
        size = self._font_size_combo.currentData()
        self._settings.setValue(FONT_SIZE_KEY, size)

    def _on_font_family_changed(self, display_name: str) -> None:
        self._settings.setValue(FONT_FAMILY_KEY, display_name)

    def _on_theme_changed(self, _index: int) -> None:
        theme_name = self._theme_combo.currentData()
        self._theme_controller.set_theme(theme_name)

    def _on_font_scale_changed(self, _index: int) -> None:
        font_scale = self._font_scale_combo.currentData()
        self._theme_controller.set_font_scale(font_scale)

    def _on_density_changed(self, _index: int) -> None:
        density = self._density_combo.currentData()
        self._theme_controller.set_density(density)


def _block() -> QFrame:
    # Scoped to #settingsBlock (an ID selector), not the QFrame type selector -
    # a type selector would cascade into any QFrame-based internals of child
    # widgets (e.g. a QComboBox's popup frame), drawing a border around them too.
    # The actual colors live in the shared app-wide stylesheet (theme.py).
    frame = QFrame()
    frame.setObjectName("settingsBlock")
    return frame
