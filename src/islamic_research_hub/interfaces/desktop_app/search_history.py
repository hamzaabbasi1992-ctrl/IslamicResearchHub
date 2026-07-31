"""Recent search queries: a small QSettings-backed list, no new DB table.

Same idiom as `settings_screen.py`'s `viewer/font_size`/`viewer/font_family`
scalars, just a list value instead of a scalar. A real `SearchHistory`
table would be the more scalable long-term answer (unlimited history,
cross-device sync) but means touching the persistence layer - out of
scope for a UI-only refactor; this is a reasonable, honest fast start.
"""

from __future__ import annotations

from PySide6.QtCore import QSettings

RECENT_SEARCHES_KEY = "search/recent_queries"
MAX_RECENT_SEARCHES = 20


class RecentSearchStore:
    """Persist and recall the most recent search queries, newest first."""

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def record(self, query: str) -> None:
        """Add a query to the front of the list, de-duplicated, trimmed to the limit."""
        query = query.strip()
        if not query:
            return
        recent = [entry for entry in self.list_recent() if entry != query]
        recent.insert(0, query)
        self._settings.setValue(RECENT_SEARCHES_KEY, recent[:MAX_RECENT_SEARCHES])

    def list_recent(self) -> list[str]:
        """Return the stored queries, newest first."""
        stored = self._settings.value(RECENT_SEARCHES_KEY, [])
        if isinstance(stored, str):
            # QSettings collapses a single-element list to a bare string on
            # some backends (confirmed with the INI format used in tests).
            return [stored] if stored else []
        return list(stored)
