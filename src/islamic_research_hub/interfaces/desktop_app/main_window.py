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

from islamic_research_hub.application.pdf_source_resolver import resolve_pdf_path
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.bookmark_repository import (
    BookmarkRepository,
)
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (
    RecentBookRepository,
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
from islamic_research_hub.interfaces.desktop_app.pdf_viewer_screen import PdfViewerScreen
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
        self._maknoon_pdf_folder = maknoon_pdf_folder
        self._browser: BookBrowserRepository | None = None
        self._bookmarks: BookmarkRepository | None = None
        self._recent_books: RecentBookRepository | None = None
        self._viewer_screen: ViewerScreen | None = None
        self._pdf_viewer_screen: PdfViewerScreen | None = None
        if database_path.is_file():
            self._browser = BookBrowserRepository(database_path)
            self._bookmarks = BookmarkRepository(database_path)
            self._recent_books = RecentBookRepository(database_path)
            self._header_bar = HeaderBar(database_path, self._translator)
            search_screen = SearchScreen(
                database_path, maknoon_pdf_folder, recent_books=self._recent_books
            )
            initial_font_px = int(self._settings.value(FONT_SIZE_KEY, DEFAULT_FONT_PX))
            initial_font_family = str(
                self._settings.value(FONT_FAMILY_KEY, DEFAULT_FONT_CHOICE)
            )
            self._viewer_screen = ViewerScreen(
                database_path,
                initial_font_px=initial_font_px,
                initial_font_family=initial_font_family,
            )
            self._viewer_screen.bookmark_toggled.connect(self._on_bookmark_toggled)
            self._pdf_viewer_screen = PdfViewerScreen()
            self._pdf_viewer_screen.bookmark_toggled.connect(self._on_bookmark_toggled)
            self._viewer_stack = QStackedWidget()
            self._viewer_stack.addWidget(self._viewer_screen)
            self._viewer_stack.addWidget(self._pdf_viewer_screen)

            search_screen.open_in_viewer_requested.connect(self._open_in_viewer)
            import_screen = ImportScreen(database_path)
            import_screen.library_imported.connect(self._on_library_imported)
            self._stack.addWidget(search_screen)
            self._stack.addWidget(self._viewer_stack)
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

    def _open_in_viewer(self, book_id: int, page_number: int) -> None:
        """Load a book into the Viewer and switch to it.

        Real text pages (~15,162 books) open in `ViewerScreen`; books with
        no extracted text at all (~9,172 real PDF-only books, PageCount=0)
        fall back to `PdfViewerScreen`, rendering the actual source PDF -
        previously these had no in-app reading at all, only "Open PDF"
        (the OS's external viewer).
        """
        if self._browser is None or self._bookmarks is None or self._recent_books is None:
            return
        bookmarked_pages = self._bookmarks.list_bookmarked_pages(book_id)

        if (
            self._viewer_screen is not None
            and self._viewer_screen.load_book(book_id, bookmarked_pages=bookmarked_pages)
            and self._viewer_screen.has_content()
        ):
            self._viewer_screen.jump_to_page_number(page_number)
            self._viewer_stack.setCurrentWidget(self._viewer_screen)
            self._recent_books.record_open(book_id, page_number)
            self._show_screen(1)
            return

        source = self._browser.get_book_source(book_id)
        if source is None or self._pdf_viewer_screen is None:
            return
        pdf_path = resolve_pdf_path(source[1], source[0], self._maknoon_pdf_folder)
        if pdf_path is None:
            return
        metadata = self._browser.get_book_metadata(book_id)
        loaded = self._pdf_viewer_screen.load_pdf(
            pdf_path,
            title=metadata.title if metadata else None,
            author=metadata.author if metadata else None,
            book_id=book_id,
            bookmarked_pages=bookmarked_pages,
        )
        if loaded:
            self._pdf_viewer_screen.jump_to_page_number(page_number)
            self._viewer_stack.setCurrentWidget(self._pdf_viewer_screen)
            self._recent_books.record_open(book_id, page_number)
            self._show_screen(1)

    def _on_bookmark_toggled(self, book_id: int, page_number: int, is_bookmarked: bool) -> None:
        if self._bookmarks is not None:
            self._bookmarks.set_bookmark(book_id, page_number, is_bookmarked)

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
