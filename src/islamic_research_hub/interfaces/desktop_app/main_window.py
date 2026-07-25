"""Main window: a navigation rail plus a stacked set of screens."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen

RAIL_WIDTH = 130
_SCREENS: tuple[tuple[str, str], ...] = (
    ("Search", ""),
    ("Viewer", "The book viewer is coming in a future update."),
    ("Import", "The import manager is coming in a future update."),
    ("Settings", "Settings are coming in a future update."),
)


class MainWindow(QMainWindow):
    """Top-level window for the Islamic Research Hub desktop app."""

    def __init__(self, database_path: Path, maknoon_pdf_folder: Path) -> None:
        super().__init__()
        self.setWindowTitle("Islamic Research Hub")
        self.resize(1180, 760)

        self._stack = QStackedWidget()
        if database_path.is_file():
            self._stack.addWidget(SearchScreen(database_path, maknoon_pdf_folder))
        else:
            self._stack.addWidget(
                _placeholder_screen(
                    "Database not found",
                    f"Expected data\\books.db next to the app, at:\n{database_path}\n\n"
                    "Copy or link your master database there and restart.",
                )
            )
        for title, message in _SCREENS[1:]:
            self._stack.addWidget(_placeholder_screen(title, message))

        rail = self._build_rail()

        central = QWidget()
        central_layout = QHBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(rail)
        central_layout.addWidget(self._stack, stretch=1)
        self.setCentralWidget(central)

    def _build_rail(self) -> QWidget:
        rail = QWidget()
        rail.setFixedWidth(RAIL_WIDTH)
        rail.setStyleSheet("background: #f7f3e9; border-right: 1px solid #d9cfb8;")
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(8, 14, 8, 14)
        rail_layout.setSpacing(4)

        self._rail_buttons: list[QPushButton] = []
        for index, (title, _message) in enumerate(_SCREENS):
            button = QPushButton(title)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.clicked.connect(lambda _checked, i=index: self._show_screen(i))
            rail_layout.addWidget(button)
            self._rail_buttons.append(button)
        rail_layout.addStretch(1)
        return rail

    def _show_screen(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for button_index, button in enumerate(self._rail_buttons):
            button.setChecked(button_index == index)


def _placeholder_screen(title: str, message: str) -> QWidget:
    """Build a simple, honest 'not built yet' screen for a future tab."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.addStretch(1)

    heading = QLabel(title)
    heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
    heading.setStyleSheet("font-size: 20px; font-weight: 600; color: #241f17;")
    layout.addWidget(heading)

    body = QLabel(message)
    body.setAlignment(Qt.AlignmentFlag.AlignCenter)
    body.setWordWrap(True)
    body.setStyleSheet("color: #7a7264;")
    layout.addWidget(body)

    layout.addStretch(1)
    return widget
