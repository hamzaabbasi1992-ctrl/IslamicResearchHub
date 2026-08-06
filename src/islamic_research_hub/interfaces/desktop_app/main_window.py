"""Main window: a navigation rail plus a stacked set of screens."""

import sqlite3
from contextlib import closing
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.application.book_chunking import compute_extraction_chunks
from islamic_research_hub.application.extraction_cost_estimate import estimate_extraction_cost
from islamic_research_hub.application.pdf_source_resolver import (
    candidate_pdf_path,
    resolve_pdf_path,
)
from islamic_research_hub.infrastructure.audio.wav_writer import write_wav
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.bookmark_repository import (
    BookmarkRepository,
)
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import (
    EventCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.flashcard_candidate_repository import (
    FlashcardCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.narrator_candidate_repository import (
    NarratorCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.pdf_match_candidate_repository import (
    PdfMatchCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (
    RecentBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.ai_agent_worker import AiAgentWorker
from islamic_research_hub.interfaces.desktop_app.ai_panel_screen import AiAssistantPanel
from islamic_research_hub.interfaces.desktop_app.ai_unavailable_dialog import (
    show_ai_unavailable_dialog,
)
from islamic_research_hub.interfaces.desktop_app.citation_manager_screen import (
    CitationManagerScreen,
)
from islamic_research_hub.interfaces.desktop_app.collections_screen import CollectionsScreen
from islamic_research_hub.interfaces.desktop_app.duplicate_manager_screen import (
    DuplicateManagerScreen,
)
from islamic_research_hub.interfaces.desktop_app.event_extraction_worker import (
    EventExtractionWorker,
)
from islamic_research_hub.interfaces.desktop_app.event_manager_screen import EventManagerScreen
from islamic_research_hub.interfaces.desktop_app.flashcard_extraction_worker import (
    FlashcardExtractionWorker,
)
from islamic_research_hub.interfaces.desktop_app.flashcard_manager_screen import (
    FlashcardManagerScreen,
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
from islamic_research_hub.interfaces.desktop_app.knowledge_gap_screen import KnowledgeGapScreen
from islamic_research_hub.interfaces.desktop_app.logs_screen import LogsScreen
from islamic_research_hub.interfaces.desktop_app.narrator_extraction_worker import (
    NarratorExtractionWorker,
)
from islamic_research_hub.interfaces.desktop_app.narrator_manager_screen import (
    NarratorManagerScreen,
)
from islamic_research_hub.interfaces.desktop_app.pdf_viewer_screen import PdfViewerScreen
from islamic_research_hub.interfaces.desktop_app.preservation_report_screen import (
    PreservationReportScreen,
)
from islamic_research_hub.interfaces.desktop_app.quick_open_dialog import QuickOpenDialog
from islamic_research_hub.interfaces.desktop_app.reading_fonts import DEFAULT_FONT_CHOICE
from islamic_research_hub.interfaces.desktop_app.podcast_generation_worker import (
    PodcastGenerationWorker,
)
from islamic_research_hub.interfaces.desktop_app.search_screen import SearchScreen
from islamic_research_hub.interfaces.desktop_app.slide_deck_worker import (
    SlideDeckGenerationWorker,
)
from islamic_research_hub.interfaces.desktop_app.settings_screen import (
    AI_AGENT_ENABLED_KEY,
    AI_AGENT_PROVIDER_KEY,
    AI_AGENT_PROVIDER_LABELS,
    AI_AGENT_PROVIDERS,
    FONT_FAMILY_KEY,
    FONT_SIZE_KEY,
    TRANSLATION_ENABLED_KEY,
    TTS_ENABLED_KEY,
    VOICE_SEARCH_ENABLED_KEY,
    SettingsScreen,
    resolve_ai_agent_api_key,
    resolve_maknoon_pdf_folder,
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
from islamic_research_hub.research_notes.slide_deck_export import export_slide_deck_to_pptx

RAIL_WIDTH = 112
"""Real bug fixed here: at the old 84px, English labels like "Preservation"
and "Knowledge Gaps" didn't fit even wrapped to two lines, so Qt's own
tool-button layout silently mid-word-elided them ("Kno...aps") - real,
reported UI text loss, not a cosmetic nit. Widened so every real rail
label (English is the widest of the three supported languages) fits
without elision."""
# "rail-viewer" is gone: the reader no longer has its own destination - it
# opens inline inside the Search/Workspace screen (see WorkspaceScreen).
_RAIL_KEYS = (
    "rail-home",
    "rail-search",
    "rail-libraries",
    "rail-duplicates",
    "rail-taxonomy",
    "rail-citations",
    "rail-events",
    "rail-narrators",
    "rail-knowledge-gaps",
    "rail-preservation",
    "rail-collections",
    "rail-flashcards",
    "rail-logs",
    "rail-settings",
)
_RAIL_ICON_NAMES = (
    "home",
    "search",
    "import",
    "duplicates",
    "taxonomy",
    "citations",
    "events",
    "narrators",
    "knowledge-gaps",
    "preservation",
    "collections",
    "flashcards",
    "logs",
    "settings",
)
_PLACEHOLDER_TITLES = (
    "Database not found",
    "Search",
    "Libraries",
    "Duplicates",
    "Taxonomy",
    "Citations",
    "Events",
    "Logs",
    "Settings",
)
# Index of the Search/Workspace page in `self._stack`, once a real database
# is loaded. `_open_in_viewer`/`_open_pdf` switch to this page directly -
# named as one constant, rather than a hardcoded index, so it stays correct
# as the rail is reordered/grown across the desktop UI redesign's milestones.
_WORKSPACE_STACK_INDEX = 1
_DUPLICATE_MANAGER_STACK_INDEX = 3
"""So `PreservationReportScreen`'s "Review in Duplicate Manager" button
can navigate there without a hardcoded index scattered at the call site."""


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
        # Real bug found and fixed: 1180px used to comfortably fit the real
        # workspace content, but adding the reader's "Extract Events" text
        # button (waqiat milestone) pushed WorkspaceScreen's real
        # minimumSizeHint width to 1196px - 16px past the old default,
        # confirmed via direct measurement. Below its own real minimum,
        # Qt abandons the outer splitter's intended stretch ratios (search:
        # reader:AI = 2:4:1) and falls back to near-equal thirds instead -
        # this is what made maximize/restore look like they barely did
        # anything and the whole layout feel cramped from first launch.
        # 1260px gives real margin above the current 1196px minimum so a
        # future small toolbar addition doesn't immediately regress this
        # again.
        self.resize(1260, 760)

        self._settings = settings or QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        self._translator = Translator(self._settings)
        self._translator.language_changed.connect(self._on_language_changed)
        self._theme_controller = ThemeController(self._settings)

        self._stack = QStackedWidget()
        self._header_bar: HeaderBar | None = None
        self._default_maknoon_pdf_folder = maknoon_pdf_folder
        self._maknoon_pdf_folder = resolve_maknoon_pdf_folder(self._settings, maknoon_pdf_folder)
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
        self._ai_panel: AiAssistantPanel | None = None
        self._database_path: Path | None = None
        self._event_extraction_worker: EventExtractionWorker | None = None
        self._narrator_extraction_worker: NarratorExtractionWorker | None = None
        self._explain_worker: AiAgentWorker | None = None
        self._summarize_passage_worker: AiAgentWorker | None = None
        self._compare_passage_worker: AiAgentWorker | None = None
        self._flashcard_extraction_worker: FlashcardExtractionWorker | None = None
        self._slide_deck_worker: SlideDeckGenerationWorker | None = None
        self._podcast_worker: PodcastGenerationWorker | None = None
        if database_path.is_file():
            self._database_path = database_path
            self._browser = BookBrowserRepository(database_path)
            self._bookmarks = BookmarkRepository(database_path)
            self._recent_books = RecentBookRepository(database_path)
            self._pdf_matches = PdfMatchCandidateRepository(database_path)
            self._header_bar = HeaderBar(database_path, self._translator)
            self._search_screen = SearchScreen(
                database_path,
                maknoon_pdf_folder,
                self._translator,
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
                # Runs local faster-whisper transcription on a background
                # QThread (see VoiceSearchWorker), same never-block-the-GUI
                # pattern as semantic search above. Defaults off, same
                # reasoning as TTS below - tied to a real Settings toggle
                # since it implies an optional model download.
                enable_lazy_voice_search=bool(
                    self._settings.value(VOICE_SEARCH_ENABLED_KEY, False, type=bool)
                ),
            )
            initial_font_px = int(self._settings.value(FONT_SIZE_KEY, DEFAULT_FONT_PX))
            initial_font_family = str(
                self._settings.value(FONT_FAMILY_KEY, DEFAULT_FONT_CHOICE)
            )
            self._viewer_screen = ViewerScreen(
                database_path,
                self._translator,
                initial_font_px=initial_font_px,
                initial_font_family=initial_font_family,
                # Runs local MMS-TTS synthesis on a background QThread (see
                # TtsWorker/ViewerScreen._get_or_build_tts_narration_service),
                # same never-block-the-GUI pattern as semantic search above -
                # essential here, not optional: confirmed for real against
                # the actual running app (not just a standalone script) that
                # a real ~2,000-character page takes ~79s to synthesize on
                # CPU (~3.1x realtime - see CHANGELOG). Unlike semantic
                # search this defaults off - it's tied to a real Settings
                # toggle (TTS_ENABLED_KEY) that's off until the user opts in,
                # since it implies an optional model download and a real
                # wait before a long page starts playing.
                enable_lazy_tts=bool(
                    self._settings.value(TTS_ENABLED_KEY, False, type=bool)
                ),
                # Gates the reader's own "Extract Events" button - same
                # Settings-driven opt-in as the AI Agent panel below, since
                # both make real paid API calls through the same service.
                enable_lazy_ai_agent=bool(
                    self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool)
                ),
                # Gates the reader's "Translate to English" context-menu
                # item - same real Settings-toggle opt-in as TTS above
                # (TRANSLATION_ENABLED_KEY), since it implies an optional
                # local MarianMT model download.
                enable_lazy_translation=bool(
                    self._settings.value(TRANSLATION_ENABLED_KEY, False, type=bool)
                ),
            )
            self._viewer_screen.bookmark_toggled.connect(self._on_bookmark_toggled)
            self._viewer_screen.pdf_fallback_requested.connect(self._on_pdf_fallback_requested)
            self._viewer_screen.extract_events_requested.connect(
                self._on_extract_events_requested
            )
            self._viewer_screen.extract_narrators_requested.connect(
                self._on_extract_narrators_requested
            )
            self._viewer_screen.explain_selection_requested.connect(
                self._on_explain_selection_requested
            )
            self._viewer_screen.summarize_selection_requested.connect(
                self._on_summarize_selection_requested
            )
            self._viewer_screen.compare_selection_requested.connect(
                self._on_compare_selection_requested
            )
            self._viewer_screen.generate_flashcards_requested.connect(
                self._on_generate_flashcards_requested
            )
            self._viewer_screen.generate_slide_deck_requested.connect(
                self._on_generate_slide_deck_requested
            )
            self._viewer_screen.generate_podcast_requested.connect(
                self._on_generate_podcast_requested
            )
            self._pdf_viewer_screen = PdfViewerScreen(self._translator)
            self._pdf_viewer_screen.bookmark_toggled.connect(self._on_bookmark_toggled)
            self._viewer_stack = QStackedWidget()
            self._viewer_stack.addWidget(self._viewer_screen)
            self._viewer_stack.addWidget(self._pdf_viewer_screen)
            self._ai_panel = AiAssistantPanel(
                self._settings,
                self._translator,
                database_path=database_path,
                # Real tool-calling loop over a cloud LLM (Anthropic/OpenAI/
                # Gemini, chosen in Settings) - the app's first feature
                # making a paid external API call, so it defaults off like
                # TTS/voice search's own opt-in model-download toggles.
                enable_lazy_ai_agent=bool(
                    self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool)
                ),
            )
            self._workspace_screen = WorkspaceScreen(
                self._search_screen, self._viewer_stack, self._ai_panel
            )

            self._search_screen.open_in_viewer_requested.connect(self._open_in_viewer)
            self._search_screen.ai_quick_ask_requested.connect(self._on_ai_quick_ask_requested)
            self._import_screen = ImportScreen(database_path, self._translator)
            self._import_screen.library_imported.connect(self._on_library_imported)
            duplicate_manager_screen = DuplicateManagerScreen(database_path, self._translator)
            duplicate_manager_screen.duplicates_resolved.connect(self._on_duplicates_resolved)
            taxonomy_browser_screen = TaxonomyBrowserScreen(
                database_path, self._translator, browser=self._browser
            )
            taxonomy_browser_screen.open_in_viewer_requested.connect(self._open_in_viewer)
            citation_manager_screen = CitationManagerScreen(
                database_path, self._translator, browser=self._browser
            )
            event_manager_screen = EventManagerScreen(
                database_path, self._translator, browser=self._browser
            )
            narrator_manager_screen = NarratorManagerScreen(
                database_path, self._translator, browser=self._browser
            )
            knowledge_gap_screen = KnowledgeGapScreen(
                database_path, self._translator, browser=self._browser
            )
            knowledge_gap_screen.open_in_viewer_requested.connect(self._open_in_viewer)
            preservation_report_screen = PreservationReportScreen(database_path, self._translator)
            preservation_report_screen.review_duplicates_requested.connect(
                lambda: self._show_screen(_DUPLICATE_MANAGER_STACK_INDEX)
            )
            collections_screen = CollectionsScreen(
                database_path, self._translator, browser=self._browser
            )
            collections_screen.open_in_viewer_requested.connect(self._open_in_viewer)
            flashcard_manager_screen = FlashcardManagerScreen(
                database_path, self._translator, browser=self._browser
            )
            self._home_screen = HomeScreen(
                database_path,
                self._translator,
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
            self._stack.addWidget(citation_manager_screen)
            self._stack.addWidget(event_manager_screen)
            self._stack.addWidget(narrator_manager_screen)
            self._stack.addWidget(knowledge_gap_screen)
            self._stack.addWidget(preservation_report_screen)
            self._stack.addWidget(collections_screen)
            self._stack.addWidget(flashcard_manager_screen)
            self._stack.addWidget(LogsScreen(log_directory, self._translator))
            self._stack.addWidget(
                SettingsScreen(
                    database_path,
                    self._settings,
                    self._translator,
                    default_maknoon_pdf_folder=self._default_maknoon_pdf_folder,
                )
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
            return
        # Real bug fixed here: this used to silently do nothing when the
        # file wasn't found on disk (e.g. an external drive with the real
        # PDF archive isn't plugged in right now) - "the book doesn't
        # open and there's no error." A real, expected path is still
        # computable even though the file's missing, so tell the user
        # exactly where to put it back instead of failing silently.
        if source is not None:
            expected_path = candidate_pdf_path(source[1], source[0], self._maknoon_pdf_folder)
            if expected_path is not None:
                QMessageBox.warning(
                    self,
                    self._translator.tr("pdf-missing-title"),
                    self._translator.tr("pdf-missing-message").format(path=expected_path),
                )

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

    def _on_extract_events_requested(self, book_id: int) -> None:
        """Extract real events from one book: pre-flight check (enabled +
        a real key), a real chunk count/cost estimate the user confirms
        before anything runs, then a background worker. Reuses
        `AiAssistantPanel`'s one real lazy-build path (`self._ai_panel`)
        rather than duplicating Settings-driven provider/key resolution.
        """
        if self._browser is None or self._database_path is None or self._ai_panel is None:
            return
        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        provider_label = AI_AGENT_PROVIDER_LABELS.get(provider_code, provider_code)
        enabled = bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))
        if not enabled:
            show_ai_unavailable_dialog(
                self, "Extract Events", "AI Agent is not enabled in Settings."
            )
            return
        if not resolve_ai_agent_api_key(self._settings, provider_code):
            show_ai_unavailable_dialog(
                self, "Extract Events", f"No API key is set for {provider_label}."
            )
            return

        metadata = self._browser.get_book_metadata(book_id)
        if metadata is None:
            return
        chapters = self._browser.list_chapters(book_id)
        chunks = compute_extraction_chunks(chapters, metadata.page_count)
        if not chunks:
            QMessageBox.information(
                self, "Extract Events", "This book has no real page content to extract from."
            )
            return

        with closing(sqlite3.connect(self._database_path)) as connection:
            total_characters = (
                connection.execute(
                    "SELECT SUM(LENGTH(Content)) FROM Pages WHERE BookID = ?", (book_id,)
                ).fetchone()[0]
                or 0
            )
        estimated_cost = estimate_extraction_cost(total_characters, len(chunks), provider_code)

        confirmed = QMessageBox.question(
            self,
            "Extract Events",
            f"This will make ~{len(chunks)} real API call(s) to {provider_label}, "
            f"estimated cost ~${estimated_cost:.2f} (approximate - not a "
            "billing guarantee). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        repository = EventCandidateRepository(self._database_path)
        worker = EventExtractionWorker(
            self._ai_panel.get_or_build_ai_agent_service, repository, book_id, chunks, self
        )
        worker.extraction_finished.connect(self._on_extraction_finished)
        worker.extraction_unavailable.connect(
            lambda reason: show_ai_unavailable_dialog(self, "Extract Events", reason)
        )
        self._event_extraction_worker = worker
        worker.start()

    def _on_extraction_finished(self, count: int) -> None:
        QMessageBox.information(
            self, "Extract Events", f"{count} event(s) found - review them in the Events screen."
        )

    def _on_extract_narrators_requested(self, book_id: int) -> None:
        """Extract real narrator mentions from one book - same pre-flight
        check, chunk/cost estimate, and background-worker shape as
        `_on_extract_events_requested`."""
        if self._browser is None or self._database_path is None or self._ai_panel is None:
            return
        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        provider_label = AI_AGENT_PROVIDER_LABELS.get(provider_code, provider_code)
        enabled = bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))
        if not enabled:
            show_ai_unavailable_dialog(
                self, "Extract Narrators", "AI Agent is not enabled in Settings."
            )
            return
        if not resolve_ai_agent_api_key(self._settings, provider_code):
            show_ai_unavailable_dialog(
                self, "Extract Narrators", f"No API key is set for {provider_label}."
            )
            return

        metadata = self._browser.get_book_metadata(book_id)
        if metadata is None:
            return
        chapters = self._browser.list_chapters(book_id)
        chunks = compute_extraction_chunks(chapters, metadata.page_count)
        if not chunks:
            QMessageBox.information(
                self, "Extract Narrators", "This book has no real page content to extract from."
            )
            return

        with closing(sqlite3.connect(self._database_path)) as connection:
            total_characters = (
                connection.execute(
                    "SELECT SUM(LENGTH(Content)) FROM Pages WHERE BookID = ?", (book_id,)
                ).fetchone()[0]
                or 0
            )
        estimated_cost = estimate_extraction_cost(total_characters, len(chunks), provider_code)

        confirmed = QMessageBox.question(
            self,
            "Extract Narrators",
            f"This will make ~{len(chunks)} real API call(s) to {provider_label}, "
            f"estimated cost ~${estimated_cost:.2f} (approximate - not a "
            "billing guarantee). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        repository = NarratorCandidateRepository(self._database_path)
        worker = NarratorExtractionWorker(
            self._ai_panel.get_or_build_ai_agent_service, repository, book_id, chunks, self
        )
        worker.extraction_finished.connect(self._on_narrator_extraction_finished)
        worker.extraction_unavailable.connect(
            lambda reason: show_ai_unavailable_dialog(self, "Extract Narrators", reason)
        )
        self._narrator_extraction_worker = worker
        worker.start()

    def _on_narrator_extraction_finished(self, count: int) -> None:
        QMessageBox.information(
            self,
            "Extract Narrators",
            f"{count} narrator mention(s) found - review them in the Narrators screen.",
        )

    def _on_generate_flashcards_requested(self, book_id: int) -> None:
        """Generate real study flashcards for one book (Phase 15
        Milestone 1: educational features) - same pre-flight check,
        chunk/cost estimate, and background-worker shape as
        `_on_extract_events_requested`."""
        if self._browser is None or self._database_path is None or self._ai_panel is None:
            return
        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        provider_label = AI_AGENT_PROVIDER_LABELS.get(provider_code, provider_code)
        enabled = bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))
        if not enabled:
            show_ai_unavailable_dialog(
                self, "Generate Flashcards", "AI Agent is not enabled in Settings."
            )
            return
        if not resolve_ai_agent_api_key(self._settings, provider_code):
            show_ai_unavailable_dialog(
                self, "Generate Flashcards", f"No API key is set for {provider_label}."
            )
            return

        metadata = self._browser.get_book_metadata(book_id)
        if metadata is None:
            return
        chapters = self._browser.list_chapters(book_id)
        chunks = compute_extraction_chunks(chapters, metadata.page_count)
        if not chunks:
            QMessageBox.information(
                self, "Generate Flashcards", "This book has no real page content to extract from."
            )
            return

        with closing(sqlite3.connect(self._database_path)) as connection:
            total_characters = (
                connection.execute(
                    "SELECT SUM(LENGTH(Content)) FROM Pages WHERE BookID = ?", (book_id,)
                ).fetchone()[0]
                or 0
            )
        estimated_cost = estimate_extraction_cost(total_characters, len(chunks), provider_code)

        confirmed = QMessageBox.question(
            self,
            "Generate Flashcards",
            f"This will make ~{len(chunks)} real API call(s) to {provider_label}, "
            f"estimated cost ~${estimated_cost:.2f} (approximate - not a "
            "billing guarantee). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        repository = FlashcardCandidateRepository(self._database_path)
        worker = FlashcardExtractionWorker(
            self._ai_panel.get_or_build_ai_agent_service, repository, book_id, chunks, self
        )
        worker.extraction_finished.connect(self._on_flashcard_generation_finished)
        worker.extraction_unavailable.connect(
            lambda reason: show_ai_unavailable_dialog(self, "Generate Flashcards", reason)
        )
        self._flashcard_extraction_worker = worker
        worker.start()

    def _on_flashcard_generation_finished(self, count: int) -> None:
        QMessageBox.information(
            self,
            "Generate Flashcards",
            f"{count} flashcard(s) generated - review them in the Flashcards screen.",
        )

    def _on_generate_slide_deck_requested(self, book_id: int) -> None:
        """Generate real slide-deck content for one book (Phase 17
        Milestone 1: multimedia generation, scope narrowed to slide
        decks + podcasts only per direct instruction) - same pre-flight
        check, chunk/cost estimate, and background-worker shape as
        `_on_generate_flashcards_requested`. The one real difference:
        there's no candidate-review screen here - a slide is a formatted
        restatement of real content, not an asserted fact, so generated
        slides go straight to a real .pptx export instead of a DB table."""
        if self._browser is None or self._database_path is None or self._ai_panel is None:
            return
        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        provider_label = AI_AGENT_PROVIDER_LABELS.get(provider_code, provider_code)
        enabled = bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))
        if not enabled:
            show_ai_unavailable_dialog(
                self, "Generate Slide Deck", "AI Agent is not enabled in Settings."
            )
            return
        if not resolve_ai_agent_api_key(self._settings, provider_code):
            show_ai_unavailable_dialog(
                self, "Generate Slide Deck", f"No API key is set for {provider_label}."
            )
            return

        metadata = self._browser.get_book_metadata(book_id)
        if metadata is None:
            return
        chapters = self._browser.list_chapters(book_id)
        chunks = compute_extraction_chunks(chapters, metadata.page_count)
        if not chunks:
            QMessageBox.information(
                self, "Generate Slide Deck", "This book has no real page content to generate from."
            )
            return

        with closing(sqlite3.connect(self._database_path)) as connection:
            total_characters = (
                connection.execute(
                    "SELECT SUM(LENGTH(Content)) FROM Pages WHERE BookID = ?", (book_id,)
                ).fetchone()[0]
                or 0
            )
        estimated_cost = estimate_extraction_cost(total_characters, len(chunks), provider_code)

        confirmed = QMessageBox.question(
            self,
            "Generate Slide Deck",
            f"This will make ~{len(chunks)} real API call(s) to {provider_label}, "
            f"estimated cost ~${estimated_cost:.2f} (approximate - not a "
            "billing guarantee). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        worker = SlideDeckGenerationWorker(
            self._ai_panel.get_or_build_ai_agent_service, book_id, chunks, self
        )
        worker.generation_finished.connect(
            lambda slides, title=metadata.title: self._on_slide_deck_generation_finished(title, slides)
        )
        worker.generation_unavailable.connect(
            lambda reason: show_ai_unavailable_dialog(self, "Generate Slide Deck", reason)
        )
        self._slide_deck_worker = worker
        worker.start()

    def _on_slide_deck_generation_finished(self, book_title: str, slides: tuple) -> None:
        if not slides:
            QMessageBox.information(
                self,
                "Generate Slide Deck",
                "No real slide-worthy content was found in this book.",
            )
            return
        default_path = str(Path.home() / "Documents" / f"{book_title[:60]}.pptx")
        output_path_str, _filter = QFileDialog.getSaveFileName(
            self, "Generate Slide Deck", default_path, "PowerPoint Presentation (*.pptx)"
        )
        if not output_path_str:
            return
        export_slide_deck_to_pptx(book_title, slides, Path(output_path_str))
        QMessageBox.information(
            self,
            "Generate Slide Deck",
            f"{len(slides)} slide(s) generated and saved to {output_path_str}.",
        )

    def _on_generate_podcast_requested(self, book_id: int) -> None:
        """Generate a real narrated podcast for one book (Phase 17
        Milestone 1) - same pre-flight/chunk/cost-estimate/background-
        worker shape as `_on_generate_slide_deck_requested`, plus a
        second pre-flight check (TTS must also be real and available,
        not just the AI Agent) since this feature needs both."""
        if (
            self._browser is None
            or self._database_path is None
            or self._ai_panel is None
            or self._viewer_screen is None
        ):
            return
        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        provider_label = AI_AGENT_PROVIDER_LABELS.get(provider_code, provider_code)
        enabled = bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))
        if not enabled:
            show_ai_unavailable_dialog(
                self, "Generate Podcast", "AI Agent is not enabled in Settings."
            )
            return
        if not resolve_ai_agent_api_key(self._settings, provider_code):
            show_ai_unavailable_dialog(
                self, "Generate Podcast", f"No API key is set for {provider_label}."
            )
            return
        if not bool(self._settings.value(TTS_ENABLED_KEY, False, type=bool)):
            show_ai_unavailable_dialog(
                self, "Generate Podcast", "Text-to-speech is not enabled in Settings."
            )
            return

        metadata = self._browser.get_book_metadata(book_id)
        if metadata is None:
            return
        chapters = self._browser.list_chapters(book_id)
        chunks = compute_extraction_chunks(chapters, metadata.page_count)
        if not chunks:
            QMessageBox.information(
                self, "Generate Podcast", "This book has no real page content to narrate."
            )
            return

        with closing(sqlite3.connect(self._database_path)) as connection:
            total_characters = (
                connection.execute(
                    "SELECT SUM(LENGTH(Content)) FROM Pages WHERE BookID = ?", (book_id,)
                ).fetchone()[0]
                or 0
            )
        estimated_cost = estimate_extraction_cost(total_characters, len(chunks), provider_code)

        confirmed = QMessageBox.question(
            self,
            "Generate Podcast",
            f"This will make ~{len(chunks)} real API call(s) to {provider_label}, "
            f"estimated cost ~${estimated_cost:.2f} (approximate - not a "
            "billing guarantee), plus real local narration/synthesis time "
            "afterward. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        worker = PodcastGenerationWorker(
            self._ai_panel.get_or_build_ai_agent_service,
            self._viewer_screen.get_or_build_tts_narration_service,
            book_id,
            chunks,
            metadata.language,
            self,
        )
        worker.generation_finished.connect(
            lambda samples, sample_rate, title=metadata.title: self._on_podcast_generation_finished(
                title, samples, sample_rate
            )
        )
        worker.generation_unavailable.connect(
            lambda reason: show_ai_unavailable_dialog(self, "Generate Podcast", reason)
        )
        worker.generation_failed.connect(
            lambda reason: QMessageBox.information(self, "Generate Podcast", reason)
        )
        self._podcast_worker = worker
        worker.start()

    def _on_podcast_generation_finished(
        self, book_title: str, samples: tuple, sample_rate: int
    ) -> None:
        default_path = str(Path.home() / "Documents" / f"{book_title[:60]}.wav")
        output_path_str, _filter = QFileDialog.getSaveFileName(
            self, "Generate Podcast", default_path, "WAV Audio (*.wav)"
        )
        if not output_path_str:
            return
        write_wav(Path(output_path_str), samples, sample_rate)
        duration_seconds = len(samples) / sample_rate if sample_rate else 0
        QMessageBox.information(
            self,
            "Generate Podcast",
            f"~{duration_seconds:.0f}s of real narration generated and saved to {output_path_str}.",
        )

    def _on_explain_selection_requested(self, selected_text: str) -> None:
        """Explain one real passage the reader selected (Phase 13
        Milestone 1: AI reading assistant) - same pre-flight check as
        Extract Events/Narrators, but a single real API call (no
        chunking, no cost-estimate confirmation - same reasoning as the
        AI panel's own Ask box not showing one per question either)."""
        if self._viewer_screen is None or self._ai_panel is None:
            return
        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        provider_label = AI_AGENT_PROVIDER_LABELS.get(provider_code, provider_code)
        enabled = bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))
        if not enabled:
            show_ai_unavailable_dialog(
                self, "Explain this passage", "AI Agent is not enabled in Settings."
            )
            return
        if not resolve_ai_agent_api_key(self._settings, provider_code):
            show_ai_unavailable_dialog(
                self, "Explain this passage", f"No API key is set for {provider_label}."
            )
            return

        worker = AiAgentWorker(
            self._ai_panel.get_or_build_ai_agent_service, selected_text, "explain", self
        )
        worker.answer_ready.connect(
            lambda answer, _tool_calls: self._on_explain_answer_ready(selected_text, answer)
        )
        worker.answer_unavailable.connect(
            lambda reason: show_ai_unavailable_dialog(self, "Explain this passage", reason)
        )
        self._explain_worker = worker
        worker.start()

    def _on_explain_answer_ready(self, passage: str, answer: str) -> None:
        if self._viewer_screen is not None:
            self._viewer_screen.show_explanation(passage, answer)

    def _on_summarize_selection_requested(self, selected_text: str) -> None:
        """Summarize one real passage the reader selected (Phase 13
        deferred scope, shipped later) - identical pre-flight/worker
        shape to `_on_explain_selection_requested`, only the worker
        mode and feature label differ."""
        if self._viewer_screen is None or self._ai_panel is None:
            return
        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        provider_label = AI_AGENT_PROVIDER_LABELS.get(provider_code, provider_code)
        enabled = bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))
        if not enabled:
            show_ai_unavailable_dialog(
                self, "Summarize this passage", "AI Agent is not enabled in Settings."
            )
            return
        if not resolve_ai_agent_api_key(self._settings, provider_code):
            show_ai_unavailable_dialog(
                self, "Summarize this passage", f"No API key is set for {provider_label}."
            )
            return

        worker = AiAgentWorker(
            self._ai_panel.get_or_build_ai_agent_service, selected_text, "summarize_passage", self
        )
        worker.answer_ready.connect(
            lambda answer, _tool_calls: self._on_summarize_answer_ready(selected_text, answer)
        )
        worker.answer_unavailable.connect(
            lambda reason: show_ai_unavailable_dialog(self, "Summarize this passage", reason)
        )
        self._summarize_passage_worker = worker
        worker.start()

    def _on_summarize_answer_ready(self, passage: str, answer: str) -> None:
        if self._viewer_screen is not None:
            self._viewer_screen.show_summary(passage, answer)

    def _on_compare_selection_requested(self, selected_text: str) -> None:
        """Compare one real passage the reader selected against other
        real scholarly discussion elsewhere in the library (Phase 13
        deferred scope, shipped later) - identical pre-flight/worker
        shape to `_on_explain_selection_requested`, only the worker
        mode and feature label differ."""
        if self._viewer_screen is None or self._ai_panel is None:
            return
        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        provider_label = AI_AGENT_PROVIDER_LABELS.get(provider_code, provider_code)
        enabled = bool(self._settings.value(AI_AGENT_ENABLED_KEY, False, type=bool))
        if not enabled:
            show_ai_unavailable_dialog(
                self, "Compare this passage", "AI Agent is not enabled in Settings."
            )
            return
        if not resolve_ai_agent_api_key(self._settings, provider_code):
            show_ai_unavailable_dialog(
                self, "Compare this passage", f"No API key is set for {provider_label}."
            )
            return

        worker = AiAgentWorker(
            self._ai_panel.get_or_build_ai_agent_service, selected_text, "compare_passage", self
        )
        worker.answer_ready.connect(
            lambda answer, _tool_calls: self._on_compare_answer_ready(selected_text, answer)
        )
        worker.answer_unavailable.connect(
            lambda reason: show_ai_unavailable_dialog(self, "Compare this passage", reason)
        )
        self._compare_passage_worker = worker
        worker.start()

    def _on_compare_answer_ready(self, passage: str, answer: str) -> None:
        if self._viewer_screen is not None:
            self._viewer_screen.show_comparison(passage, answer)

    def _on_ai_quick_ask_requested(self, question: str) -> None:
        """A real question asked from the Search screen's empty detail
        pane - expand the real AI panel (if currently collapsed) and ask
        it there, reusing its own lazy-build/pre-flight/worker logic
        rather than duplicating it in a second, narrower box."""
        if self._ai_panel is None:
            return
        if self._ai_panel.is_collapsed:
            self._ai_panel.set_collapsed(False)
        self._ai_panel.ask(question)

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
