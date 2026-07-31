"""Shared visual theme: design tokens (palette/spacing/type) and the global
Qt stylesheet built from them.

Centralizes the colors/fonts every screen was previously hardcoding its own
(slightly inconsistent) copies of, and provides the one global Qt stylesheet
applied at the `QApplication` level in `__main__.py`. Screens still set
`objectName`s for the few widgets that need a specific look (cards, the nav
rail, primary buttons) - the actual colors live only here.

The stylesheet is generated from a `Palette` so a second (dark) or third
(high-contrast) theme is just a different `Palette` instance passed to
`build_stylesheet()`, not a parallel stylesheet to maintain. The original
flat, single-palette module-level constants (`BG`, `INK`, `ACCENT`, ...)
are kept as aliases onto `LIGHT` so every existing `from theme import ...`
call site keeps working unchanged.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """A named set of colors the stylesheet is built from."""

    bg: str
    surface: str
    surface_raised: str
    surface_hover: str
    ink: str
    ink_soft: str
    ink_faint: str
    accent: str
    accent_soft: str
    accent_ink: str
    line: str
    line_soft: str
    danger: str
    success: str
    warning: str


LIGHT = Palette(
    bg="#ede6d6",
    surface="#f7f3e9",
    surface_raised="#ffffff",
    surface_hover="#e6dfcc",
    ink="#241f17",
    ink_soft="#5b5346",
    ink_faint="#948c78",
    accent="#1f5c50",
    accent_soft="#dce8e2",
    accent_ink="#0f342d",
    line="#d9cfb8",
    line_soft="#e6dfcc",
    danger="#a13a3a",
    success="#2f6f4f",
    warning="#a3711f",
)

DARK = Palette(
    bg="#1b1a17",
    surface="#242320",
    surface_raised="#2c2b27",
    surface_hover="#38362f",
    ink="#f1ede2",
    ink_soft="#c9c2af",
    ink_faint="#8d8672",
    accent="#4fae97",
    accent_soft="#26433a",
    accent_ink="#bfe9dc",
    line="#3d3b34",
    line_soft="#332f28",
    danger="#d97a7a",
    success="#6fbf94",
    warning="#d9a94f",
)

HIGH_CONTRAST = Palette(
    bg="#000000",
    surface="#0a0a0a",
    surface_raised="#000000",
    surface_hover="#262626",
    ink="#ffffff",
    ink_soft="#ffffff",
    ink_faint="#dddddd",
    accent="#ffd60a",
    accent_soft="#3a3200",
    accent_ink="#ffd60a",
    line="#ffffff",
    line_soft="#8a8a8a",
    danger="#ff6b6b",
    success="#7cffb2",
    warning="#ffd60a",
)


class Spacing:
    """A 4px spacing grid, for consistent gaps/margins across new layouts."""

    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Type:
    """Font-size scale (px, before `font_scale` is applied)."""

    CAPTION = 11
    BODY_SM = 12
    BODY = 13
    BODY_LG = 14
    H3 = 18
    H2 = 22
    H1 = 28


RADIUS_SM = 4
RADIUS = 8
RADIUS_LG = 12

# Backward-compatible aliases onto the light palette - every existing
# `from islamic_research_hub.interfaces.desktop_app.theme import X` call
# site keeps working with its original value.
BG = LIGHT.bg
SURFACE = LIGHT.surface
SURFACE_RAISED = LIGHT.surface_raised
INK = LIGHT.ink
INK_SOFT = LIGHT.ink_soft
INK_FAINT = LIGHT.ink_faint
ACCENT = LIGHT.accent
ACCENT_SOFT = LIGHT.accent_soft
ACCENT_INK = LIGHT.accent_ink
LINE = LIGHT.line
LINE_SOFT = LIGHT.line_soft

RTL_FONT_FAMILY = (
    "'Noto Nastaliq Urdu', 'Jameel Noori Nastaliq', Tahoma, 'Segoe UI', sans-serif"
)

MUTED_LABEL_STYLE = f"color: {INK_FAINT};"
"""Shared style for small secondary/meta text (status lines, captions, hints)."""

RTL_TEXT_STYLE = f"font-family: {RTL_FONT_FAMILY};"
"""Shared style for labels displaying Arabic/Urdu book content or titles."""


DENSITY_COMFORTABLE = 1.0
DENSITY_COMPACT = 0.65
"""Multipliers for `build_stylesheet()`'s `density` parameter - Comfortable
is today's unchanged spacing; Compact tightens every QSS-driven padding/
margin for Compact Research Mode (Milestone 6)."""


def build_stylesheet(palette: Palette, font_scale: float = 1.0, density: float = 1.0) -> str:
    """Build the global Qt stylesheet for the given palette, font scale, and density.

    `font_scale` multiplies every font-size in the sheet, rounded to the
    nearest pixel - used for the app-chrome accessibility scale setting,
    independent of the reading-content font size in the Viewer.

    `density` multiplies every QSS-driven padding/spacing value the same
    way - `DENSITY_COMPACT` (Compact Research Mode) tightens chrome
    padding app-wide the instant the stylesheet is re-applied, the same
    live mechanism `font_scale` already uses. Per-screen Python layout
    margins (card contents margins, results-list spacing) are a
    separate, coarser-grained concern - see each screen's own density
    handling.
    """

    def px(base_size: float) -> str:
        return f"{round(base_size * font_scale)}px"

    def sp(base_size: float) -> str:
        return f"{max(0, round(base_size * density))}px"

    return f"""
QMainWindow {{
    background: {palette.bg};
}}

QWidget {{
    color: {palette.ink};
    font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
    font-size: {px(Type.BODY)};
}}

QLabel, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

#headerBar {{
    background: {palette.surface};
    border-bottom: 1px solid {palette.line};
}}
#headerBar QLabel {{
    color: {palette.ink_soft};
}}
#langPill {{
    background: transparent;
    border: none;
    border-radius: 999px;
    padding: {sp(4)} {sp(10)};
    font-size: {px(Type.CAPTION)};
    font-weight: 600;
    color: {palette.ink_soft};
}}
#langPill:hover {{
    background: {palette.line_soft};
    color: {palette.ink};
}}
#langPill:checked {{
    background: {palette.accent};
    color: {palette.surface_raised};
}}

#navRail {{
    background: {palette.surface};
    border-right: 1px solid {palette.line};
}}
#navRail QToolButton {{
    background: transparent;
    border: none;
    border-radius: {RADIUS}px;
    color: {palette.ink_soft};
    padding: {sp(10)} {sp(6)};
    font-size: {px(Type.BODY_SM)};
    font-weight: 600;
}}
#navRail QToolButton:hover {{
    background: {palette.line_soft};
    color: {palette.ink};
}}
#navRail QToolButton:checked {{
    background: {palette.accent_soft};
    color: {palette.accent_ink};
}}

QPushButton {{
    background: {palette.surface_raised};
    border: 1px solid {palette.line};
    border-radius: 6px;
    padding: {sp(6)} {sp(14)};
    color: {palette.ink_soft};
}}
QPushButton:hover {{
    border-color: {palette.accent};
    color: {palette.ink};
}}
QPushButton:pressed {{
    background: {palette.accent_soft};
    border-color: {palette.accent};
    color: {palette.accent_ink};
}}
QPushButton:focus {{
    border: 1px solid {palette.accent};
    outline: none;
}}
QPushButton:disabled {{
    color: {palette.ink_faint};
    border-color: {palette.line_soft};
}}
QPushButton:default, QPushButton#primaryButton {{
    background: {palette.accent};
    border: 1px solid {palette.accent};
    color: {palette.surface_raised};
    font-weight: 600;
}}
QPushButton:default:hover, QPushButton#primaryButton:hover {{
    background: {palette.accent_ink};
    border-color: {palette.accent_ink};
    color: {palette.surface_raised};
}}
QPushButton:default:pressed, QPushButton#primaryButton:pressed {{
    background: {palette.accent_ink};
    border-color: {palette.accent_ink};
    color: {palette.surface_raised};
}}

#searchLeftPane {{
    background: {palette.surface};
    border: none;
    border-right: 1px solid {palette.line};
}}
#navTab {{
    background: {palette.bg};
    border: none;
    border-radius: 5px;
    padding: {sp(5)} {sp(8)};
    font-size: {px(Type.CAPTION)};
    font-weight: 600;
    color: {palette.ink_soft};
}}
#navTab:hover {{
    background: {palette.line_soft};
    color: {palette.ink};
}}
#navTab:checked {{
    background: {palette.surface_raised};
    color: {palette.accent_ink};
}}
#authorRow, #libraryChip {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: {sp(4)} {sp(6)};
    text-align: left;
    font-size: {px(Type.CAPTION)};
    color: {palette.ink_soft};
}}
#authorRow:hover, #libraryChip:hover {{
    background: {palette.line_soft};
    color: {palette.ink};
}}

QTreeWidget {{
    background: transparent;
    border: none;
    font-size: {px(Type.BODY_SM)};
}}
QTreeWidget::item {{
    padding: {sp(3)} {sp(2)};
    border-radius: 4px;
}}
QTreeWidget::item:hover {{
    background: {palette.line_soft};
}}
QTreeWidget::item:selected {{
    background: {palette.accent_soft};
    color: {palette.accent_ink};
}}

QLineEdit, QComboBox {{
    background: {palette.surface_raised};
    border: 1px solid {palette.line};
    border-radius: 6px;
    padding: {sp(6)} {sp(8)};
    color: {palette.ink};
    selection-background-color: {palette.accent_soft};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {palette.accent};
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: {palette.ink_faint};
    background: {palette.surface};
    border-color: {palette.line_soft};
}}
#mainSearchBox {{
    font-size: {px(Type.H3 - 2)};
    padding: {sp(8)} {sp(12)};
    border-radius: 8px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {palette.surface_raised};
    border: 1px solid {palette.line};
    selection-background-color: {palette.accent_soft};
    selection-color: {palette.accent_ink};
}}

QPlainTextEdit {{
    background: {palette.surface_raised};
    border: 1px solid {palette.line_soft};
    border-radius: {RADIUS}px;
    color: {palette.ink};
}}

#resultCard, #settingsBlock, #card {{
    background: {palette.surface_raised};
    border: 1px solid {palette.line_soft};
    border-radius: {RADIUS}px;
}}
#resultCard:hover {{
    border: 1px solid {palette.accent};
}}
#resultCard[selected="true"] {{
    border: 2px solid {palette.accent};
    background: {palette.accent_soft};
}}

QTableWidget {{
    background: {palette.surface_raised};
    border: 1px solid {palette.line_soft};
    border-radius: {RADIUS}px;
    gridline-color: {palette.line_soft};
}}
QTableWidget::item {{
    padding: {sp(4)} {sp(6)};
}}
QTableWidget::item:hover {{
    background: {palette.line_soft};
}}
QTableWidget::item:selected {{
    background: {palette.accent_soft};
    color: {palette.accent_ink};
}}
QHeaderView::section {{
    background: {palette.surface};
    color: {palette.ink_faint};
    padding: {sp(6)};
    border: none;
    border-bottom: 1px solid {palette.line_soft};
    font-weight: 600;
    font-size: {px(Type.CAPTION)};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {palette.line};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {palette.ink_faint};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""


GLOBAL_STYLESHEET = build_stylesheet(LIGHT)
