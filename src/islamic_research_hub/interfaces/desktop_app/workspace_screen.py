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

from islamic_research_hub.interfaces.desktop_app.ai_panel_screen import AiAssistantPanel
from islamic_research_hub.interfaces.desktop_app.animations import animate_splitter_size
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen

_MIN_READER_WIDTH = 320


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
        self._reader_stack = reader_stack
        self._ai_panel = ai_panel
        self._last_reader_width = _MIN_READER_WIDTH
        self._last_ai_panel_width = 280
        self._reader_animation: QVariantAnimation | None = None
        self._ai_panel_animation: QVariantAnimation | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(search_screen)
        self._splitter.addWidget(reader_stack)
        self._splitter.addWidget(ai_panel)
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setCollapsible(0, False)
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
        self._splitter.setSizes([600, max(600, _MIN_READER_WIDTH), self._last_ai_panel_width])
        layout.addWidget(self._splitter)

        ai_panel.collapsed_changed.connect(self._on_ai_panel_collapsed_changed)
        self._apply_ai_panel_collapsed(ai_panel.is_collapsed, animated=False)

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
