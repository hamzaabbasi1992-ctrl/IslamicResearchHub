"""Tests for PanelToggle - real QSplitter behavior, no screen classes."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QSplitter, QWidget  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.panel_toggle import PanelToggle  # noqa: E402


def _splitter(qtbot) -> QSplitter:
    splitter = QSplitter(Qt.Orientation.Horizontal)
    a, b, c = QWidget(), QWidget(), QWidget()
    a.setMinimumWidth(180)
    b.setMinimumWidth(0)
    c.setMinimumWidth(220)
    splitter.addWidget(a)
    splitter.addWidget(b)
    splitter.addWidget(c)
    qtbot.addWidget(splitter)
    splitter.resize(1000, 600)
    splitter.setSizes([230, 640, 220])
    return splitter


def test_maximize_shrinks_siblings_to_their_own_minimums(qtbot) -> None:
    splitter = _splitter(qtbot)
    toggle = PanelToggle(splitter, index=2, expanded_width=220)

    toggle.set_maximized(True)

    assert splitter.sizes()[0] == 180  # sibling's real minimumWidth
    assert splitter.sizes()[2] > 220
    assert toggle.is_maximized is True


def test_restore_returns_to_the_exact_pre_maximize_sizes(qtbot) -> None:
    splitter = _splitter(qtbot)
    initial = splitter.sizes()
    toggle = PanelToggle(splitter, index=2, expanded_width=220)

    toggle.set_maximized(True)
    toggle.set_maximized(False)

    assert splitter.sizes() == initial
    assert toggle.is_maximized is False


def test_toggle_maximized_flips_state(qtbot) -> None:
    splitter = _splitter(qtbot)
    toggle = PanelToggle(splitter, index=2, expanded_width=220)

    toggle.toggle_maximized()
    assert toggle.is_maximized is True

    toggle.toggle_maximized()
    assert toggle.is_maximized is False


def test_setting_the_same_state_twice_is_a_no_op(qtbot) -> None:
    """Calling set_maximized(True) twice shouldn't double-save pre-maximize
    sizes (which would otherwise remember the already-maximized sizes)."""
    splitter = _splitter(qtbot)
    initial = splitter.sizes()
    toggle = PanelToggle(splitter, index=2, expanded_width=220)

    toggle.set_maximized(True)
    toggle.set_maximized(True)  # no-op, already maximized
    toggle.set_maximized(False)

    assert splitter.sizes() == initial
