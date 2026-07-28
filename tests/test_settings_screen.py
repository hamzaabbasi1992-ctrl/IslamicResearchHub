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
    FONT_FAMILY_KEY,
    FONT_SIZE_KEY,
    SettingsScreen,
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
