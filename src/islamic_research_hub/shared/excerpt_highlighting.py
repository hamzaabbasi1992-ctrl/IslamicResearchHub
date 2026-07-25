"""Convert `snippet()`'s `**term**` markers into safe, highlighted HTML.

Framework-free (stdlib `html.escape` only) so both the web app (which
marks the result trusted for Jinja) and the desktop app (which feeds it
straight to a Qt rich-text label) can use the exact same output. The
highlight color is an inline style, not just a bare `<mark>` tag - Qt's
rich-text engine (unlike a browser) has no default styling for `<mark>`,
so without it the highlighting would be semantically present but
invisible in the desktop app.
"""

import html
import re

_BOLD_MARKER = re.compile(r"\*\*(.+?)\*\*")
_MARK_OPEN = '<mark style="background-color: #ffe58a; padding: 0 2px;">'


def highlight_excerpt_html(excerpt: str) -> str:
    """Escape `excerpt` and wrap `**term**` spans in a styled `<mark>` tag."""
    parts: list[str] = []
    last_end = 0
    for match in _BOLD_MARKER.finditer(excerpt):
        parts.append(html.escape(excerpt[last_end : match.start()]))
        parts.append(_MARK_OPEN + html.escape(match.group(1)) + "</mark>")
        last_end = match.end()
    parts.append(html.escape(excerpt[last_end:]))
    return "".join(parts)
