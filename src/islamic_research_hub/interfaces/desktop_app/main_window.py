"""Main window: a navigation rail plus a stacked set of screens."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.interfaces.desktop_app.i18n import (
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
    Translator,
)
from islamic_research_hub.interfaces.desktop_app.import_screen import ImportScreen
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen
from islamic_research_hub.interfaces.desktop_app.settings_screen import (
    FONT_SIZE_KEY,
    SettingsScreen,
)
from islamic_research_hub.interfaces.desktop_app.viewer_screen import (
    DEFAULT_FONT_PX,
    ViewerScreen,
)

RAIL_WIDTH = 130
_RAIL_KEYS = ("rail-search", "rail-viewer", "rail-import", "rail-settings")
_PLACEHOLDER_TITLES = ("Database not found", "Viewer", "Import", "Settings")


class MainWindow(QMainWindow):
    """Top-level window for the Islamic Research Hub desktop app."""

    def __init__(
        self,
        database_path: Path,
        maknoon_pdf_folder: Path,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Islamic Research Hub")
        self.resize(1180, 760)

        self._settings = settings or QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        self._translator = Translator(self._settings)
        self._translator.language_changed.connect(self._on_language_changed)

        self._stack = QStackedWidget()
        if database_path.is_file():
            search_screen = SearchScreen(database_path, maknoon_pdf_folder)
            initial_font_px = int(self._settings.value(FONT_SIZE_KEY, DEFAULT_FONT_PX))
            viewer_screen = ViewerScreen(database_path, initial_font_px=initial_font_px)
            search_screen.open_in_viewer_requested.connect(
                lambda book_id, page_number: self._open_in_viewer(
                    viewer_screen, book_id, page_number
                )
            )
            self._stack.addWidget(search_screen)
            self._stack.addWidget(viewer_screen)
            self._stack.addWidget(ImportScreen(database_path))
            self._stack.addWidget(
                SettingsScreen(database_path, self._settings, self._translator)
            )
        else:
            missing_database_message = (
                f"Expected data\\books.db next to the app, at:\n{database_path}\n\n"
                "Copy or link your master database there and restart."
            )
            for title in _PLACEHOLDER_TITLES:
                self._stack.addWidget(_placeholder_screen(title, missing_database_message))

        rail = self._build_rail()
        self._apply_layout_direction()

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
        for index, key in enumerate(_RAIL_KEYS):
            button = QPushButton(self._translator.tr(key))
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

    def _on_language_changed(self, _language: str) -> None:
        """Update rail labels and mirror the whole app's layout for the new language."""
        for key, button in zip(_RAIL_KEYS, self._rail_buttons, strict=True):
            button.setText(self._translator.tr(key))
        self._apply_layout_direction()

    def _apply_layout_direction(self) -> None:
        app = QApplication.instance()
        if app is not None:
            app.setLayoutDirection(self._translator.layout_direction)


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
