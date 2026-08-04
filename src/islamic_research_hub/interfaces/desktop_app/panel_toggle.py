"""Reusable "maximize" controller for one QSplitter segment.

Written once instead of duplicated per screen - the AI panel, the
reader's TOC/Bookmarks panel, and the Search screen's detail panel all
use this for maximize/restore. Collapse is deliberately left to each
screen's own existing, already-working collapse implementation (the AI
panel's `set_collapsed`, ViewerScreen's `_on_contents_toggled`,
SearchScreen's `_on_detail_panel_toggled`) rather than retrofitted onto
this class - those are proven, tested code paths, not worth the
regression risk of replacing for the sake of using one shared class for
both behaviors.
"""

from __future__ import annotations

from PySide6.QtWidgets import QSplitter


class PanelToggle:
    """Maximize/restore one segment of a `QSplitter`.

    An instant snap (not animated) - shrinks every sibling segment to
    its own real `minimumWidth()` and gives this segment the rest,
    remembering the pre-maximize sizes to restore exactly on toggle-back.
    """

    def __init__(self, splitter: QSplitter, index: int, expanded_width: int) -> None:
        self._splitter = splitter
        self._index = index
        self._expanded_width = expanded_width
        self._maximized = False
        self._pre_maximize_sizes: list[int] | None = None

    @property
    def is_maximized(self) -> bool:
        return self._maximized

    def toggle_maximized(self) -> None:
        self.set_maximized(not self._maximized)

    def set_maximized(self, maximized: bool) -> None:
        if maximized == self._maximized:
            return
        self._maximized = maximized
        if maximized:
            self._pre_maximize_sizes = self._splitter.sizes()
            sizes = list(self._pre_maximize_sizes)
            total = sum(sizes)
            sibling_floor_total = 0
            for i in range(self._splitter.count()):
                if i == self._index:
                    continue
                sibling = self._splitter.widget(i)
                # Real Qt behavior confirmed directly (not assumed): a
                # composite widget's effective floor for setSizes() is
                # the LARGER of its explicit minimumWidth() and its real
                # minimumSizeHint().width() (driven by its own internal
                # layout content) - using minimumWidth() alone under-
                # counted this for SearchScreen (explicit 0, but a real
                # ~627px minimumSizeHint from its own 3-pane layout),
                # so "maximize" barely grew the target segment at all.
                floor = max(sibling.minimumWidth(), sibling.minimumSizeHint().width())
                sizes[i] = floor
                sibling_floor_total += floor
            sizes[self._index] = max(total - sibling_floor_total, self._expanded_width)
            self._splitter.setSizes(sizes)
        elif self._pre_maximize_sizes is not None:
            self._splitter.setSizes(self._pre_maximize_sizes)
            self._pre_maximize_sizes = None
