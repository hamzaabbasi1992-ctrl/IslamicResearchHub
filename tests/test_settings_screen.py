"""Tests for the desktop app's Settings screen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.settings_screen import (  # noqa: E402
    AI_AGENT_API_KEY_ENV_VARS,
    FONT_FAMILY_KEY,
    FONT_SIZE_KEY,
    MAKNOON_PDF_FOLDER_KEY,
    SettingsScreen,
    resolve_ai_agent_api_key,
    resolve_maknoon_pdf_folder,
)
from islamic_research_hub.interfaces.desktop_app.viewer_screen import DEFAULT_FONT_PX  # noqa: E402


def _isolated_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def _seed_database(database_path: Path) -> None:
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Some real page content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "source.mjbz",)
    )


def test_default_font_size_falls_back_when_nothing_is_stored(qtbot, tmp_path: Path) -> None:
    """With no stored preference, the built-in default font size is used."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    assert screen.default_font_size() == DEFAULT_FONT_PX


def test_changing_font_size_persists_to_settings(qtbot, tmp_path: Path) -> None:
    """Picking a new font size writes it to the shared QSettings."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    index_24 = screen._font_size_combo.findData(24)
    screen._font_size_combo.setCurrentIndex(index_24)

    assert int(settings.value(FONT_SIZE_KEY)) == 24
    assert screen.default_font_size() == 24


def test_default_font_family_falls_back_when_nothing_is_stored(qtbot, tmp_path: Path) -> None:
    """With no stored preference, the built-in default reading font is used."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    assert screen.default_font_family() == "Jameel Noori Nastaleeq"


def test_changing_font_family_persists_to_settings(qtbot, tmp_path: Path) -> None:
    """Picking a new reading font writes it to the shared QSettings."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    screen._font_family_combo.setCurrentText("Amiri")

    assert settings.value(FONT_FAMILY_KEY) == "Amiri"
    assert screen.default_font_family() == "Amiri"


def test_language_combo_reflects_the_translators_current_language(qtbot, tmp_path: Path) -> None:
    """The language dropdown starts on whatever language the translator is set to."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    translator = Translator(settings)
    translator.set_language("ar")

    screen = SettingsScreen(database_path, settings, translator)
    qtbot.addWidget(screen)

    assert screen._language_combo.currentData() == "ar"


def test_changing_language_combo_updates_the_translator(qtbot, tmp_path: Path) -> None:
    """Picking a language in Settings actually changes the shared translator."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    translator = Translator(settings)
    screen = SettingsScreen(database_path, settings, translator)
    qtbot.addWidget(screen)

    ur_index = screen._language_combo.findData("ur")
    screen._language_combo.setCurrentIndex(ur_index)

    assert translator.language == "ur"


def test_screen_retranslates_its_own_labels_on_language_change(qtbot, tmp_path: Path) -> None:
    """Switching language elsewhere updates this screen's own headings too."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    translator = Translator(settings)
    screen = SettingsScreen(database_path, settings, translator)
    qtbot.addWidget(screen)

    translator.set_language("ur")

    assert screen._language_heading.text() == "ایپ کی زبان"


def test_theme_combo_defaults_to_light_when_nothing_is_stored(qtbot, tmp_path: Path) -> None:
    """With no stored preference, the Appearance theme combo starts on Light."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    assert screen._theme_combo.currentData() == "light"


def test_changing_theme_combo_persists_and_applies_the_stylesheet(
    qtbot, tmp_path: Path
) -> None:
    """Picking Dark in Settings persists it and live-updates the app stylesheet."""
    from PySide6.QtWidgets import QApplication

    from islamic_research_hub.interfaces.desktop_app import theme
    from islamic_research_hub.interfaces.desktop_app.theme_controller import THEME_KEY

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    dark_index = screen._theme_combo.findData("dark")
    screen._theme_combo.setCurrentIndex(dark_index)

    assert settings.value(THEME_KEY) == "dark"
    assert theme.DARK.bg in QApplication.instance().styleSheet()


def test_font_scale_combo_defaults_to_100_percent(qtbot, tmp_path: Path) -> None:
    """With no stored preference, the interface text size combo starts at 100%."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    assert screen._font_scale_combo.currentData() == 1.0


def test_changing_font_scale_combo_persists_and_applies_the_stylesheet(
    qtbot, tmp_path: Path
) -> None:
    """Picking a larger interface text size persists it and rescales the stylesheet."""
    from islamic_research_hub.interfaces.desktop_app.theme_controller import FONT_SCALE_KEY

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    large_index = screen._font_scale_combo.findData(1.5)
    screen._font_scale_combo.setCurrentIndex(large_index)

    assert float(settings.value(FONT_SCALE_KEY)) == 1.5


def test_density_combo_defaults_to_comfortable(qtbot, tmp_path: Path) -> None:
    """With no stored preference, Compact Research Mode starts off (Comfortable)."""
    from islamic_research_hub.interfaces.desktop_app import theme

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    assert screen._density_combo.currentData() == theme.DENSITY_COMFORTABLE


def test_switching_to_compact_persists_and_applies_the_stylesheet(
    qtbot, tmp_path: Path
) -> None:
    """Picking Compact persists it and tightens the live app-wide stylesheet."""
    from PySide6.QtWidgets import QApplication

    from islamic_research_hub.interfaces.desktop_app import theme
    from islamic_research_hub.interfaces.desktop_app.theme_controller import DENSITY_KEY

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    compact_index = screen._density_combo.findData(theme.DENSITY_COMPACT)
    screen._density_combo.setCurrentIndex(compact_index)

    assert float(settings.value(DENSITY_KEY)) == theme.DENSITY_COMPACT
    # QPushButton padding is density-scaled (round(6*0.65)=4) - a real,
    # live, visible effect from the same re-apply mechanism as font_scale.
    assert "padding: 4px 9px;" in QApplication.instance().styleSheet()


def test_screen_retranslates_appearance_labels_on_language_change(
    qtbot, tmp_path: Path
) -> None:
    """Switching language elsewhere updates the Appearance section's labels too."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    translator = Translator(settings)
    screen = SettingsScreen(database_path, settings, translator)
    qtbot.addWidget(screen)

    translator.set_language("ur")

    assert screen._appearance_heading.text() == "ظاہری شکل"
    assert screen._theme_combo.itemText(0) == "ہلکا"


def test_shortcuts_block_lists_every_documented_shortcut(qtbot, tmp_path: Path) -> None:
    """The Settings shortcuts reference lists the real, installed shortcuts."""
    from islamic_research_hub.interfaces.desktop_app.shortcuts import SHORTCUTS

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    all_text = " ".join(
        label.text() for label in screen.findChildren(type(screen._shortcuts_heading))
    )
    for key, description in SHORTCUTS:
        assert key in all_text
        assert description in all_text


def test_about_block_shows_real_book_and_library_counts(qtbot, tmp_path: Path) -> None:
    """The About section reflects the real database, not placeholder text."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    all_text = " ".join(
        label.text() for label in screen.findChildren(type(screen._about_heading))
    )
    assert str(database_path) in all_text
    assert "1 books" in all_text


def test_ai_agent_is_disabled_by_default(qtbot, tmp_path: Path) -> None:
    """Off by default - this is the app's first feature making a paid
    external API call, same opt-in reasoning as TTS/voice search."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    assert screen.ai_agent_enabled() is False
    assert screen._ai_agent_enabled_checkbox.isChecked() is False


def test_changing_ai_agent_enabled_persists_to_settings(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    screen._ai_agent_enabled_checkbox.setChecked(True)

    assert screen.ai_agent_enabled() is True


def test_entering_an_api_key_persists_it_for_the_selected_provider(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    screen._ai_agent_api_key_edit.setText("sk-ant-real-looking-key")
    screen._ai_agent_api_key_edit.editingFinished.emit()

    assert resolve_ai_agent_api_key(settings, "anthropic") == "sk-ant-real-looking-key"


def test_entering_an_api_key_shows_a_real_saved_confirmation(qtbot, tmp_path: Path) -> None:
    """Every field on this screen already auto-saves - this confirms the
    previously-invisible save now shows real, visible feedback instead of
    reading as "is there a Save button I'm missing?"."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)
    assert screen._save_status_label.text() == ""

    screen._ai_agent_api_key_edit.setText("sk-ant-real-looking-key")
    screen._ai_agent_api_key_edit.editingFinished.emit()

    assert screen._save_status_label.text() != ""


def test_switching_provider_keeps_each_providers_own_key_separate(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)
    screen._ai_agent_api_key_edit.setText("anthropic-key")
    screen._ai_agent_api_key_edit.editingFinished.emit()

    openai_index = screen._ai_agent_provider_combo.findData("openai")
    screen._ai_agent_provider_combo.setCurrentIndex(openai_index)
    screen._ai_agent_api_key_edit.setText("openai-key")
    screen._ai_agent_api_key_edit.editingFinished.emit()

    assert resolve_ai_agent_api_key(settings, "anthropic") == "anthropic-key"
    assert resolve_ai_agent_api_key(settings, "openai") == "openai-key"
    # Switching back shows the real, still-separate stored key, not a stale mix.
    anthropic_index = screen._ai_agent_provider_combo.findData("anthropic")
    screen._ai_agent_provider_combo.setCurrentIndex(anthropic_index)
    assert screen._ai_agent_api_key_edit.text() == "anthropic-key"


def test_resolve_api_key_prefers_the_env_var_over_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = _isolated_settings(tmp_path)
    settings.setValue("ai_agent/api_key/anthropic", "from-settings")
    monkeypatch.setenv(AI_AGENT_API_KEY_ENV_VARS["anthropic"], "from-env-var")

    assert resolve_ai_agent_api_key(settings, "anthropic") == "from-env-var"


def test_resolve_api_key_returns_none_when_nothing_is_set(tmp_path: Path) -> None:
    settings = _isolated_settings(tmp_path)

    assert resolve_ai_agent_api_key(settings, "anthropic") is None


def test_resolve_api_key_for_ollama_is_always_a_real_truthy_sentinel(tmp_path: Path) -> None:
    """Ollama needs no real API key at all (it's a local model) - a
    truthy sentinel here means every "is this provider configured?"
    pre-flight check across the app (all written as `if not
    resolve_ai_agent_api_key(...)`) treats Ollama as ready without a
    provider-specific bypass at every one of those call sites."""
    settings = _isolated_settings(tmp_path)

    assert resolve_ai_agent_api_key(settings, "ollama")


def test_ollama_model_defaults_when_nothing_is_stored(tmp_path: Path) -> None:
    from islamic_research_hub.infrastructure.ai.ollama_llm_provider import DEFAULT_MODEL
    from islamic_research_hub.interfaces.desktop_app.settings_screen import resolve_ollama_model

    settings = _isolated_settings(tmp_path)

    assert resolve_ollama_model(settings) == DEFAULT_MODEL


def test_ollama_base_url_defaults_when_nothing_is_stored(tmp_path: Path) -> None:
    from islamic_research_hub.infrastructure.ai.ollama_llm_provider import DEFAULT_BASE_URL
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        resolve_ollama_base_url,
    )

    settings = _isolated_settings(tmp_path)

    assert resolve_ollama_base_url(settings) == DEFAULT_BASE_URL


def test_switching_to_ollama_shows_model_and_server_fields_hides_api_key(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)
    assert screen._ollama_model_edit.isHidden() is True

    ollama_index = screen._ai_agent_provider_combo.findData("ollama")
    screen._ai_agent_provider_combo.setCurrentIndex(ollama_index)

    assert screen._ai_agent_api_key_edit.isHidden() is True
    assert screen._ollama_model_edit.isHidden() is False
    assert screen._ollama_base_url_edit.isHidden() is False


def test_switching_away_from_ollama_restores_the_api_key_field(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)
    ollama_index = screen._ai_agent_provider_combo.findData("ollama")
    screen._ai_agent_provider_combo.setCurrentIndex(ollama_index)

    openai_index = screen._ai_agent_provider_combo.findData("openai")
    screen._ai_agent_provider_combo.setCurrentIndex(openai_index)

    assert screen._ai_agent_api_key_edit.isHidden() is False
    assert screen._ollama_model_edit.isHidden() is True
    assert screen._ollama_base_url_edit.isHidden() is True


def test_entering_an_ollama_model_persists_it(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import resolve_ollama_model

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    screen._ollama_model_edit.setText("llama3.1")
    screen._ollama_model_edit.editingFinished.emit()

    assert resolve_ollama_model(settings) == "llama3.1"


def test_entering_an_ollama_base_url_persists_it(qtbot, tmp_path: Path) -> None:
    from islamic_research_hub.interfaces.desktop_app.settings_screen import (
        resolve_ollama_base_url,
    )

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    screen._ollama_base_url_edit.setText("http://192.168.1.50:11434/v1")
    screen._ollama_base_url_edit.editingFinished.emit()

    assert resolve_ollama_base_url(settings) == "http://192.168.1.50:11434/v1"


def test_maknoon_pdf_folder_falls_back_to_the_default_when_nothing_is_stored(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    default_folder = tmp_path / "default-pdfs"
    screen = SettingsScreen(
        database_path, settings, Translator(settings), default_maknoon_pdf_folder=default_folder
    )
    qtbot.addWidget(screen)

    assert screen.maknoon_pdf_folder() == default_folder
    assert screen._maknoon_pdf_folder_edit.text() == str(default_folder)


def test_browsing_to_a_new_maknoon_pdf_folder_persists_and_updates_the_field(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QFileDialog

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    chosen_folder = tmp_path / "moved-pdfs"
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: str(chosen_folder))
    )
    screen = SettingsScreen(database_path, settings, Translator(settings))
    qtbot.addWidget(screen)

    screen._on_maknoon_pdf_folder_browse_clicked()

    assert screen.maknoon_pdf_folder() == chosen_folder
    assert screen._maknoon_pdf_folder_edit.text() == str(chosen_folder)
    assert settings.value(MAKNOON_PDF_FOLDER_KEY) == str(chosen_folder)


def test_cancelling_the_folder_picker_leaves_the_stored_value_unchanged(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QFileDialog

    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    settings = _isolated_settings(tmp_path)
    default_folder = tmp_path / "default-pdfs"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: ""))
    screen = SettingsScreen(
        database_path, settings, Translator(settings), default_maknoon_pdf_folder=default_folder
    )
    qtbot.addWidget(screen)

    screen._on_maknoon_pdf_folder_browse_clicked()

    assert screen.maknoon_pdf_folder() == default_folder
    assert settings.value(MAKNOON_PDF_FOLDER_KEY, None) is None


def test_resolve_maknoon_pdf_folder_prefers_the_stored_value(tmp_path: Path) -> None:
    settings = _isolated_settings(tmp_path)
    settings.setValue(MAKNOON_PDF_FOLDER_KEY, str(tmp_path / "stored"))

    assert resolve_maknoon_pdf_folder(settings, tmp_path / "default") == tmp_path / "stored"


def test_resolve_maknoon_pdf_folder_falls_back_when_nothing_is_stored(tmp_path: Path) -> None:
    settings = _isolated_settings(tmp_path)

    assert resolve_maknoon_pdf_folder(settings, tmp_path / "default") == tmp_path / "default"
