"""Nav-rail and inline-button icons, rendered from shared SVG paths.

Nav-rail icons are rasterized twice (muted "off" color, accent "on" color)
via `QSvgRenderer`, so a checkable `QPushButton` shows the accent version
automatically when checked - `QIcon` natively supports a separate pixmap
per `QIcon.State`, no manual state-tracking needed. `button_icon()` renders
a single-color icon for ordinary (non-checkable) buttons - Prev/Next,
bookmark, and the various "open PDF"/"read in app" actions - at a smaller
size appropriate for sitting next to a button's own label text.
"""

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from islamic_research_hub.interfaces.desktop_app.theme import ACCENT, INK_SOFT

_RENDER_SIZE = QSize(40, 40)
_BUTTON_RENDER_SIZE = QSize(18, 18)

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
    "prev": '<polyline points="15 5 8 12 15 19"/>',
    "next": '<polyline points="9 5 16 12 9 19"/>',
    "bookmark": '<path d="M6 3.5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1V21l-6-4-6 4z"/>',
    "open-pdf": (
        '<path d="M6 3h9l4 4v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/>'
        '<path d="M15 3v4h4"/>'
        '<path d="M10.3 14.7 15 10"/>'
        '<path d="M11 10h4v4"/>'
    ),
    "home": (
        '<path d="M4 12 12 4.5 20 12"/>'
        '<path d="M6 10.5V19a1 1 0 0 0 1 1h3.5v-5.5h3V20H17a1 1 0 0 0 1-1v-8.5"/>'
    ),
    "duplicates": '<rect x="3" y="3" width="12" height="12" rx="2"/><rect x="9" y="9" width="12" height="12" rx="2"/>',
    "ai-assistant": '<path d="M12 3.5 13.8 9 19.5 10.8 13.8 12.6 12 18.1 10.2 12.6 4.5 10.8 10.2 9z"/>',
    "sun": (
        '<circle cx="12" cy="12" r="4"/>'
        '<line x1="12" y1="2" x2="12" y2="5"/>'
        '<line x1="12" y1="19" x2="12" y2="22"/>'
        '<line x1="2" y1="12" x2="5" y2="12"/>'
        '<line x1="19" y1="12" x2="22" y2="12"/>'
        '<line x1="4.9" y1="4.9" x2="7" y2="7"/>'
        '<line x1="17" y1="17" x2="19.1" y2="19.1"/>'
        '<line x1="4.9" y1="19.1" x2="7" y2="17"/>'
        '<line x1="17" y1="7" x2="19.1" y2="4.9"/>'
    ),
    "moon": '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z"/>',
    "filter": '<line x1="4" y1="6" x2="20" y2="6"/><line x1="7" y1="12" x2="17" y2="12"/><line x1="10.5" y1="18" x2="13.5" y2="18"/>',
    "star": '<path d="M12 4 14.5 9.5 20.5 10.3 16 14.3 17.2 20.2 12 17.1 6.8 20.2 8 14.3 3.5 10.3 9.5 9.5z"/>',
    "star-filled": (
        '<path d="M12 4 14.5 9.5 20.5 10.3 16 14.3 17.2 20.2 12 17.1 6.8 20.2 8 14.3 3.5 10.3 9.5 9.5z" '
        'fill="{color}"/>'
    ),
    "clock": '<circle cx="12" cy="12" r="8.5"/><polyline points="12 7.5 12 12 15.5 14"/>',
    "x": '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
    "taxonomy": (
        '<circle cx="12" cy="4.5" r="2"/><circle cx="5" cy="19.5" r="2"/><circle cx="19" cy="19.5" r="2"/>'
        '<path d="M12 6.5v4a2 2 0 0 1-2 2H7a2 2 0 0 0-2 2v3"/>'
        '<path d="M12 10.5a2 2 0 0 0 2 2h3a2 2 0 0 1 2 2v3"/>'
    ),
}


def rail_icon(name: str) -> QIcon:
    """Return the checkable-state icon (muted normally, accent when checked) for a rail entry."""
    icon = QIcon()
    icon.addPixmap(_render(name, INK_SOFT, _RENDER_SIZE), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_render(name, ACCENT, _RENDER_SIZE), QIcon.Mode.Normal, QIcon.State.On)
    return icon


def button_icon(name: str, color: str = INK_SOFT) -> QIcon:
    """Return a single-color icon sized for an ordinary (non-checkable) button's label."""
    icon = QIcon()
    icon.addPixmap(_render(name, color, _BUTTON_RENDER_SIZE))
    return icon


def button_icon_size() -> QSize:
    """Return the size `button_icon()` renders at, for `QPushButton.setIconSize()`."""
    return QSize(_BUTTON_RENDER_SIZE)


def _render(name: str, color: str, size: QSize) -> QPixmap:
    # `.format(color=...)` is a no-op for the (majority) of path strings that
    # don't reference `{color}` - it only matters for icons like "star-filled"
    # that need a solid fill matching the icon's own color instead of "none".
    path_svg = _SVG_PATHS[name].format(color=color)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f"{path_svg}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap
