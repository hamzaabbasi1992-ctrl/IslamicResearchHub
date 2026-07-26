"""Nav-rail icons, rendered from the same SVG paths as the design preview.

Each icon is rasterized twice (muted "off" color, accent "on" color) via
`QSvgRenderer`, so a checkable `QPushButton` shows the accent version
automatically when checked - `QIcon` natively supports a separate pixmap
per `QIcon.State`, no manual state-tracking needed.
"""

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from islamic_research_hub.interfaces.desktop_app.theme import ACCENT, INK_SOFT

_RENDER_SIZE = QSize(40, 40)

_SVG_PATHS: dict[str, str] = {
    "search": '<circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.2" y2="16.2"/>',
    "viewer": (
        '<path d="M3 5c3-1.5 6-1.5 9 0v14c-3-1.5-6-1.5-9 0z"/>'
        '<path d="M21 5c-3-1.5-6-1.5-9 0v14c3-1.5 6-1.5 9 0z"/>'
    ),
    "import": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M8 4v5"/>',
    "logs": (
        '<rect x="4" y="3" width="16" height="18" rx="2"/>'
        '<line x1="8" y1="8" x2="16" y2="8"/>'
        '<line x1="8" y1="12" x2="16" y2="12"/>'
        '<line x1="8" y1="16" x2="12" y2="16"/>'
    ),
    "settings": (
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0'
        "-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 0 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0"
        "-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2"
        " 2 0 0 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l."
        "06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 0 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7"
        " 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0"
        ' 1.55 1H21a2 2 0 0 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1z"/>'
    ),
}


def rail_icon(name: str) -> QIcon:
    """Return the checkable-state icon (muted normally, accent when checked) for a rail entry."""
    icon = QIcon()
    icon.addPixmap(_render(name, INK_SOFT), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_render(name, ACCENT), QIcon.Mode.Normal, QIcon.State.On)
    return icon


def _render(name: str, color: str) -> QPixmap:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{_SVG_PATHS[name]}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(_RENDER_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap
