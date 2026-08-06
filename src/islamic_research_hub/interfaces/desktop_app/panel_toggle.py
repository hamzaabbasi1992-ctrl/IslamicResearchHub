"""Reusable "maximize" controller for one QSplitter segment.

Written once instead of duplicated per screen - the AI panel and the
Search screen's detail panel both use this for maximize/restore.
ViewerScreen's reader/TOC split deliberately does NOT use this class:
maximizing a segment hides every real sibling (see `set_maximized()`
below), which is fine for a secondary panel (AI chat, book detail) but
was a real, reported bug when applied to the reader's own TOC - it
drove the actual page text to a real 0px width ("I have to minimize TOC
to see my reading text"). Collapse (as opposed to maximize) is
deliberately left to each screen's own existing, already-working
collapse implementation (the AI panel's `set_collapsed`, ViewerScreen's
`_on_contents_toggled`, SearchScreen's `_on_detail_panel_toggled`)
rather than retrofitted onto this class - those are proven, tested code
paths, not worth the regression risk of replacing for the sake of using
one shared class for both behaviors.
"""

from __future__ import annotations

from PySide6.QtWidgets import QSplitter


class PanelToggle:
    """Maximize/restore one segment of a `QSplitter`.

    An instant snap (not animated) - fully hides every sibling segment
    (not just shrinks them to their own minimum) and gives this segment
    the whole splitter, remembering the pre-maximize sizes to restore
    exactly on toggle-back.

    Real bug found and fixed here: shrinking siblings to their own
    `minimumSizeHint()` (the original approach) often freed little or no
    real space - confirmed directly against the real app at its default
    1180px window width, `SearchScreen`'s own internal 3-pane layout
    alone has a real ~650px `minimumSizeHint`, which combined with the
    reader's 320px minimum already consumed nearly the whole window,
    leaving the AI panel's maximize button doing visibly nothing. Siblings
    are now genuinely hidden instead: `minimumWidth`/`maximumWidth` are
    both temporarily pinned to 0 (confirmed directly this is what it
    takes to get a real 0px collapse from `QSplitter.setSizes()`,
    regardless of a widget's own `minimumSizeHint`) and restored exactly
    on toggle-back.
    """

    def __init__(self, splitter: QSplitter, index: int, expanded_width: int) -> None:
        self._splitter = splitter
        self._index = index
        self._expanded_width = expanded_width
        self._maximized = False
        self._pre_maximize_sizes: list[int] | None = None
        self._pre_maximize_widths: dict[int, tuple[int, int]] = {}

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
            for i in range(self._splitter.count()):
                if i == self._index:
                    continue
                sibling = self._splitter.widget(i)
                self._pre_maximize_widths[i] = (sibling.minimumWidth(), sibling.maximumWidth())
                sibling.setMinimumWidth(0)
                sibling.setMaximumWidth(0)
            self._splitter.setSizes(
                [
                    sum(self._pre_maximize_sizes) if i == self._index else 0
                    for i in range(self._splitter.count())
                ]
            )
        else:
            for i, (min_width, max_width) in self._pre_maximize_widths.items():
                sibling = self._splitter.widget(i)
                sibling.setMinimumWidth(min_width)
                sibling.setMaximumWidth(max_width)
            self._pre_maximize_widths = {}
            if self._pre_maximize_sizes is not None:
                self._splitter.setSizes(self._pre_maximize_sizes)
                self._pre_maximize_sizes = None
