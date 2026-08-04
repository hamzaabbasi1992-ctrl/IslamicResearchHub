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


def test_maximize_fully_hides_siblings_not_just_shrinks_them(qtbot) -> None:
    """Real bug found and fixed: shrinking siblings to their own
    minimumWidth (the original approach) often freed little or no real
    space - confirmed directly against the real app, where SearchScreen's
    own internal layout alone has a real ~650px minimumSizeHint. Siblings
    are now genuinely hidden (0px), regardless of their own minimum."""
    splitter = _splitter(qtbot)
    toggle = PanelToggle(splitter, index=2, expanded_width=220)

    toggle.set_maximized(True)

    assert splitter.sizes()[0] == 0
    assert splitter.sizes()[1] == 0
    assert splitter.sizes()[2] == sum(_splitter(qtbot).sizes())  # the whole splitter
    assert toggle.is_maximized is True


def test_maximize_works_even_when_a_sibling_has_a_large_minimum_size_hint(qtbot) -> None:
    """The real-world case this fix targets: a sibling whose own internal
    layout demands a large minimumSizeHint (like SearchScreen's real
    ~650px) must not block maximize from using that space."""
    splitter = QSplitter(Qt.Orientation.Horizontal)
    from PySide6.QtWidgets import QHBoxLayout, QLineEdit

    wide_content = QWidget()
    wide_layout = QHBoxLayout(wide_content)
    for _ in range(20):
        edit = QLineEdit()
        edit.setMinimumWidth(50)
        wide_layout.addWidget(edit)
    b, c = QWidget(), QWidget()
    splitter.addWidget(wide_content)
    splitter.addWidget(b)
    splitter.addWidget(c)
    qtbot.addWidget(splitter)
    splitter.resize(1200, 600)
    splitter.setSizes([700, 300, 200])
    assert wide_content.minimumSizeHint().width() > 700  # confirms the real-world scenario

    toggle = PanelToggle(splitter, index=2, expanded_width=200)
    toggle.set_maximized(True)

    assert splitter.sizes()[2] > 900  # got the real space, not blocked by the sibling's hint


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
