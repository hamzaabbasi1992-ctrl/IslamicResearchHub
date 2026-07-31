"""Small animation helpers for panel collapse/expand transitions.

Deliberately minimal: Qt stylesheets don't support CSS-style `transition:`,
so small controls (buttons, chips) keep the instant QSS `:hover` swap
already used throughout `theme.py` - real `QPropertyAnimation`/
`QVariantAnimation` is reserved for the few places it reads as genuine
polish rather than decoration, per the approved UI redesign plan: panel
collapse/expand transitions.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QVariantAnimation
from PySide6.QtWidgets import QSplitter

DEFAULT_DURATION_MS = 180


def animate_splitter_size(
    splitter: QSplitter, index: int, end: int, duration_ms: int = DEFAULT_DURATION_MS
) -> QVariantAnimation:
    """Animate one segment of `splitter` to a new width.

    The size difference is taken from (or given to) whichever other
    segment is currently widest, so the splitter's total width stays
    constant instead of the whole layout jumping. Returns the
    already-started animation - the caller must keep a reference until it
    finishes (e.g. `self._animation = animate_splitter_size(...)`), or Qt
    garbage-collects it mid-animation and the resize never completes.
    """
    start = splitter.sizes()[index]
    animation = QVariantAnimation()
    animation.setDuration(duration_ms)
    animation.setStartValue(start)
    animation.setEndValue(end)
    animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _apply(value: int) -> None:
        sizes = splitter.sizes()
        delta = value - sizes[index]
        sizes[index] = value
        other_indices = [i for i in range(len(sizes)) if i != index]
        widest = max(other_indices, key=lambda i: sizes[i])
        sizes[widest] -= delta
        splitter.setSizes(sizes)

    animation.valueChanged.connect(_apply)
    animation.start(QVariantAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation
