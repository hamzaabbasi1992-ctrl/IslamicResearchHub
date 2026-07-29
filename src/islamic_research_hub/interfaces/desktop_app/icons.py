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
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><line x1="20.5" y1="20.5" x2="15.3" y2="15.3"/>',
    "viewer": (
        '<path d="M12 6.2c-2.4-1.6-5.6-2.1-9.2-1V19c3.6-1.1 6.8-.6 9.2 1 2.4-1.6 5.6-2.1 9.2-1V5.2'
        'c-3.6-1.1-6.8-.6-9.2 1z"/>'
        '<line x1="12" y1="6.2" x2="12" y2="20"/>'
    ),
    "import": (
        '<path d="M3 7.2a1 1 0 0 1 1-1h4.4l1.8 1.8H20a1 1 0 0 1 1 1V19a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z"/>'
        '<line x1="12" y1="11.7" x2="12" y2="16.7"/>'
        '<line x1="9.5" y1="14.2" x2="14.5" y2="14.2"/>'
    ),
    "logs": (
        '<path d="M6 3h9l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/>'
        '<path d="M15 3v4h4"/>'
        '<line x1="8" y1="11.5" x2="16" y2="11.5"/>'
        '<line x1="8" y1="15" x2="16" y2="15"/>'
        '<line x1="8" y1="18.5" x2="12.5" y2="18.5"/>'
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
