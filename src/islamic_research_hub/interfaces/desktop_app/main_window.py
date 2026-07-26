"""Main window: a navigation rail plus a stacked set of screens."""

from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.interfaces.desktop_app.header_bar import HeaderBar
from islamic_research_hub.interfaces.desktop_app.i18n import (
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
    Translator,
)
from islamic_research_hub.interfaces.desktop_app.icons import rail_icon
from islamic_research_hub.interfaces.desktop_app.import_screen import ImportScreen
from islamic_research_hub.interfaces.desktop_app.logs_screen import LogsScreen
from islamic_research_hub.interfaces.desktop_app.reading_fonts import DEFAULT_FONT_CHOICE
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen
from islamic_research_hub.interfaces.desktop_app.settings_screen import (
    FONT_FAMILY_KEY,
    FONT_SIZE_KEY,
    SettingsScreen,
)
from islamic_research_hub.interfaces.desktop_app.theme import INK, MUTED_LABEL_STYLE
from islamic_research_hub.interfaces.desktop_app.viewer_screen import (
    DEFAULT_FONT_PX,
    ViewerScreen,
)

RAIL_WIDTH = 84
_RAIL_KEYS = ("rail-search", "rail-viewer", "rail-import", "rail-logs", "rail-settings")
_RAIL_ICON_NAMES = ("search", "viewer", "import", "logs", "settings")
_PLACEHOLDER_TITLES = ("Database not found", "Viewer", "Import", "Logs", "Settings")


class MainWindow(QMainWindow):
    """Top-level window for the Islamic Research Hub desktop app."""

    def __init__(
        self,
        database_path: Path,
        maknoon_pdf_folder: Path,
        settings: QSettings | None = None,
        log_directory: Path = Path("logs"),
    ) -> None:
        super().__init__()
        self.setWindowTitle("Islamic Research Hub")
        self.resize(1180, 760)

        self._settings = settings or QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        self._translator = Translator(self._settings)
        self._translator.language_changed.connect(self._on_language_changed)

        self._stack = QStackedWidget()
        self._header_bar: HeaderBar | None = None
        if database_path.is_file():
            self._header_bar = HeaderBar(database_path, self._translator)
            search_screen = SearchScreen(database_path, maknoon_pdf_folder)
            initial_font_px = int(self._settings.value(FONT_SIZE_KEY, DEFAULT_FONT_PX))
            initial_font_family = str(
                self._settings.value(FONT_FAMILY_KEY, DEFAULT_FONT_CHOICE)
            )
            viewer_screen = ViewerScreen(
                database_path,
                initial_font_px=initial_font_px,
                initial_font_family=initial_font_family,
            )
            search_screen.open_in_viewer_requested.connect(
                lambda book_id, page_number: self._open_in_viewer(
                    viewer_screen, book_id, page_number
                )
            )
            import_screen = ImportScreen(database_path)
            import_screen.library_imported.connect(self._on_library_imported)
            self._stack.addWidget(search_screen)
            self._stack.addWidget(viewer_screen)
            self._stack.addWidget(import_screen)
            self._stack.addWidget(LogsScreen(log_directory))
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

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(rail)
        body_layout.addWidget(self._stack, stretch=1)

        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        if self._header_bar is not None:
            central_layout.addWidget(self._header_bar)
        central_layout.addWidget(body, stretch=1)
        self.setCentralWidget(central)

    def _on_library_imported(self) -> None:
        """Refresh the header's live stats after a new library is imported."""
        if self._header_bar is not None:
            self._header_bar.refresh_stats()

    def _build_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("navRail")
        rail.setFixedWidth(RAIL_WIDTH)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(8, 14, 8, 14)
        rail_layout.setSpacing(4)

        self._rail_buttons: list[QToolButton] = []
        for index, (key, icon_name) in enumerate(zip(_RAIL_KEYS, _RAIL_ICON_NAMES, strict=True)):
            button = QToolButton()
            button.setText(self._translator.tr(key))
            button.setIcon(rail_icon(icon_name))
            button.setIconSize(QSize(20, 20))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
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
    heading.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {INK};")
    layout.addWidget(heading)

    body = QLabel(message)
    body.setAlignment(Qt.AlignmentFlag.AlignCenter)
    body.setWordWrap(True)
    body.setStyleSheet(MUTED_LABEL_STYLE)
    layout.addWidget(body)

    layout.addStretch(1)
    return widget
