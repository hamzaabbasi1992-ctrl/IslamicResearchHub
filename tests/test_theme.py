"""Tests for the design-token system in `theme.py`.

`theme.py` has no Qt dependency (it's pure string/dataclass building), so
these tests don't need a `QApplication` and run without `qtbot`.
"""

from islamic_research_hub.interfaces.desktop_app import theme


def test_backward_compatible_constants_match_the_light_palette() -> None:
    """Every pre-existing module-level color constant still resolves to
    the light palette's value, so existing `from theme import ACCENT`
    call sites keep working unchanged."""
    assert theme.BG == theme.LIGHT.bg
    assert theme.SURFACE == theme.LIGHT.surface
    assert theme.SURFACE_RAISED == theme.LIGHT.surface_raised
    assert theme.INK == theme.LIGHT.ink
    assert theme.INK_SOFT == theme.LIGHT.ink_soft
    assert theme.INK_FAINT == theme.LIGHT.ink_faint
    assert theme.ACCENT == theme.LIGHT.accent
    assert theme.ACCENT_SOFT == theme.LIGHT.accent_soft
    assert theme.ACCENT_INK == theme.LIGHT.accent_ink
    assert theme.LINE == theme.LIGHT.line
    assert theme.LINE_SOFT == theme.LIGHT.line_soft


def test_backward_compatible_constants_have_their_original_values() -> None:
    """Pin the exact original hex values, so a future palette edit can't
    silently change the shipped light theme's appearance."""
    assert theme.BG == "#ede6d6"
    assert theme.SURFACE == "#f7f3e9"
    assert theme.SURFACE_RAISED == "#ffffff"
    assert theme.INK == "#241f17"
    assert theme.ACCENT == "#1f5c50"
    assert theme.LINE == "#d9cfb8"
    assert theme.RADIUS == 8


def test_global_stylesheet_is_built_from_the_light_palette_at_default_scale() -> None:
    """`GLOBAL_STYLESHEET` is exactly `build_stylesheet(LIGHT)` - the
    module-level constant is a convenience alias, not a separate sheet."""
    assert theme.GLOBAL_STYLESHEET == theme.build_stylesheet(theme.LIGHT)


def test_build_stylesheet_embeds_every_palette_color() -> None:
    """Every `Palette` field appears somewhere in the generated stylesheet."""
    sheet = theme.build_stylesheet(theme.DARK)

    assert theme.DARK.bg in sheet
    assert theme.DARK.ink in sheet
    assert theme.DARK.accent in sheet
    assert theme.DARK.line in sheet
    assert theme.DARK.surface_raised in sheet


def test_build_stylesheet_scales_font_sizes() -> None:
    """A 2x font scale doubles (rounded) pixel font sizes in the sheet."""
    base_sheet = theme.build_stylesheet(theme.LIGHT, font_scale=1.0)
    scaled_sheet = theme.build_stylesheet(theme.LIGHT, font_scale=2.0)

    assert "font-size: 13px;" in base_sheet
    assert "font-size: 26px;" in scaled_sheet


def test_the_three_palettes_are_visually_distinct() -> None:
    """Light/dark/high-contrast don't accidentally share a background."""
    backgrounds = {theme.LIGHT.bg, theme.DARK.bg, theme.HIGH_CONTRAST.bg}

    assert len(backgrounds) == 3


def test_build_stylesheet_scales_padding_with_density() -> None:
    """Compact Research Mode's density multiplier tightens QSS padding,
    the same live-reappliable mechanism `font_scale` already uses."""
    comfortable = theme.build_stylesheet(theme.LIGHT, density=theme.DENSITY_COMFORTABLE)
    compact = theme.build_stylesheet(theme.LIGHT, density=theme.DENSITY_COMPACT)

    assert "padding: 6px 14px;" in comfortable  # QPushButton, unchanged at density 1.0
    assert "padding: 4px 9px;" in compact  # round(6*0.65)=4, round(14*0.65)=9.1->9


def test_build_stylesheet_defines_a_pressed_state_for_buttons() -> None:
    """Real gap found and fixed: no :pressed state existed for any button."""
    sheet = theme.build_stylesheet(theme.LIGHT)

    assert "QPushButton:pressed" in sheet
    assert "QPushButton:focus" in sheet


def test_build_stylesheet_defines_table_row_hover_and_selected_states() -> None:
    """Real gap found and fixed: QTableWidget rows had no hover/selected styling."""
    sheet = theme.build_stylesheet(theme.LIGHT)

    assert "QTableWidget::item:hover" in sheet
    assert "QTableWidget::item:selected" in sheet


def test_spacing_and_type_scales_are_ordered() -> None:
    """The spacing/type scales are strictly increasing, as a sanity check
    against a future typo swapping two values."""
    assert theme.Spacing.XS < theme.Spacing.SM < theme.Spacing.MD
    assert theme.Spacing.MD < theme.Spacing.LG < theme.Spacing.XL < theme.Spacing.XXL
    assert theme.Type.CAPTION < theme.Type.BODY_SM < theme.Type.BODY
    assert theme.Type.BODY < theme.Type.BODY_LG < theme.Type.H3 < theme.Type.H2 < theme.Type.H1
