"""Settings screen: app language, default reading font size, and app info."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
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
    ACCENT,
    DENSITY_COMFORTABLE,
    DENSITY_COMPACT,
    MUTED_LABEL_STYLE,
    Type,
)
from islamic_research_hub.interfaces.desktop_app.theme_controller import ThemeController
from islamic_research_hub.interfaces.desktop_app.viewer_screen import DEFAULT_FONT_PX

FONT_SIZE_KEY = "viewer/font_size"
FONT_FAMILY_KEY = "viewer/font_family"
TTS_ENABLED_KEY = "tts/enabled"
TRANSLATION_ENABLED_KEY = "translation/enabled"
VOICE_SEARCH_ENABLED_KEY = "voice_search/enabled"
AI_AGENT_ENABLED_KEY = "ai_agent/enabled"
AI_AGENT_PROVIDER_KEY = "ai_agent/provider"
MAKNOON_PDF_FOLDER_KEY = "library/maknoon_pdf_folder"
"""Real bug found and fixed 2026-08-06: this path used to be hardcoded in
`__main__.py`, silently breaking every "Open PDF" resolution for the
Maktaba Al-Maknoon text library the moment the drive it pointed at moved
or was renamed (confirmed: the user's own machine migration did exactly
this). Settings-backed instead, with the old hardcoded value still used
as the one-time default for a user who has never opened this picker -
see `_build_library_paths_block()` below."""
AI_AGENT_PROVIDERS: tuple[str, ...] = ("anthropic", "openai", "gemini", "ollama")
AI_AGENT_PROVIDER_LABELS: dict[str, str] = {
    "anthropic": "Claude (Anthropic)",
    "openai": "ChatGPT (OpenAI)",
    "gemini": "Gemini (Google)",
    "ollama": "Local (Ollama)",
}
AI_AGENT_API_KEY_ENV_VARS: dict[str, str] = {
    "anthropic": "ISLAMIC_RESEARCH_HUB_ANTHROPIC_API_KEY",
    "openai": "ISLAMIC_RESEARCH_HUB_OPENAI_API_KEY",
    "gemini": "ISLAMIC_RESEARCH_HUB_GEMINI_API_KEY",
}
"""Checked first, before the QSettings-stored key for that same provider -
lets a security-conscious user avoid ever having the key touch local
settings storage. Each provider gets its own real key, both in QSettings
and as an env var, so switching providers doesn't lose a key already
entered for another one. "ollama" deliberately has no entry here - a
local model needs no real API key at all (see `resolve_ai_agent_api_key()`)."""
OLLAMA_MODEL_KEY = "ai_agent/ollama_model"
OLLAMA_BASE_URL_KEY = "ai_agent/ollama_base_url"
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
        default_maknoon_pdf_folder: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._database_path = database_path
        self._default_maknoon_pdf_folder = default_maknoon_pdf_folder or Path()
        self._theme_controller = ThemeController(settings)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Every field on this screen already auto-saves the instant it
        # changes (QSettings.setValue in each _on_*_changed handler below)
        # - there was just never any visible confirmation that it actually
        # happened, which read as "is there a Save button I'm missing?"
        # especially for the API key field. A real, transient confirmation
        # instead of a new save-then-forget button, since the underlying
        # live-save behavior is already correct and safer (nothing to lose
        # by navigating away without remembering to click Save).
        self._save_status_label = QLabel("")
        self._save_status_label.setStyleSheet(f"color: {ACCENT}; font-weight: 600;")
        self._save_status_label.setContentsMargins(16, 6, 16, 0)
        outer.addWidget(self._save_status_label)
        self._save_status_timer = QTimer(self)
        self._save_status_timer.setSingleShot(True)
        self._save_status_timer.setInterval(1600)
        self._save_status_timer.timeout.connect(lambda: self._save_status_label.setText(""))

        # Real bug fixed here: this screen had no QScrollArea at all (every
        # other block-stacked screen in this app does) - on a real window,
        # the Keyboard Shortcuts list plus the About block below it pushed
        # the total content past the visible height with no way to reach
        # the rest, reading as "shortcuts are hidden, no way to scroll."
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(self._build_language_block())
        layout.addWidget(self._build_reading_block())
        layout.addWidget(self._build_appearance_block())
        layout.addWidget(self._build_ai_agent_block())
        layout.addWidget(self._build_library_paths_block())
        layout.addWidget(self._build_shortcuts_block())
        layout.addWidget(self._build_about_block())
        layout.addStretch(1)
        scroll_area.setWidget(content)
        outer.addWidget(scroll_area)

        self._translator.language_changed.connect(self._retranslate)

    def _retranslate(self, _language: str) -> None:
        """Update this screen's own labels after the app language changes."""
        self._language_heading.setText(self._translator.tr("settings-language"))
        self._language_note.setText(self._translator.tr("settings-language-note"))
        self._reading_heading.setText(self._translator.tr("settings-reading"))
        self._font_size_label.setText(self._translator.tr("settings-default-font-size"))
        self._font_family_label.setText(self._translator.tr("settings-default-font-family"))
        self._tts_enabled_checkbox.setText(self._translator.tr("settings-tts-enabled"))
        self._voice_search_enabled_checkbox.setText(
            self._translator.tr("settings-voice-search-enabled")
        )
        self._translation_enabled_checkbox.setText(
            self._translator.tr("settings-translation-enabled")
        )
        self._appearance_heading.setText(self._translator.tr("settings-appearance"))
        self._theme_label.setText(self._translator.tr("settings-theme"))
        self._font_scale_label.setText(self._translator.tr("settings-font-scale"))
        self._density_label.setText(self._translator.tr("settings-density"))
        for row, (_theme_name, translation_key) in enumerate(_THEME_NAME_KEYS):
            self._theme_combo.setItemText(row, self._translator.tr(translation_key))
        self._ai_agent_heading.setText(self._translator.tr("settings-ai-agent"))
        self._ai_agent_enabled_checkbox.setText(self._translator.tr("settings-ai-agent-enabled"))
        self._ai_agent_provider_label.setText(self._translator.tr("settings-ai-agent-provider"))
        self._ai_agent_api_key_label.setText(self._translator.tr("settings-ai-agent-api-key"))
        self._ai_agent_disclosure_label.setText(self._translator.tr("settings-ai-agent-disclosure"))
        self._library_paths_heading.setText(self._translator.tr("settings-library-paths"))
        self._maknoon_pdf_folder_label.setText(self._translator.tr("settings-maknoon-pdf-folder"))
        self._maknoon_pdf_folder_browse_button.setText(self._translator.tr("settings-browse"))
        self._maknoon_pdf_folder_note_label.setText(
            self._translator.tr("settings-maknoon-pdf-folder-note")
        )
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

        self._tts_enabled_checkbox = QCheckBox(self._translator.tr("settings-tts-enabled"))
        self._tts_enabled_checkbox.setChecked(self.tts_enabled())
        self._tts_enabled_checkbox.toggled.connect(self._on_tts_enabled_changed)
        block_layout.addWidget(self._tts_enabled_checkbox)

        self._voice_search_enabled_checkbox = QCheckBox(
            self._translator.tr("settings-voice-search-enabled")
        )
        self._voice_search_enabled_checkbox.setChecked(self.voice_search_enabled())
        self._voice_search_enabled_checkbox.toggled.connect(
            self._on_voice_search_enabled_changed
        )
        block_layout.addWidget(self._voice_search_enabled_checkbox)

        self._translation_enabled_checkbox = QCheckBox(
            self._translator.tr("settings-translation-enabled")
        )
        self._translation_enabled_checkbox.setChecked(self.translation_enabled())
        self._translation_enabled_checkbox.toggled.connect(
            self._on_translation_enabled_changed
        )
        block_layout.addWidget(self._translation_enabled_checkbox)
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

    def _build_ai_agent_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._ai_agent_heading = QLabel(self._translator.tr("settings-ai-agent"))
        self._ai_agent_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        block_layout.addWidget(self._ai_agent_heading)

        self._ai_agent_enabled_checkbox = QCheckBox(
            self._translator.tr("settings-ai-agent-enabled")
        )
        self._ai_agent_enabled_checkbox.setChecked(self.ai_agent_enabled())
        self._ai_agent_enabled_checkbox.toggled.connect(self._on_ai_agent_enabled_changed)
        block_layout.addWidget(self._ai_agent_enabled_checkbox)

        provider_row = QHBoxLayout()
        self._ai_agent_provider_label = QLabel(self._translator.tr("settings-ai-agent-provider"))
        provider_row.addWidget(self._ai_agent_provider_label)
        self._ai_agent_provider_combo = QComboBox()
        for provider in AI_AGENT_PROVIDERS:
            self._ai_agent_provider_combo.addItem(
                AI_AGENT_PROVIDER_LABELS[provider], userData=provider
            )
        provider_index = self._ai_agent_provider_combo.findData(self.ai_agent_provider())
        self._ai_agent_provider_combo.setCurrentIndex(max(provider_index, 0))
        self._ai_agent_provider_combo.currentIndexChanged.connect(
            self._on_ai_agent_provider_changed
        )
        provider_row.addWidget(self._ai_agent_provider_combo, stretch=1)
        block_layout.addLayout(provider_row)

        key_row = QHBoxLayout()
        self._ai_agent_api_key_label = QLabel(self._translator.tr("settings-ai-agent-api-key"))
        key_row.addWidget(self._ai_agent_api_key_label)
        self._ai_agent_api_key_edit = QLineEdit()
        self._ai_agent_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._ai_agent_api_key_edit.setText(self._stored_api_key_for(self.ai_agent_provider()))
        self._ai_agent_api_key_edit.editingFinished.connect(self._on_ai_agent_api_key_changed)
        key_row.addWidget(self._ai_agent_api_key_edit, stretch=1)
        block_layout.addLayout(key_row)

        # Ollama-only fields (no real API key - a local model needs a
        # model name and a server address instead). Visible only when
        # "ollama" is the selected provider, same `setVisible()`-gating
        # philosophy this app already uses everywhere else for opt-in
        # AI features - see `_apply_ai_agent_provider_field_visibility()`.
        model_row = QHBoxLayout()
        self._ollama_model_label = QLabel(self._translator.tr("settings-ollama-model"))
        model_row.addWidget(self._ollama_model_label)
        self._ollama_model_edit = QLineEdit()
        self._ollama_model_edit.setText(self.ollama_model())
        self._ollama_model_edit.editingFinished.connect(self._on_ollama_model_changed)
        model_row.addWidget(self._ollama_model_edit, stretch=1)
        block_layout.addLayout(model_row)

        base_url_row = QHBoxLayout()
        self._ollama_base_url_label = QLabel(self._translator.tr("settings-ollama-base-url"))
        base_url_row.addWidget(self._ollama_base_url_label)
        self._ollama_base_url_edit = QLineEdit()
        self._ollama_base_url_edit.setText(self.ollama_base_url())
        self._ollama_base_url_edit.editingFinished.connect(self._on_ollama_base_url_changed)
        base_url_row.addWidget(self._ollama_base_url_edit, stretch=1)
        block_layout.addLayout(base_url_row)

        self._apply_ai_agent_provider_field_visibility()

        self._ai_agent_disclosure_label = QLabel(
            self._translator.tr("settings-ai-agent-disclosure")
        )
        self._ai_agent_disclosure_label.setStyleSheet(
            f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px;"
        )
        self._ai_agent_disclosure_label.setWordWrap(True)
        block_layout.addWidget(self._ai_agent_disclosure_label)
        return block

    def _build_library_paths_block(self) -> QFrame:
        block = _block()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(14, 12, 14, 14)
        block_layout.setSpacing(6)
        self._library_paths_heading = QLabel(self._translator.tr("settings-library-paths"))
        self._library_paths_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        block_layout.addWidget(self._library_paths_heading)

        self._maknoon_pdf_folder_label = QLabel(
            self._translator.tr("settings-maknoon-pdf-folder")
        )
        block_layout.addWidget(self._maknoon_pdf_folder_label)

        folder_row = QHBoxLayout()
        self._maknoon_pdf_folder_edit = QLineEdit()
        self._maknoon_pdf_folder_edit.setReadOnly(True)
        self._maknoon_pdf_folder_edit.setText(str(self.maknoon_pdf_folder()))
        folder_row.addWidget(self._maknoon_pdf_folder_edit, stretch=1)
        self._maknoon_pdf_folder_browse_button = QPushButton(
            self._translator.tr("settings-browse")
        )
        self._maknoon_pdf_folder_browse_button.clicked.connect(
            self._on_maknoon_pdf_folder_browse_clicked
        )
        folder_row.addWidget(self._maknoon_pdf_folder_browse_button)
        block_layout.addLayout(folder_row)

        self._maknoon_pdf_folder_note_label = QLabel(
            self._translator.tr("settings-maknoon-pdf-folder-note")
        )
        self._maknoon_pdf_folder_note_label.setStyleSheet(
            f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px;"
        )
        self._maknoon_pdf_folder_note_label.setWordWrap(True)
        block_layout.addWidget(self._maknoon_pdf_folder_note_label)
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

    def tts_enabled(self) -> bool:
        """Return whether the user has turned on read-pages-aloud (off by default -
        it's an optional local model download, not something to start silently)."""
        return bool(self._settings.value(TTS_ENABLED_KEY, False, type=bool))

    def voice_search_enabled(self) -> bool:
        """Return whether the user has turned on spoken search queries (off by
        default - same reasoning as `tts_enabled()`: an optional local model
        download, not something to start silently)."""
        return bool(self._settings.value(VOICE_SEARCH_ENABLED_KEY, False, type=bool))

    def translation_enabled(self) -> bool:
        """Return whether the user has turned on Translate to English (off
        by default - same reasoning as `tts_enabled()`: an optional local
        model download, not something to start silently)."""
        return bool(self._settings.value(TRANSLATION_ENABLED_KEY, False, type=bool))

    def ai_agent_enabled(self) -> bool:
        """Return whether the user has turned on the AI Agent (off by
        default - it's the app's first feature making a paid external API
        call, not something to start silently)."""
        return bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))

    def ai_agent_provider(self) -> str:
        """Return the currently selected AI Agent provider code."""
        return str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )

    def ollama_model(self) -> str:
        """Return the real Ollama model name currently in effect."""
        return resolve_ollama_model(self._settings)

    def ollama_base_url(self) -> str:
        """Return the real Ollama server URL currently in effect."""
        return resolve_ollama_base_url(self._settings)

    def maknoon_pdf_folder(self) -> Path:
        """Return the real Maknoon PDF Archive folder currently in
        effect - whatever the user picked here, or the app's own
        hardcoded default if they never have (see `resolve_maknoon_pdf_folder()`)."""
        return resolve_maknoon_pdf_folder(self._settings, self._default_maknoon_pdf_folder)

    def _on_maknoon_pdf_folder_browse_clicked(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, self._translator.tr("settings-maknoon-pdf-folder"), str(self.maknoon_pdf_folder())
        )
        if not chosen:
            return
        self._settings.setValue(MAKNOON_PDF_FOLDER_KEY, chosen)
        self._maknoon_pdf_folder_edit.setText(chosen)
        self._flash_saved()

    def _stored_api_key_for(self, provider: str) -> str:
        return str(self._settings.value(_ai_agent_api_key_settings_key(provider), "", type=str))

    def _on_language_changed(self, _index: int) -> None:
        code = self._language_combo.currentData()
        self._translator.set_language(code)

    def _flash_saved(self) -> None:
        """Show a brief, real confirmation that a change was actually
        persisted - every field on this screen already auto-saves, this
        just makes that visible instead of silent."""
        self._save_status_label.setText(self._translator.tr("settings-saved"))
        self._save_status_timer.start()

    def _on_font_size_changed(self, _index: int) -> None:
        size = self._font_size_combo.currentData()
        self._settings.setValue(FONT_SIZE_KEY, size)
        self._flash_saved()

    def _on_font_family_changed(self, display_name: str) -> None:
        self._settings.setValue(FONT_FAMILY_KEY, display_name)
        self._flash_saved()

    def _on_tts_enabled_changed(self, checked: bool) -> None:
        self._settings.setValue(TTS_ENABLED_KEY, checked)
        self._flash_saved()

    def _on_voice_search_enabled_changed(self, checked: bool) -> None:
        self._settings.setValue(VOICE_SEARCH_ENABLED_KEY, checked)
        self._flash_saved()

    def _on_translation_enabled_changed(self, checked: bool) -> None:
        self._settings.setValue(TRANSLATION_ENABLED_KEY, checked)
        self._flash_saved()

    def _on_ai_agent_enabled_changed(self, checked: bool) -> None:
        self._settings.setValue(AI_AGENT_ENABLED_KEY, checked)
        self._flash_saved()

    def _on_ai_agent_provider_changed(self, _index: int) -> None:
        provider = self._ai_agent_provider_combo.currentData()
        self._settings.setValue(AI_AGENT_PROVIDER_KEY, provider)
        # Show *that* provider's own stored key, not the previous one's -
        # each provider keeps its own real key, switching never loses or
        # overwrites another provider's already-entered key.
        self._ai_agent_api_key_edit.setText(self._stored_api_key_for(provider))
        self._apply_ai_agent_provider_field_visibility()
        self._flash_saved()

    def _apply_ai_agent_provider_field_visibility(self) -> None:
        """Real API key fields for the 3 cloud providers, model/server
        fields for Ollama - never both at once, since a local model
        needs no real API key at all."""
        is_ollama = self.ai_agent_provider() == "ollama"
        self._ai_agent_api_key_label.setVisible(not is_ollama)
        self._ai_agent_api_key_edit.setVisible(not is_ollama)
        self._ollama_model_label.setVisible(is_ollama)
        self._ollama_model_edit.setVisible(is_ollama)
        self._ollama_base_url_label.setVisible(is_ollama)
        self._ollama_base_url_edit.setVisible(is_ollama)

    def _on_ollama_model_changed(self) -> None:
        self._settings.setValue(OLLAMA_MODEL_KEY, self._ollama_model_edit.text())
        self._flash_saved()

    def _on_ollama_base_url_changed(self) -> None:
        self._settings.setValue(OLLAMA_BASE_URL_KEY, self._ollama_base_url_edit.text())
        self._flash_saved()

    def _on_ai_agent_api_key_changed(self) -> None:
        provider = self._ai_agent_provider_combo.currentData()
        self._settings.setValue(
            _ai_agent_api_key_settings_key(provider), self._ai_agent_api_key_edit.text()
        )
        self._flash_saved()

    def _on_theme_changed(self, _index: int) -> None:
        theme_name = self._theme_combo.currentData()
        self._theme_controller.set_theme(theme_name)
        self._flash_saved()

    def _on_font_scale_changed(self, _index: int) -> None:
        font_scale = self._font_scale_combo.currentData()
        self._theme_controller.set_font_scale(font_scale)
        self._flash_saved()

    def _on_density_changed(self, _index: int) -> None:
        density = self._density_combo.currentData()
        self._theme_controller.set_density(density)
        self._flash_saved()


def _ai_agent_api_key_settings_key(provider: str) -> str:
    return f"ai_agent/api_key/{provider}"


def resolve_ai_agent_api_key(settings: QSettings, provider: str) -> str | None:
    """Return the real API key to use for `provider`, or None if none is
    set anywhere.

    Checks that provider's own env var first (lets a security-conscious
    user avoid ever storing the key in QSettings), falls back to the
    QSettings-stored value from the Settings screen.

    "ollama" always returns a real, non-empty sentinel rather than a
    stored key - a local model needs no real API key at all, but every
    "is this provider configured?" pre-flight check across this app
    (`main_window.py`'s AI-generation handlers, `ai_panel_screen.py`'s
    lazy-build) treats a falsy return as "not configured, don't
    proceed" - returning a real value here means Ollama never has to
    duplicate that same gate with a provider-specific bypass everywhere
    it's checked.
    """
    if provider == "ollama":
        return "ollama-local"
    import os

    env_var = AI_AGENT_API_KEY_ENV_VARS.get(provider)
    if env_var:
        env_value = os.environ.get(env_var, "").strip()
        if env_value:
            return env_value
    settings_value = str(
        settings.value(_ai_agent_api_key_settings_key(provider), "", type=str)
    ).strip()
    return settings_value or None


def resolve_ollama_model(settings: QSettings) -> str:
    """Return the real Ollama model name to use - whatever the user has
    entered in Settings, or a real, well-established tool-calling-
    capable default if they haven't."""
    from islamic_research_hub.infrastructure.ai.ollama_llm_provider import DEFAULT_MODEL

    stored = str(settings.value(OLLAMA_MODEL_KEY, "", type=str)).strip()
    return stored or DEFAULT_MODEL


def resolve_ollama_base_url(settings: QSettings) -> str:
    """Return the real Ollama server URL to use - whatever the user has
    entered in Settings, or Ollama's own default local address."""
    from islamic_research_hub.infrastructure.ai.ollama_llm_provider import DEFAULT_BASE_URL

    stored = str(settings.value(OLLAMA_BASE_URL_KEY, "", type=str)).strip()
    return stored or DEFAULT_BASE_URL


def resolve_maknoon_pdf_folder(settings: QSettings, default: Path) -> Path:
    """Return the real Maknoon PDF Archive folder to use: whatever the
    user has picked via Settings, or `default` (the app entry point's
    own hardcoded fallback) if they've never opened the picker.

    Called from `__main__.py` before `MainWindow` exists, same reason
    `resolve_ai_agent_api_key()` is a free function here rather than a
    `SettingsScreen` instance method.
    """
    stored = str(settings.value(MAKNOON_PDF_FOLDER_KEY, "", type=str)).strip()
    return Path(stored) if stored else default


def _block() -> QFrame:
    # Scoped to #settingsBlock (an ID selector), not the QFrame type selector -
    # a type selector would cascade into any QFrame-based internals of child
    # widgets (e.g. a QComboBox's popup frame), drawing a border around them too.
    # The actual colors live in the shared app-wide stylesheet (theme.py).
    frame = QFrame()
    frame.setObjectName("settingsBlock")
    return frame
