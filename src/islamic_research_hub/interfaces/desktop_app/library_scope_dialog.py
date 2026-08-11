"""Multi-library search scope picker.

Search's own library filter used to be a single QComboBox - pick one
library, or "All libraries". Maktaba Jibreel's own search dialog offers
a real checklist letting a user search several specific libraries at
once (e.g. every "(PDF Archive)" variant, or every Urdu library, without
also pulling in Maktaba Shamela) - this is the same idea, applied to
this app's own library list.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.interfaces.desktop_app.i18n import Translator


class LibraryScopeDialog(QDialog):
    """Pick zero, one, or several libraries to restrict a search to.

    `selected_libraries()` returns `None` for "no restriction" - both
    "every box checked" and "no box checked" collapse to this same
    meaning, since restricting a search to zero libraries isn't a real
    scope a user would intend to end up in.
    """

    def __init__(
        self,
        libraries_with_counts: tuple[tuple[str, int], ...],
        currently_selected: tuple[str, ...] | None,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        tr = translator.tr
        self.setWindowTitle(tr("search-scope-dialog-title"))
        self.resize(380, 420)

        layout = QVBoxLayout(self)
        hint = QLabel(tr("search-scope-dialog-hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        button_row = QHBoxLayout()
        select_all_button = QPushButton(tr("search-scope-select-all"))
        select_all_button.clicked.connect(lambda: self._set_all_checked(True))
        button_row.addWidget(select_all_button)
        clear_all_button = QPushButton(tr("search-scope-clear-all"))
        clear_all_button.clicked.connect(lambda: self._set_all_checked(False))
        button_row.addWidget(clear_all_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        selected_set = set(currently_selected) if currently_selected else None
        self._checkboxes: list[QCheckBox] = []
        for name, count in libraries_with_counts:
            checkbox = QCheckBox(f"{name}  ({count})")
            checkbox.setChecked(selected_set is None or name in selected_set)
            content_layout.addWidget(checkbox)
            self._checkboxes.append(checkbox)
        content_layout.addStretch(1)
        scroll_area.setWidget(content)
        layout.addWidget(scroll_area, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all_checked(self, checked: bool) -> None:
        for checkbox in self._checkboxes:
            checkbox.setChecked(checked)

    def selected_libraries(self) -> tuple[str, ...] | None:
        """Return the checked library names, or `None` for "no restriction"
        (every box checked, or none - both mean the same thing here)."""
        checked_names = tuple(
            checkbox.text().rsplit("  (", 1)[0]
            for checkbox in self._checkboxes
            if checkbox.isChecked()
        )
        if not checked_names or len(checked_names) == len(self._checkboxes):
            return None
        return checked_names
