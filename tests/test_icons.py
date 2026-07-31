"""Tests for the desktop app's SVG-rendered icons."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.icons import (  # noqa: E402
    _SVG_PATHS,
    button_icon,
    button_icon_size,
    rail_icon,
)


def _ensure_app() -> None:
    """QPixmap/QSvgRenderer need a real QApplication instance."""
    if QApplication.instance() is None:
        QApplication([])


def test_rail_icon_renders_both_states_for_every_rail_entry() -> None:
    """Every nav-rail icon name renders a non-null pixmap for both Off and On states."""
    _ensure_app()

    for name in ("search", "viewer", "import", "logs", "settings"):
        icon = rail_icon(name)
        assert not icon.isNull()


def test_button_icon_renders_for_every_defined_name() -> None:
    """Every SVG path entry renders as a valid, non-null single-state icon."""
    _ensure_app()

    for name in _SVG_PATHS:
        icon = button_icon(name)
        assert not icon.isNull()


def test_new_redesign_icons_render_for_both_rail_states() -> None:
    """The icons added for the UI redesign (home, dark mode, etc.) render fine
    as checkable nav-rail icons too, not just single-color button icons."""
    _ensure_app()

    for name in ("home", "duplicates", "ai-assistant", "sun", "moon", "filter", "star", "clock", "x"):
        icon = rail_icon(name)
        assert not icon.isNull()


def test_star_filled_icon_substitutes_its_own_color_as_a_fill() -> None:
    """"star-filled" uses a `{color}`-templated fill (unlike every other icon,
    which is stroke-only) - confirm it still renders cleanly at two colors."""
    _ensure_app()

    assert not button_icon("star-filled", color="#1f5c50").isNull()
    assert not button_icon("star-filled", color="#ffffff").isNull()


def test_button_icon_size_is_smaller_than_the_rail_icon_size() -> None:
    """Inline button icons render smaller than the 40x40 nav-rail icons."""
    size = button_icon_size()

    assert size.width() < 40
    assert size.height() < 40


def test_unknown_icon_name_raises_a_clear_error() -> None:
    """A typo'd icon name fails loudly (KeyError) rather than rendering blank."""
    _ensure_app()

    with pytest.raises(KeyError):
        button_icon("not-a-real-icon-name")
