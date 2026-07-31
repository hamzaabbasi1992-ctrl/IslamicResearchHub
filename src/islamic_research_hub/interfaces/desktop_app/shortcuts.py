"""Global keyboard shortcuts for the desktop app's main window.

No keyboard shortcuts existed anywhere in this codebase before this
milestone (confirmed by grep before starting - not even Ctrl+F). Each one
here triggers exactly the same code path as its existing button/control -
no new business logic, just a new input trigger for existing behavior.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtGui import QKeySequence, QShortcut

if TYPE_CHECKING:
    from islamic_research_hub.interfaces.desktop_app.main_window import MainWindow

# Mirrors `_RAIL_KEYS`' order in `main_window.py` - keep in sync if the
# rail is ever reordered/grown again. Real bug found and fixed (Navigation
# milestone): these had gone stale when the Taxonomy rail entry was added
# earlier - `_RAIL_SETTINGS` still pointed at index 5 (now Logs), and no
# shortcut existed for Taxonomy at all.
_RAIL_SEARCH = 1
_RAIL_SETTINGS = 6

SHORTCUTS: tuple[tuple[str, str], ...] = (
    ("Ctrl+F", "Focus the search box"),
    ("Ctrl+K", "Focus the search box"),
    ("Ctrl+P", "Quick Open - jump to a screen or a recent book"),
    ("Ctrl+B", "Toggle bookmark on the current reader page"),
    ("Ctrl+D", "Toggle dark mode"),
    ("Ctrl+,", "Open Settings"),
    ("Alt+1", "Go to Home"),
    ("Alt+2", "Go to Search"),
    ("Alt+3", "Go to Libraries"),
    ("Alt+4", "Go to Duplicates"),
    ("Alt+5", "Go to Taxonomy"),
    ("Alt+6", "Go to Logs"),
    ("Alt+7", "Go to Settings"),
)
"""Every installed shortcut's key sequence and a short description - shown
as a reference list in Settings."""


def install_shortcuts(window: MainWindow) -> list[QShortcut]:
    """Wire every shortcut in `SHORTCUTS` onto `window`.

    Returns the created `QShortcut`s - the caller must keep a reference
    (e.g. `self._shortcuts = install_shortcuts(self)`), since a `QShortcut`
    with no live Python reference is garbage-collected and silently stops
    working, even though its C++ Qt object was parented to `window`.
    """
    shortcuts: list[QShortcut] = []

    for key in ("Ctrl+F", "Ctrl+K"):
        shortcut = _bind(window, key, lambda: _focus_search(window))
        shortcuts.append(shortcut)

    shortcuts.append(_bind(window, "Ctrl+P", lambda: window.open_quick_open()))
    shortcuts.append(_bind(window, "Ctrl+B", lambda: _toggle_bookmark(window)))
    shortcuts.append(_bind(window, "Ctrl+D", lambda: _toggle_dark_mode(window)))
    shortcuts.append(_bind(window, "Ctrl+,", lambda: window._show_screen(_RAIL_SETTINGS)))

    for offset, key in enumerate(
        ("Alt+1", "Alt+2", "Alt+3", "Alt+4", "Alt+5", "Alt+6", "Alt+7")
    ):
        shortcuts.append(_bind(window, key, lambda index=offset: window._show_screen(index)))

    return shortcuts


def _bind(window: MainWindow, key: str, slot: Callable[[], None]) -> QShortcut:
    shortcut = QShortcut(QKeySequence(key), window)
    shortcut.activated.connect(slot)
    return shortcut


def _focus_search(window: MainWindow) -> None:
    if window._search_screen is None:
        return
    window._show_screen(_RAIL_SEARCH)
    window._search_screen.focus_search_box()


def _toggle_bookmark(window: MainWindow) -> None:
    if window._viewer_stack is None:
        return
    current = window._viewer_stack.currentWidget()
    if current is not None and hasattr(current, "toggle_bookmark"):
        current.toggle_bookmark()


def _toggle_dark_mode(window: MainWindow) -> None:
    next_theme = "light" if window._theme_controller.theme_name == "dark" else "dark"
    window._theme_controller.set_theme(next_theme)
