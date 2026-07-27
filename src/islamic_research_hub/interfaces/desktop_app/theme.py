"""Shared visual theme, matching the Phase 4 design preview's color palette.

Centralizes the colors/fonts every screen was previously hardcoding its own
(slightly inconsistent) copies of, and provides the one global Qt stylesheet
applied once at the `QApplication` level in `__main__.py`. Screens still set
`objectName`s for the few widgets that need a specific look (cards, the nav
rail, primary buttons) - the actual colors live only here.
"""

BG = "#ede6d6"
SURFACE = "#f7f3e9"
SURFACE_RAISED = "#ffffff"
INK = "#241f17"
INK_SOFT = "#5b5346"
INK_FAINT = "#948c78"
ACCENT = "#1f5c50"
ACCENT_SOFT = "#dce8e2"
ACCENT_INK = "#0f342d"
LINE = "#d9cfb8"
LINE_SOFT = "#e6dfcc"
RADIUS = 8

RTL_FONT_FAMILY = (
    "'Noto Nastaliq Urdu', 'Jameel Noori Nastaliq', Tahoma, 'Segoe UI', sans-serif"
)

MUTED_LABEL_STYLE = f"color: {INK_FAINT};"
"""Shared style for small secondary/meta text (status lines, captions, hints)."""

RTL_TEXT_STYLE = f"font-family: {RTL_FONT_FAMILY};"
"""Shared style for labels displaying Arabic/Urdu book content or titles."""

GLOBAL_STYLESHEET = f"""
QMainWindow {{
    background: {BG};
}}

QWidget {{
    color: {INK};
    font-family: "Segoe UI", "Segoe UI Variable", sans-serif;
    font-size: 13px;
}}

QLabel, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

#headerBar {{
    background: {SURFACE};
    border-bottom: 1px solid {LINE};
}}
#headerBar QLabel {{
    color: {INK_SOFT};
}}
#langPill {{
    background: transparent;
    border: none;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
    color: {INK_SOFT};
}}
#langPill:hover {{
    background: {LINE_SOFT};
    color: {INK};
}}
#langPill:checked {{
    background: {ACCENT};
    color: {SURFACE_RAISED};
}}

#navRail {{
    background: {SURFACE};
    border-right: 1px solid {LINE};
}}
#navRail QToolButton {{
    background: transparent;
    border: none;
    border-radius: {RADIUS}px;
    color: {INK_SOFT};
    padding: 10px 6px;
    font-size: 12px;
    font-weight: 600;
}}
#navRail QToolButton:hover {{
    background: {LINE_SOFT};
    color: {INK};
}}
#navRail QToolButton:checked {{
    background: {ACCENT_SOFT};
    color: {ACCENT_INK};
}}

QPushButton {{
    background: {SURFACE_RAISED};
    border: 1px solid {LINE};
    border-radius: 6px;
    padding: 6px 14px;
    color: {INK_SOFT};
}}
QPushButton:hover {{
    border-color: {ACCENT};
    color: {INK};
}}
QPushButton:disabled {{
    color: {INK_FAINT};
    border-color: {LINE_SOFT};
}}
QPushButton:default, QPushButton#primaryButton {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: {SURFACE_RAISED};
    font-weight: 600;
}}
QPushButton:default:hover, QPushButton#primaryButton:hover {{
    background: {ACCENT_INK};
    border-color: {ACCENT_INK};
    color: {SURFACE_RAISED};
}}

#searchLeftPane {{
    background: {SURFACE};
    border: none;
    border-right: 1px solid {LINE};
}}
#navTab {{
    background: {BG};
    border: none;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 11px;
    font-weight: 600;
    color: {INK_SOFT};
}}
#navTab:checked {{
    background: {SURFACE_RAISED};
    color: {ACCENT_INK};
}}
#authorRow, #libraryChip {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 6px;
    text-align: left;
    font-size: 11px;
    color: {INK_SOFT};
}}
#authorRow:hover, #libraryChip:hover {{
    background: {LINE_SOFT};
    color: {INK};
}}

QTreeWidget {{
    background: transparent;
    border: none;
    font-size: 12px;
}}
QTreeWidget::item {{
    padding: 3px 2px;
    border-radius: 4px;
}}
QTreeWidget::item:hover {{
    background: {LINE_SOFT};
}}
QTreeWidget::item:selected {{
    background: {ACCENT_SOFT};
    color: {ACCENT_INK};
}}

QLineEdit, QComboBox {{
    background: {SURFACE_RAISED};
    border: 1px solid {LINE};
    border-radius: 6px;
    padding: 6px 8px;
    color: {INK};
    selection-background-color: {ACCENT_SOFT};
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {ACCENT};
}}
#mainSearchBox {{
    font-size: 16px;
    padding: 8px 12px;
    border-radius: 8px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {SURFACE_RAISED};
    border: 1px solid {LINE};
    selection-background-color: {ACCENT_SOFT};
    selection-color: {ACCENT_INK};
}}

QPlainTextEdit {{
    background: {SURFACE_RAISED};
    border: 1px solid {LINE_SOFT};
    border-radius: {RADIUS}px;
    color: {INK};
}}

#resultCard, #settingsBlock {{
    background: {SURFACE_RAISED};
    border: 1px solid {LINE_SOFT};
    border-radius: {RADIUS}px;
}}

QTableWidget {{
    background: {SURFACE_RAISED};
    border: 1px solid {LINE_SOFT};
    border-radius: {RADIUS}px;
    gridline-color: {LINE_SOFT};
}}
QHeaderView::section {{
    background: {SURFACE};
    color: {INK_FAINT};
    padding: 6px;
    border: none;
    border-bottom: 1px solid {LINE_SOFT};
    font-weight: 600;
    font-size: 11px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {LINE};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {INK_FAINT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
"""
