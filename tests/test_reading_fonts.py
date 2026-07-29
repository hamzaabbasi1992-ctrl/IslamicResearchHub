"""Tests for resolving a reading font choice to a genuinely installed font family."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.reading_fonts import (  # noqa: E402
    FONT_CHOICES,
    resolve_installed_font_family,
)


def _ensure_app() -> None:
    """QFontDatabase needs a real QApplication instance to query fonts."""
    if QApplication.instance() is None:
        QApplication([])


def test_resolves_to_the_first_genuinely_installed_name_in_the_stack() -> None:
    """A stack whose first name isn't installed resolves to a real installed one.

    This is the exact real bug found in production: Qt's own font-family
    property does not walk a CSS-style comma list the way a browser does -
    it silently substitutes something else entirely for an unknown first
    name, ignoring the rest of the list. This function does the real walk.
    """
    _ensure_app()

    resolved = resolve_installed_font_family("'Definitely Not A Real Font XYZ', Tahoma, sans-serif")

    assert resolved == "Tahoma"


def test_falls_back_to_tahoma_when_nothing_in_the_stack_is_installed() -> None:
    """A stack with no real installed names at all still returns something usable."""
    _ensure_app()

    resolved = resolve_installed_font_family("'Nonexistent One', 'Nonexistent Two'")

    assert resolved == "Tahoma"


def test_returns_the_exact_name_when_the_first_choice_is_installed() -> None:
    """A stack whose first name is genuinely installed uses it directly."""
    _ensure_app()

    resolved = resolve_installed_font_family("Tahoma, 'Some Other Font'")

    assert resolved == "Tahoma"


def test_every_font_choice_resolves_to_a_real_installed_family() -> None:
    """Every offered choice, English/Latin included, resolves to something real -
    not silently falling through to the generic Tahoma default for all of them."""
    _ensure_app()

    for display_name, font_stack in FONT_CHOICES:
        resolved = resolve_installed_font_family(font_stack)
        assert resolved != "", display_name


def test_english_font_choices_are_offered() -> None:
    """The corpus's own English-titled/English-authored content gets real
    English reading fonts, not just the Urdu/Arabic choices."""
    display_names = {name for name, _stack in FONT_CHOICES}

    assert {"Georgia", "Cambria", "Constantia", "Calibri", "Segoe UI"} <= display_names
