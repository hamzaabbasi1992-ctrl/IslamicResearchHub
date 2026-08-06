"""Workspace screen: Search results and the book Reader side by side.

Replaces the old model where opening a book fully replaced the Search
screen (a `QStackedWidget` page swap). `SearchScreen` and the Viewer/
PdfViewer stack are unchanged internally - re-hosted here as splitter
segments instead of separate top-level `QStackedWidget` pages, so search
results stay visible while reading. A collapsible AI-assistant panel is
the third segment. Any new panel here must use `QSplitter`/standard Qt
layouts, never absolute positioning, so the app's existing RTL mirroring
(`QApplication.setLayoutDirection`) keeps working for free.
"""

from __future__ import annotations

from PySide6.QtCore import QVariantAnimation, Qt
from PySide6.QtWidgets import QSplitter, QStackedWidget, QVBoxLayout, QWidget

from islamic_research_hub.interfaces.desktop_app.ai_panel_screen import (
    MIN_AI_PANEL_WIDTH,
    AiAssistantPanel,
)
from islamic_research_hub.interfaces.desktop_app.animations import animate_splitter_size
from islamic_research_hub.interfaces.desktop_app.panel_toggle import PanelToggle
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen

_MIN_READER_WIDTH = 320
_MIN_SEARCH_PANEL_WIDTH = 280


class WorkspaceScreen(QWidget):
    """Search + Reader + AI-assistant panel, as one resizable/collapsible workspace."""

    def __init__(
        self,
        search_screen: SearchScreen,
        reader_stack: QStackedWidget,
        ai_panel: AiAssistantPanel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._search_screen = search_screen
        self._reader_stack = reader_stack
        self._ai_panel = ai_panel
        self._last_reader_width = _MIN_READER_WIDTH
        self._last_ai_panel_width = 280
        self._last_search_width = 600
        self._reader_animation: QVariantAnimation | None = None
        self._ai_panel_animation: QVariantAnimation | None = None
        self._search_panel_animation: QVariantAnimation | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(search_screen)
        self._splitter.addWidget(reader_stack)
        self._splitter.addWidget(ai_panel)
        # UI Polish Pass 2: the reader is the primary reading surface, so it
        # gets double the search segment's stretch weight (grows faster as
        # the window widens) on top of a real, larger starting share below -
        # a real external review flagged the reader reading as too narrow
        # relative to search/metadata.
        #
        # Real bug found and fixed: the AI panel's stretch factor was 0,
        # meaning it never grew as the window widened - confirmed directly
        # that on a large/maximized window its share of the total width
        # actually *shrinks* (18.5% at 1180px down to 9.3% at 2560px),
        # reading as "I can't see the AI panel" even though it was
        # technically still visible. A real, smaller-than-reader stretch
        # weight keeps it a secondary panel while still growing with the
        # window instead of staying pinned to a near-fixed width.
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 4)
        self._splitter.setStretchFactor(2, 1)
        # Real bug fixed here: the search segment used to be permanently
        # uncollapsible ("the search panel can't be minimized") - it now
        # collapses the same way the AI panel already does, via
        # `search_screen.collapsed_changed` below.
        self._splitter.setCollapsible(0, True)
        self._splitter.setCollapsible(1, True)
        self._splitter.setCollapsible(2, True)
        # Real fix: the reader used to start collapsed to 0px (a hidden
        # segment, not just an empty one) - directly the cause of "the
        # center panel is frequently empty." A real minimum width is now
        # enforced so it can never get crushed to nothing on resize
        # either. QSplitter does NOT respect stretch factors on its very
        # first layout pass (confirmed directly - stretch factors alone
        # left the reader at 0px even with a minimum width set), so an
        # explicit real starting size is required: the reader is meant to
        # be the central experience, so it starts with a genuine, visible
        # share of the window, showing `ViewerScreen`'s own real empty
        # state ("Open a book to read it here") instead of being invisible.
        reader_stack.setMinimumWidth(_MIN_READER_WIDTH)
        # Reader starts at ~35% more than an even split with Search (810 vs
        # 600), on top of the doubled stretch factor above - both together
        # are what actually give the reader a visibly larger, real share.
        self._splitter.setSizes([600, max(810, _MIN_READER_WIDTH), self._last_ai_panel_width])
        layout.addWidget(self._splitter)
        self._ai_panel_toggle = PanelToggle(self._splitter, index=2, expanded_width=MIN_AI_PANEL_WIDTH)

        ai_panel.collapsed_changed.connect(self._on_ai_panel_collapsed_changed)
        ai_panel.maximize_clicked.connect(self._on_ai_panel_maximize_clicked)
        self._apply_ai_panel_collapsed(ai_panel.is_collapsed, animated=False)

        search_screen.collapsed_changed.connect(self._on_search_panel_collapsed_changed)
        self._apply_search_panel_collapsed(search_screen.is_collapsed, animated=False)

    def show_reader(self, widget: QWidget | None, animated: bool = True) -> None:
        """Switch the reader to `widget` and expand its segment; `None` collapses it.

        The reader stack always contains a real widget (`ViewerScreen` shows
        its own empty state with nothing loaded) - `widget=None` only affects
        this segment's width, not what the stack itself is showing.
        """
        if widget is not None:
            self._reader_stack.setCurrentWidget(widget)
        sizes = self._splitter.sizes()
        if widget is None:
            if sizes[1] > 0:
                self._last_reader_width = sizes[1]
            target = 0
        else:
            target = sizes[1] if sizes[1] > 0 else max(self._last_reader_width, _MIN_READER_WIDTH)
        if animated:
            self._reader_animation = animate_splitter_size(self._splitter, index=1, end=target)
        else:
            sizes[1] = target
            self._splitter.setSizes(sizes)

    def _on_ai_panel_collapsed_changed(self, collapsed: bool) -> None:
        self._apply_ai_panel_collapsed(collapsed)

    def _on_ai_panel_maximize_clicked(self) -> None:
        """Maximize/restore the AI panel - if it's currently collapsed,
        expand it first so maximizing always shows something real rather
        than a maximized-but-invisible panel."""
        if self._ai_panel.is_collapsed:
            self._ai_panel.set_collapsed(False)
        self._ai_panel_toggle.toggle_maximized()
        self._ai_panel.set_maximize_icon(self._ai_panel_toggle.is_maximized)

    def _apply_ai_panel_collapsed(self, collapsed: bool, animated: bool = True) -> None:
        sizes = self._splitter.sizes()
        if collapsed:
            if sizes[2] > 0:
                self._last_ai_panel_width = sizes[2]
            target = 0
        else:
            target = sizes[2] if sizes[2] > 0 else self._last_ai_panel_width
        if animated:
            self._ai_panel_animation = animate_splitter_size(self._splitter, index=2, end=target)
        else:
            sizes[2] = target
            self._splitter.setSizes(sizes)
        # Real fix: unlike the reader segment (protected by a permanent
        # `setMinimumWidth`), the AI panel had none - under real space
        # pressure (a window too narrow for every segment's natural size)
        # Qt's splitter would silently squeeze it toward 0px even while
        # `is_collapsed` still reported False, making it disappear with no
        # visible way to bring it back. A PERMANENT minimum would be the
        # obvious fix, but `QSplitter.setSizes()` cannot shrink a widget
        # below its own `minimumWidth()` even when marked collapsible
        # (confirmed directly), which would break the panel's own,
        # legitimate collapse-to-0 - so the floor is toggled with the
        # collapse state instead: a real, Qt-native minimum (which also
        # correctly grows the whole window's minimum size to guarantee
        # room) whenever expanded, relaxed to 0 only while collapsed.
        self._ai_panel.setMinimumWidth(0 if collapsed else MIN_AI_PANEL_WIDTH)

    def _on_search_panel_collapsed_changed(self, collapsed: bool) -> None:
        self._apply_search_panel_collapsed(collapsed)

    def _apply_search_panel_collapsed(self, collapsed: bool, animated: bool = True) -> None:
        """Collapse/expand the search segment - mirrors
        `_apply_ai_panel_collapsed` exactly, including the same
        toggled-minimum-width recipe (a permanent minimum would block the
        real collapse-to-0; none at all would let the splitter silently
        squeeze it to nothing under real space pressure)."""
        sizes = self._splitter.sizes()
        if collapsed:
            if sizes[0] > 0:
                self._last_search_width = sizes[0]
            target = 0
        else:
            target = sizes[0] if sizes[0] > 0 else self._last_search_width
        if animated:
            self._search_panel_animation = animate_splitter_size(self._splitter, index=0, end=target)
        else:
            sizes[0] = target
            self._splitter.setSizes(sizes)
        self._search_screen.setMinimumWidth(0 if collapsed else _MIN_SEARCH_PANEL_WIDTH)
