"""Tests for the desktop app's language switching (Translator)."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings, Qt  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.i18n import (  # noqa: E402
    DEFAULT_LANGUAGE,
    Translator,
)


def _isolated_settings(tmp_path: Path) -> QSettings:
    """A real QSettings backed by a temp ini file, never touching the real registry."""
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_defaults_to_english_with_no_stored_preference(tmp_path: Path) -> None:
    """A fresh install with nothing stored defaults to English, LTR."""
    translator = Translator(_isolated_settings(tmp_path))

    assert translator.language == DEFAULT_LANGUAGE
    assert translator.layout_direction == Qt.LayoutDirection.LeftToRight


def test_set_language_updates_current_language_and_direction(tmp_path: Path) -> None:
    """Switching to Urdu changes both the language and the layout direction."""
    translator = Translator(_isolated_settings(tmp_path))

    translator.set_language("ur")

    assert translator.language == "ur"
    assert translator.layout_direction == Qt.LayoutDirection.RightToLeft


def test_arabic_is_also_right_to_left(tmp_path: Path) -> None:
    """Arabic, like Urdu, lays out right-to-left."""
    translator = Translator(_isolated_settings(tmp_path))

    translator.set_language("ar")

    assert translator.layout_direction == Qt.LayoutDirection.RightToLeft


def test_set_language_emits_signal(tmp_path: Path, qtbot) -> None:
    """Changing language notifies listeners via language_changed."""
    translator = Translator(_isolated_settings(tmp_path))

    with qtbot.waitSignal(translator.language_changed, timeout=1000) as blocker:
        translator.set_language("ar")

    assert blocker.args == ["ar"]


def test_set_language_does_not_emit_when_unchanged(tmp_path: Path, qtbot) -> None:
    """Setting the same language again is a no-op, not a redundant signal."""
    translator = Translator(_isolated_settings(tmp_path))
    received = []
    translator.language_changed.connect(received.append)

    translator.set_language(DEFAULT_LANGUAGE)

    assert received == []


def test_set_language_ignores_unknown_language_code(tmp_path: Path) -> None:
    """An invalid language code is ignored, not silently accepted."""
    translator = Translator(_isolated_settings(tmp_path))

    translator.set_language("fr")

    assert translator.language == DEFAULT_LANGUAGE


def test_tr_falls_back_to_english_for_missing_key(tmp_path: Path) -> None:
    """A key with no translation in the current language falls back to English."""
    translator = Translator(_isolated_settings(tmp_path))
    translator.set_language("ur")

    assert translator.tr("rail-search") == "تلاش"


def test_language_choice_persists_across_translator_instances(tmp_path: Path) -> None:
    """A saved preference is picked up by a fresh Translator (e.g. on next launch)."""
    settings = _isolated_settings(tmp_path)
    Translator(settings).set_language("ar")

    second_translator = Translator(settings)

    assert second_translator.language == "ar"
