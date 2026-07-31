"""Tests for the shared empty-state label component."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel  # noqa: E402


def test_empty_state_label_wraps_and_shows_its_text(qtbot) -> None:
    """The label shows the given message and always wraps long text."""
    label = EmptyStateLabel("No bookmarks yet.")
    qtbot.addWidget(label)

    assert label.text() == "No bookmarks yet."
    assert label.wordWrap() is True


def test_centered_empty_state_label_is_centered_with_padding(qtbot) -> None:
    """A centered empty state (full-pane message) gets center alignment
    and generous padding, unlike a compact in-list empty row."""
    label = EmptyStateLabel("Open a book from Search to read it here.", centered=True)
    qtbot.addWidget(label)

    assert label.alignment() & Qt.AlignmentFlag.AlignCenter
    assert "padding" in label.styleSheet()


def test_uncentered_empty_state_label_has_no_extra_padding(qtbot) -> None:
    """A compact list-row empty state doesn't get the full-pane padding."""
    label = EmptyStateLabel("No bookmarks yet.")
    qtbot.addWidget(label)

    assert "padding" not in label.styleSheet()
