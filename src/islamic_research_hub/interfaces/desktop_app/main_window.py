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

from islamic_research_hub.interfaces.desktop_app.import_screen import ImportScreen
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen
from islamic_research_hub.interfaces.desktop_app.viewer_screen import ViewerScreen

RAIL_WIDTH = 130
_RAIL_TITLES = ("Search", "Viewer", "Import", "Settings")
_PLACEHOLDER_MESSAGES = {
    "Settings": "Settings are coming in a future update.",
}


class MainWindow(QMainWindow):
    """Top-level window for the Islamic Research Hub desktop app."""

    def __init__(self, database_path: Path, maknoon_pdf_folder: Path) -> None:
        super().__init__()
        self.setWindowTitle("Islamic Research Hub")
        self.resize(1180, 760)

        self._stack = QStackedWidget()
        if database_path.is_file():
            search_screen = SearchScreen(database_path, maknoon_pdf_folder)
            viewer_screen = ViewerScreen(database_path)
            search_screen.open_in_viewer_requested.connect(
                lambda book_id, page_number: self._open_in_viewer(
                    viewer_screen, book_id, page_number
                )
            )
            self._stack.addWidget(search_screen)
            self._stack.addWidget(viewer_screen)
            self._stack.addWidget(ImportScreen(database_path))
        else:
            missing_database_message = (
                f"Expected data\\books.db next to the app, at:\n{database_path}\n\n"
                "Copy or link your master database there and restart."
            )
            self._stack.addWidget(_placeholder_screen("Database not found", missing_database_message))
            self._stack.addWidget(_placeholder_screen("Viewer", missing_database_message))
            self._stack.addWidget(_placeholder_screen("Import", missing_database_message))
        for title in _RAIL_TITLES[3:]:
            self._stack.addWidget(_placeholder_screen(title, _PLACEHOLDER_MESSAGES[title]))

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
        for index, title in enumerate(_RAIL_TITLES):
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

    def _open_in_viewer(self, viewer_screen: ViewerScreen, book_id: int, page_number: int) -> None:
        """Load the requested book/page into the Viewer and switch to it."""
        if viewer_screen.load_book(book_id):
            viewer_screen.jump_to_page_number(page_number)
            self._show_screen(1)


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
