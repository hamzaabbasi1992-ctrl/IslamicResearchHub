"""Shared button for a real, dynamic-length list row (a book title, author
name, or library name, each with a real, unbounded-length count of
characters - some real library/author names measured over 400px wide on
their own). Without this, a single unusually long real name forces its
whole containing pane - and from there the whole window - wider than the
screen, since Qt never lets a window shrink below its layout's true
minimum size. Found and fixed after a real repro: `library_combo` and the
`libraryChip`/`authorRow` button lists in `search_screen.py` were together
responsible for a measured ~2056px window minimum width on a real
production database.
"""

from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget


def list_row_button(text: str, *, object_name: str, parent: QWidget | None = None) -> QPushButton:
    """A `QPushButton` whose full, real text is always shown and tooltip-
    accessible, but whose natural width is never allowed to dictate its
    container's minimum size."""
    button = QPushButton(text, parent)
    button.setObjectName(object_name)
    button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    button.setToolTip(text)
    return button
