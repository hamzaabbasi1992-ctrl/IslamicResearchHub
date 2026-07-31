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
from islamic_research_hub.infrastructure.persistence.pdf_match_candidate_repository import (
    PdfMatchCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (
    RecentBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.ai_panel_screen import AiAssistantPanel
from islamic_research_hub.interfaces.desktop_app.duplicate_manager_screen import (
    DuplicateManagerScreen,
)
from islamic_research_hub.interfaces.desktop_app.header_bar import HeaderBar
from islamic_research_hub.interfaces.desktop_app.home_screen import HomeScreen
from islamic_research_hub.interfaces.desktop_app.i18n import (
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
    Translator,
)
from islamic_research_hub.interfaces.desktop_app.icons import rail_icon
from islamic_research_hub.interfaces.desktop_app.import_screen import ImportScreen
from islamic_research_hub.interfaces.desktop_app.logs_screen import LogsScreen
from islamic_research_hub.interfaces.desktop_app.pdf_viewer_screen import PdfViewerScreen
from islamic_research_hub.interfaces.desktop_app.quick_open_dialog import QuickOpenDialog
from islamic_research_hub.interfaces.desktop_app.reading_fonts import DEFAULT_FONT_CHOICE
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen
from islamic_research_hub.interfaces.desktop_app.settings_screen import (
    FONT_FAMILY_KEY,
    FONT_SIZE_KEY,
    SettingsScreen,
)
from islamic_research_hub.interfaces.desktop_app.shortcuts import install_shortcuts
from islamic_research_hub.interfaces.desktop_app.taxonomy_browser_screen import (
    TaxonomyBrowserScreen,
)
from islamic_research_hub.interfaces.desktop_app.theme import INK, MUTED_LABEL_STYLE
from islamic_research_hub.interfaces.desktop_app.theme_controller import ThemeController
from islamic_research_hub.interfaces.desktop_app.viewer_screen import (
    DEFAULT_FONT_PX,
    ViewerScreen,
)
from islamic_research_hub.interfaces.desktop_app.workspace_screen import WorkspaceScreen

RAIL_WIDTH = 84
# "rail-viewer" is gone: the reader no longer has its own destination - it
# opens inline inside the Search/Workspace screen (see WorkspaceScreen).
_RAIL_KEYS = (
    "rail-home",
    "rail-search",
    "rail-libraries",
    "rail-duplicates",
    "rail-taxonomy",
    "rail-logs",
    "rail-settings",
)
_RAIL_ICON_NAMES = ("home", "search", "import", "duplicates", "taxonomy", "logs", "settings")
_PLACEHOLDER_TITLES = (
    "Database not found",
    "Search",
    "Libraries",
    "Duplicates",
    "Taxonomy",
    "Logs",
    "Settings",
)
# Index of the Search/Workspace page in `self._stack`, once a real database
# is loaded. `_open_in_viewer`/`_open_pdf` switch to this page directly -
# named as one constant, rather than a hardcoded index, so it stays correct
# as the rail is reordered/grown across the desktop UI redesign's milestones.
_WORKSPACE_STACK_INDEX = 1


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
        self._theme_controller = ThemeController(self._settings)

        self._stack = QStackedWidget()
        self._header_bar: HeaderBar | None = None
        self._maknoon_pdf_folder = maknoon_pdf_folder
        self._browser: BookBrowserRepository | None = None
        self._bookmarks: BookmarkRepository | None = None
        self._recent_books: RecentBookRepository | None = None
        self._pdf_matches: PdfMatchCandidateRepository | None = None
        self._pdf_fallback_book_id: int | None = None
        self._pdf_fallback_path: Path | None = None
        self._search_screen: SearchScreen | None = None
        self._viewer_screen: ViewerScreen | None = None
        self._pdf_viewer_screen: PdfViewerScreen | None = None
        self._viewer_stack: QStackedWidget | None = None
        self._import_screen: ImportScreen | None = None
        self._workspace_screen: WorkspaceScreen | None = None
        self._home_screen: HomeScreen | None = None
        if database_path.is_file():
            self._browser = BookBrowserRepository(database_path)
            self._bookmarks = BookmarkRepository(database_path)
            self._recent_books = RecentBookRepository(database_path)
            self._pdf_matches = PdfMatchCandidateRepository(database_path)
            self._header_bar = HeaderBar(database_path, self._translator)
            self._search_screen = SearchScreen(
                database_path,
                maknoon_pdf_folder,
                recent_books=self._recent_books,
                # Real fixes made this safe to enable - see CHANGELOG:
                # semantic search now runs on a background QThread (never
                # blocks keyword results, which still appear instantly),
                # and two real query bottlenecks were fixed (a
                # metadata-join that fetched full page text for every
                # embedded row, and per-row numpy array construction).
                # Confirmed for real: ~36s once (one-time model import),
                # ~8-9s per search after that at ~600K+ embedded pages,
                # entirely in the background.
                enable_lazy_semantic_search=True,
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
            self._viewer_screen.pdf_fallback_requested.connect(self._on_pdf_fallback_requested)
            self._pdf_viewer_screen = PdfViewerScreen()
            self._pdf_viewer_screen.bookmark_toggled.connect(self._on_bookmark_toggled)
            self._viewer_stack = QStackedWidget()
            self._viewer_stack.addWidget(self._viewer_screen)
            self._viewer_stack.addWidget(self._pdf_viewer_screen)
            ai_panel = AiAssistantPanel(self._settings)
            self._workspace_screen = WorkspaceScreen(
                self._search_screen, self._viewer_stack, ai_panel
            )

            self._search_screen.open_in_viewer_requested.connect(self._open_in_viewer)
            self._import_screen = ImportScreen(database_path)
            self._import_screen.library_imported.connect(self._on_library_imported)
            duplicate_manager_screen = DuplicateManagerScreen(database_path)
            duplicate_manager_screen.duplicates_resolved.connect(self._on_duplicates_resolved)
            taxonomy_browser_screen = TaxonomyBrowserScreen(database_path, browser=self._browser)
            taxonomy_browser_screen.open_in_viewer_requested.connect(self._open_in_viewer)
            self._home_screen = HomeScreen(
                database_path,
                browser=self._browser,
                recent_books=self._recent_books,
                bookmarks=self._bookmarks,
            )
            self._home_screen.open_in_viewer_requested.connect(self._open_in_viewer)
            self._stack.addWidget(self._home_screen)
            self._stack.addWidget(self._workspace_screen)
            self._stack.addWidget(self._import_screen)
            self._stack.addWidget(duplicate_manager_screen)
            self._stack.addWidget(taxonomy_browser_screen)
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

        self._shortcuts = install_shortcuts(self)
        if self._header_bar is not None and self._rail_buttons:
            self._header_bar.set_current_location(self._rail_buttons[0].text())

    def _on_library_imported(self, library_name: str) -> None:
        """Refresh corpus-wide stats and note the import on Home, after a new library import."""
        self._refresh_corpus_dependent_ui()
        if self._home_screen is not None:
            self._home_screen.note_library_imported(library_name)

    def _on_duplicates_resolved(self) -> None:
        """Refresh library counts and corpus-wide stats after a duplicate
        cleanup actually removes book(s) - the same downstream data an
        import changes, just via a removal instead."""
        if self._import_screen is not None:
            self._import_screen.refresh()
        self._refresh_corpus_dependent_ui()

    def _refresh_corpus_dependent_ui(self) -> None:
        if self._header_bar is not None:
            self._header_bar.refresh_stats()
        if self._home_screen is not None:
            self._home_screen.refresh()

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

    def open_quick_open(self) -> None:
        """Show the Quick Open dialog (also reachable via Ctrl+P) - a
        filterable jump to any rail screen or recent book."""
        if self._recent_books is None:
            return
        rail_labels = tuple(button.text() for button in self._rail_buttons)
        dialog = QuickOpenDialog(rail_labels, self._recent_books, parent=self)
        dialog.screen_requested.connect(self._show_screen)
        dialog.book_requested.connect(self._open_in_viewer)
        dialog.exec()

    def _show_screen(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        for button_index, button in enumerate(self._rail_buttons):
            button.setChecked(button_index == index)
        if self._header_bar is not None and 0 <= index < len(self._rail_buttons):
            self._header_bar.set_current_location(self._rail_buttons[index].text())

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
            and self._workspace_screen is not None
            and self._viewer_screen.load_book(book_id, bookmarked_pages=bookmarked_pages)
            and self._viewer_screen.has_content()
        ):
            self._viewer_screen.jump_to_page_number(page_number)
            self._recent_books.record_open(book_id, page_number)
            self._workspace_screen.show_reader(self._viewer_screen)
            self._show_screen(_WORKSPACE_STACK_INDEX)
            self._offer_pdf_fallback(book_id)
            return

        source = self._browser.get_book_source(book_id)
        pdf_path = (
            resolve_pdf_path(source[1], source[0], self._maknoon_pdf_folder)
            if source is not None
            else None
        )
        if pdf_path is not None:
            self._open_pdf(pdf_path, book_id, page_number)

    def _offer_pdf_fallback(self, book_id: int) -> None:
        """Show the "scanned PDF available" banner for a stub book, if a PDF can be found.

        Tries the book's own Source first - reliable, e.g. the original
        Al-Maknoon library's filename-stem lookup, which real data showed
        already resolves for 481 stub books with no fuzzy matching
        involved - before falling back to a fuzzy cross-library title
        match from `PdfMatchCandidateRepository`.
        """
        self._pdf_fallback_book_id = None
        self._pdf_fallback_path = None
        if self._viewer_screen is None or self._browser is None or self._pdf_matches is None:
            return
        if not self._pdf_matches.is_stub(book_id):
            self._viewer_screen.set_pdf_fallback_available(False)
            return

        own_source = self._browser.get_book_source(book_id)
        pdf_path = (
            resolve_pdf_path(own_source[1], own_source[0], self._maknoon_pdf_folder)
            if own_source is not None
            else None
        )
        fallback_book_id = book_id

        if pdf_path is None:
            match = self._pdf_matches.get_match(book_id)
            if match is not None:
                matched_source = self._browser.get_book_source(match.pdf_book_id)
                pdf_path = (
                    resolve_pdf_path(matched_source[1], matched_source[0], self._maknoon_pdf_folder)
                    if matched_source is not None
                    else None
                )
                fallback_book_id = match.pdf_book_id

        if pdf_path is not None:
            self._pdf_fallback_book_id = fallback_book_id
            self._pdf_fallback_path = pdf_path
        self._viewer_screen.set_pdf_fallback_available(pdf_path is not None)

    def _on_pdf_fallback_requested(self) -> None:
        """Open the fuzzy-matched PDF the user asked for from the Viewer's fallback banner."""
        if self._pdf_fallback_path is not None and self._pdf_fallback_book_id is not None:
            self._open_pdf(self._pdf_fallback_path, self._pdf_fallback_book_id, page_number=1)

    def _open_pdf(self, pdf_path: Path, book_id: int, page_number: int) -> None:
        """Load a real PDF into `PdfViewerScreen` and switch to it."""
        if self._pdf_viewer_screen is None or self._bookmarks is None or self._recent_books is None:
            return
        if self._browser is None or self._workspace_screen is None:
            return
        bookmarked_pages = self._bookmarks.list_bookmarked_pages(book_id)
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
            self._recent_books.record_open(book_id, page_number)
            self._workspace_screen.show_reader(self._pdf_viewer_screen)
            self._show_screen(_WORKSPACE_STACK_INDEX)

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
