"""Tests for the desktop app's splitter-resize animation helper.

Drives the animation deterministically via `setCurrentTime()` (scrubbing
to an exact point in the animation's timeline) rather than waiting on a
real timer/event loop - reliable in a headless/offscreen test environment
and doesn't depend on real wall-clock timing.
"""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QLabel, QSplitter  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.animations import (  # noqa: E402
    animate_splitter_size,
)


def _make_splitter(qtbot) -> QSplitter:
    splitter = QSplitter()
    for _ in range(3):
        splitter.addWidget(QLabel())
    qtbot.addWidget(splitter)
    splitter.resize(900, 400)
    splitter.setSizes([300, 300, 300])
    return splitter


def test_animation_ends_at_the_requested_size(qtbot) -> None:
    """Scrubbed to the end, the target segment reaches exactly the requested size."""
    splitter = _make_splitter(qtbot)

    animation = animate_splitter_size(splitter, index=2, end=0, duration_ms=200)
    animation.setCurrentTime(200)

    assert splitter.sizes()[2] == 0


def test_animation_preserves_total_width(qtbot) -> None:
    """Shrinking one segment grows another by the same amount - total width is stable."""
    splitter = _make_splitter(qtbot)
    total_before = sum(splitter.sizes())

    animation = animate_splitter_size(splitter, index=2, end=0, duration_ms=200)
    animation.setCurrentTime(200)

    assert sum(splitter.sizes()) == total_before


def test_animation_is_partway_through_at_the_midpoint(qtbot) -> None:
    """At 50% duration, the segment is roughly halfway to its target."""
    splitter = _make_splitter(qtbot)

    animation = animate_splitter_size(splitter, index=2, end=0, duration_ms=200)
    animation.setCurrentTime(100)

    assert 0 < splitter.sizes()[2] < 300


def test_animation_can_expand_a_segment_too(qtbot) -> None:
    """The same helper works for growing a segment, not just shrinking it."""
    splitter = _make_splitter(qtbot)
    splitter.setSizes([300, 300, 0])

    animation = animate_splitter_size(splitter, index=2, end=280, duration_ms=200)
    animation.setCurrentTime(200)

    assert splitter.sizes()[2] == 280
