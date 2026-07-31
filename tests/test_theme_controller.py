"""Tests for `ThemeController`, the live theme/font-scale switcher."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from islamic_research_hub.interfaces.desktop_app import theme  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.theme_controller import (  # noqa: E402
    DENSITY_KEY,
    FONT_SCALE_KEY,
    THEME_KEY,
    ThemeController,
)


def _isolated_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_defaults_to_light_theme_and_full_scale(qtbot, tmp_path: Path) -> None:
    """With nothing stored, the controller starts on light / 1.0x / comfortable."""
    controller = ThemeController(_isolated_settings(tmp_path))

    assert controller.theme_name == "light"
    assert controller.font_scale == 1.0
    assert controller.density == theme.DENSITY_COMFORTABLE
    assert controller.palette() is theme.LIGHT


def test_set_density_persists_and_changes_the_stylesheet(qtbot, tmp_path: Path) -> None:
    """Compact Research Mode's toggle updates the live stylesheet and persists,
    independent of theme/font-scale."""
    settings = _isolated_settings(tmp_path)
    controller = ThemeController(settings)

    controller.set_density(theme.DENSITY_COMPACT)

    assert controller.density == theme.DENSITY_COMPACT
    assert float(settings.value(DENSITY_KEY)) == theme.DENSITY_COMPACT
    assert QApplication.instance().styleSheet() == controller.stylesheet()


def test_density_changed_signal_emits_the_new_density(qtbot, tmp_path: Path) -> None:
    """`density_changed` fires with the new value on every switch."""
    controller = ThemeController(_isolated_settings(tmp_path))

    with qtbot.waitSignal(controller.density_changed, timeout=1000) as blocker:
        controller.set_density(theme.DENSITY_COMPACT)

    assert blocker.args == [theme.DENSITY_COMPACT]


def test_a_second_controller_picks_up_previously_persisted_density(
    qtbot, tmp_path: Path
) -> None:
    """A fresh controller reads back a prior controller's persisted density."""
    settings = _isolated_settings(tmp_path)
    ThemeController(settings).set_density(theme.DENSITY_COMPACT)

    reloaded = ThemeController(_isolated_settings(tmp_path))

    assert reloaded.density == theme.DENSITY_COMPACT


def test_set_theme_persists_and_applies_to_the_running_application(
    qtbot, tmp_path: Path
) -> None:
    """Switching themes updates QApplication's live stylesheet and persists."""
    settings = _isolated_settings(tmp_path)
    controller = ThemeController(settings)

    controller.set_theme("dark")

    assert controller.theme_name == "dark"
    assert controller.palette() is theme.DARK
    assert settings.value(THEME_KEY) == "dark"
    assert theme.DARK.bg in QApplication.instance().styleSheet()


def test_set_theme_rejects_an_unknown_theme_name(qtbot, tmp_path: Path) -> None:
    """An invalid theme name raises rather than silently no-op-ing."""
    controller = ThemeController(_isolated_settings(tmp_path))

    with pytest.raises(ValueError):
        controller.set_theme("neon")


def test_set_font_scale_persists_and_changes_the_stylesheet(qtbot, tmp_path: Path) -> None:
    """Changing the font scale updates the live stylesheet and persists."""
    settings = _isolated_settings(tmp_path)
    controller = ThemeController(settings)

    controller.set_font_scale(1.5)

    assert controller.font_scale == 1.5
    assert float(settings.value(FONT_SCALE_KEY)) == 1.5
    assert QApplication.instance().styleSheet() == controller.stylesheet()


def test_a_second_controller_picks_up_previously_persisted_settings(
    qtbot, tmp_path: Path
) -> None:
    """A fresh controller reads back a prior controller's persisted choices."""
    settings = _isolated_settings(tmp_path)
    ThemeController(settings).set_theme("high_contrast")

    reloaded = ThemeController(_isolated_settings(tmp_path))

    assert reloaded.theme_name == "high_contrast"


def test_theme_changed_signal_emits_the_new_theme_name(qtbot, tmp_path: Path) -> None:
    """`theme_changed` fires with the new theme's key on every switch."""
    controller = ThemeController(_isolated_settings(tmp_path))

    with qtbot.waitSignal(controller.theme_changed, timeout=1000) as blocker:
        controller.set_theme("dark")

    assert blocker.args == ["dark"]
