"""Viewer screen: read one book's pages in-app, with page navigation."""

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.application.page_narration import PageNarrationService
from islamic_research_hub.domain.models.book import Chapter
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.interfaces.desktop_app.animations import animate_splitter_size
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.panel_toggle import PanelToggle
from islamic_research_hub.interfaces.desktop_app.reading_fonts import (
    DEFAULT_FONT_CHOICE,
    FONT_CHOICES,
    resolve_installed_font_family,
)
from islamic_research_hub.interfaces.desktop_app.theme import (
    MUTED_LABEL_STYLE,
    RTL_TEXT_STYLE,
    Spacing,
    Type,
)
from islamic_research_hub.interfaces.desktop_app.tts_worker import TtsWorker
from islamic_research_hub.research_notes.docx_writer import LocalDocxStorage
from islamic_research_hub.research_notes.notes_dialog import (
    open_current_notes,
    show_save_to_notes_dialog,
)
from islamic_research_hub.research_notes.research_notes_manager import ResearchNotesManager
from islamic_research_hub.shared.citation_formatting import format_citation
from islamic_research_hub.shared.html_text_extraction import strip_html_to_text

LOGGER = logging.getLogger(__name__)

MIN_FONT_PX = 13
MAX_FONT_PX = 30
DEFAULT_FONT_PX = 19
FONT_STEP_PX = 1.5
MAX_READING_COLUMN_WIDTH = 820
"""Caps reading-content width to a real typeset column (Acrobat/Zotero
convention) instead of text filling the whole width of a wide monitor."""
NAV_PANEL_WIDTH = 240


class ViewerScreen(QWidget):
    """Show one book's pages, one at a time, with prev/next/jump navigation."""

    bookmark_toggled = Signal(int, int, bool)  # book_id, page_number, is_now_bookmarked
    pdf_fallback_requested = Signal()

    def __init__(
        self,
        database_path: Path,
        browser: BookBrowserRepository | None = None,
        initial_font_px: float | None = None,
        initial_font_family: str | None = None,
        enable_lazy_tts: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._browser = browser or BookBrowserRepository(database_path)
        self._pages: tuple = ()
        self._current_index = 0
        self._font_px = initial_font_px or DEFAULT_FONT_PX
        self._font_family = initial_font_family or DEFAULT_FONT_CHOICE
        self._current_book_id: int | None = None
        self._current_title: str | None = None
        self._current_volume_number: int | None = None
        self._current_language: str | None = None
        self._bookmarked_pages: set[int] = set()
        self._nav_panel_animation = None

        # Text-to-speech: same lazy-build-at-most-once-behind-a-lock pattern
        # as SearchScreen's semantic search (see `_get_or_build_tts_narration_service`).
        self._enable_lazy_tts = enable_lazy_tts
        self._tts_lock = threading.Lock()
        self._tts_narration_service: PageNarrationService | None = None
        self._tts_attempted = False
        self._tts_worker: TtsWorker | None = None
        self._tts_wav_path: str | None = None
        self._media_player = QMediaPlayer(self)
        self._tts_audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._tts_audio_output)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._empty_label = EmptyStateLabel(
            "Open a book from Search to read it here.", centered=True
        )
        layout.addWidget(self._empty_label)

        self._reader = QWidget()
        self._reader.setVisible(False)
        reader_layout = QVBoxLayout(self._reader)
        reader_layout.setContentsMargins(0, 0, 0, 0)
        reader_layout.setSpacing(0)

        header = QVBoxLayout()
        header.setContentsMargins(16, 12, 16, 4)
        self._title_label = QLabel()
        self._title_label.setStyleSheet(f"font-size: 16px; font-weight: 700; {RTL_TEXT_STYLE}")
        self._title_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._author_label = QLabel()
        self._author_label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.BODY_SM}px;")
        self._author_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        header.addWidget(self._title_label)
        header.addWidget(self._author_label)
        reader_layout.addLayout(header)

        self._pdf_fallback_banner = QWidget()
        self._pdf_fallback_banner.setVisible(False)
        banner_layout = QHBoxLayout(self._pdf_fallback_banner)
        banner_layout.setContentsMargins(16, 0, 16, 8)
        banner_label = QLabel(
            "This book's digitized text may be limited to headings - a scanned PDF is available."
        )
        banner_label.setStyleSheet(MUTED_LABEL_STYLE)
        banner_label.setWordWrap(True)
        banner_layout.addWidget(banner_label, stretch=1)
        pdf_fallback_button = QPushButton("Open scanned PDF")
        pdf_fallback_button.setIcon(button_icon("open-pdf"))
        pdf_fallback_button.setIconSize(button_icon_size())
        pdf_fallback_button.clicked.connect(self.pdf_fallback_requested)
        banner_layout.addWidget(pdf_fallback_button)
        reader_layout.addWidget(self._pdf_fallback_banner)

        # Real fix: this toolbar's widgets measured a real ~1024px combined
        # minimum width, on its own already 3x the reader segment's real
        # 320px floor - the direct cause of buttons rendering as clipped,
        # unreadable fragments whenever the reader wasn't given a very
        # wide share of the window. Icon-bearing actions drop their text
        # label (icon + tooltip only, the standard reader-toolbar pattern
        # in Acrobat/Zotero); the remaining wide controls get the same
        # Ignored size policy already proven safe elsewhere in this pass.
        toolbar_container = QWidget()
        toolbar = QHBoxLayout(toolbar_container)
        toolbar.setContentsMargins(16, 4, 16, 8)
        self._contents_button = QPushButton("Contents")
        self._contents_button.setCheckable(True)
        self._contents_button.setChecked(True)
        self._contents_button.setToolTip("Show/hide this book's table of contents and bookmarks.")
        self._contents_button.toggled.connect(self._on_contents_toggled)
        toolbar.addWidget(self._contents_button)

        self._nav_maximize_button = QPushButton()
        self._nav_maximize_button.setIcon(button_icon("maximize"))
        self._nav_maximize_button.setIconSize(button_icon_size())
        self._nav_maximize_button.setToolTip("Maximize the contents/bookmarks panel")
        self._nav_maximize_button.clicked.connect(self._on_nav_maximize_clicked)
        toolbar.addWidget(self._nav_maximize_button)
        toolbar.addWidget(_toolbar_separator())

        self._prev_button = QPushButton()
        self._prev_button.setIcon(button_icon("prev"))
        self._prev_button.setIconSize(button_icon_size())
        self._prev_button.setToolTip("Previous page")
        self._prev_button.clicked.connect(self._go_previous)
        toolbar.addWidget(self._prev_button)

        self._page_input = QLineEdit()
        self._page_input.setFixedWidth(50)
        self._page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_input.returnPressed.connect(self._jump_to_entered_page)
        toolbar.addWidget(self._page_input)

        self._page_count_label = QLabel()
        toolbar.addWidget(self._page_count_label)

        self._next_button = QPushButton()
        self._next_button.setIcon(button_icon("next"))
        self._next_button.setIconSize(button_icon_size())
        self._next_button.setToolTip("Next page")
        self._next_button.clicked.connect(self._go_next)
        toolbar.addWidget(self._next_button)

        toolbar.addStretch(1)

        self._bookmark_button = QPushButton()
        self._bookmark_button.setIcon(button_icon("bookmark"))
        self._bookmark_button.setIconSize(button_icon_size())
        self._bookmark_button.setToolTip("Bookmark this page")
        self._bookmark_button.clicked.connect(self.toggle_bookmark)
        toolbar.addWidget(self._bookmark_button)

        self._play_pause_button = QPushButton()
        self._play_pause_button.setIcon(button_icon("play"))
        self._play_pause_button.setIconSize(button_icon_size())
        self._play_pause_button.setToolTip("Read this page aloud")
        # Visible only when TTS is actually enabled (Settings toggle, wired
        # via MainWindow) - a dead button offering a feature the user turned
        # off (or a test double never enabled) is worse than no button.
        # Once visible, a real build *failure* (missing optional dependency,
        # model load error) disables rather than hides it - same
        # degrade-gracefully-but-stay-visible philosophy SearchScreen's
        # semantic search panel already uses.
        self._play_pause_button.setVisible(self._enable_lazy_tts)
        self._play_pause_button.clicked.connect(self._on_play_pause_clicked)
        toolbar.addWidget(self._play_pause_button)
        toolbar.addWidget(_toolbar_separator())

        self._copy_citation_button = QPushButton("Copy citation")
        self._copy_citation_button.setToolTip(
            "Copy a citation for the current page to the clipboard."
        )
        self._copy_citation_button.clicked.connect(self.copy_citation)
        toolbar.addWidget(self._copy_citation_button)
        toolbar.addWidget(_toolbar_separator())

        self._font_family_combo = QComboBox()
        for display_name, _font_stack in FONT_CHOICES:
            self._font_family_combo.addItem(display_name)
        initial_index = self._font_family_combo.findText(self._font_family)
        self._font_family_combo.setCurrentIndex(max(initial_index, 0))
        self._font_family_combo.currentTextChanged.connect(self._change_font_family)
        toolbar.addWidget(self._font_family_combo)

        smaller_button = QPushButton("A-")
        smaller_button.setFixedWidth(32)
        smaller_button.clicked.connect(lambda: self._change_font_size(-FONT_STEP_PX))
        toolbar.addWidget(smaller_button)

        larger_button = QPushButton("A+")
        larger_button.setFixedWidth(32)
        larger_button.clicked.connect(lambda: self._change_font_size(FONT_STEP_PX))
        toolbar.addWidget(larger_button)

        # Real bug fixed here: this toolbar's own natural width (~1024px,
        # see the comment above) already exceeds the reader pane's real
        # floor (320px) - previously, widgets marked `Ignored` (the font
        # combo, Contents/Copy Citation buttons) were squeezed toward
        # zero width under real space pressure instead of just not
        # dictating the container's minimum size, which read as those
        # controls vanishing entirely, not shrinking. Wrapping the whole
        # toolbar in its own horizontal-scrolling area means every
        # control keeps its real, full, readable size - narrow windows
        # get a scrollbar instead of missing controls.
        toolbar_scroll = QScrollArea()
        toolbar_scroll.setWidget(toolbar_container)
        toolbar_scroll.setWidgetResizable(True)
        toolbar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        toolbar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        toolbar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        toolbar_scroll.setFixedHeight(toolbar_container.sizeHint().height())
        reader_layout.addWidget(toolbar_scroll)

        self._body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.addWidget(self._build_nav_panel())

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._content_label = QLabel()
        self._content_label.setWordWrap(True)
        self._content_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._content_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._content_label.setMaximumWidth(MAX_READING_COLUMN_WIDTH)
        self._content_label.setStyleSheet(f"padding: 16px 24px; {RTL_TEXT_STYLE}")
        self._content_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._content_label.customContextMenuRequested.connect(self._show_content_context_menu)
        scroll_area.setWidget(self._content_label)
        self._body_splitter.addWidget(scroll_area)
        self._body_splitter.setStretchFactor(0, 0)
        self._body_splitter.setStretchFactor(1, 1)
        self._body_splitter.setCollapsible(1, False)
        self._body_splitter.setSizes([NAV_PANEL_WIDTH, 1])
        reader_layout.addWidget(self._body_splitter, stretch=1)
        self._nav_panel_toggle = PanelToggle(self._body_splitter, index=0, expanded_width=NAV_PANEL_WIDTH)

        layout.addWidget(self._reader, stretch=1)
        self._apply_font_size()

    def _build_nav_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("searchLeftPane")
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(360)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(Spacing.SM, Spacing.SM, Spacing.SM, Spacing.SM)
        layout.setSpacing(Spacing.XS)

        contents_label = QLabel("Contents")
        contents_label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-weight: 600;")
        layout.addWidget(contents_label)
        self._toc_tree = QTreeWidget()
        self._toc_tree.setHeaderHidden(True)
        # Typography fix: real Arabic/Urdu chapter titles need RTL layout
        # direction, matching search_screen.py's category tree.
        self._toc_tree.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._toc_tree.itemClicked.connect(self._on_toc_item_clicked)
        layout.addWidget(self._toc_tree, stretch=2)

        bookmarks_label = QLabel("Bookmarks")
        bookmarks_label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-weight: 600;")
        layout.addWidget(bookmarks_label)
        self._bookmarks_list = QListWidget()
        self._bookmarks_list.itemClicked.connect(self._on_bookmark_item_clicked)
        layout.addWidget(self._bookmarks_list, stretch=1)

        research_notes_label = QLabel("Research Notes")
        research_notes_label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-weight: 600;")
        layout.addWidget(research_notes_label)
        self._research_notes_list = QListWidget()
        self._research_notes_list.setToolTip("Documents with a quotation saved from this book")
        self._research_notes_list.itemClicked.connect(self._on_research_notes_item_clicked)
        layout.addWidget(self._research_notes_list, stretch=1)

        return panel

    def _on_contents_toggled(self, checked: bool) -> None:
        target = NAV_PANEL_WIDTH if checked else 0
        self._nav_panel_animation = animate_splitter_size(self._body_splitter, index=0, end=target)

    def _on_nav_maximize_clicked(self) -> None:
        """Maximize/restore the contents/bookmarks panel - if it's
        currently collapsed, expand it first so maximizing always shows
        something real rather than a maximized-but-invisible panel."""
        if not self._contents_button.isChecked():
            self._contents_button.setChecked(True)
        self._nav_panel_toggle.toggle_maximized()
        self._nav_maximize_button.setIcon(
            button_icon("restore" if self._nav_panel_toggle.is_maximized else "maximize")
        )

    def _on_toc_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        page_number = item.data(0, Qt.ItemDataRole.UserRole)
        if page_number is not None:
            self.jump_to_page_number(page_number)

    def _on_bookmark_item_clicked(self, item: QListWidgetItem) -> None:
        page_number = item.data(Qt.ItemDataRole.UserRole)
        if page_number is not None:
            self.jump_to_page_number(page_number)

    def _on_research_notes_item_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _reload_toc(self, book_id: int) -> None:
        self._toc_tree.clear()
        chapters = self._browser.list_chapters(book_id)
        if not chapters:
            # Real empty state instead of a blank white box - a book with
            # no digitized table of contents is a real, common case, not
            # an error.
            self._toc_tree.addTopLevelItem(
                QTreeWidgetItem(["No table of contents available."])
            )
            return
        for chapter in chapters:
            self._toc_tree.addTopLevelItem(_chapter_tree_item(chapter))

    def _reload_bookmarks_list(self) -> None:
        self._bookmarks_list.clear()
        if not self._bookmarked_pages:
            self._bookmarks_list.addItem(
                "No bookmarks yet - bookmark a page to see it here."
            )
            return
        title = self._current_title or "(untitled)"
        for page_number in sorted(self._bookmarked_pages):
            # Full details, not just "Page N" - the same title/volume
            # every row shares today (bookmarks are per-currently-open-
            # book), but real and complete rather than context-free.
            if self._current_volume_number is not None:
                text = f"{title}, Volume {self._current_volume_number}, Page {page_number}"
            else:
                text = f"{title}, Page {page_number}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, page_number)
            self._bookmarks_list.addItem(item)

    def _reload_research_notes_list(self) -> None:
        """List every real Research Notes document with a quotation saved
        from the currently open book - lets the reader jump straight to
        prior notes on this book, not just bookmarks."""
        self._research_notes_list.clear()
        if self._current_title is None:
            return
        try:
            documents = self._build_research_notes_manager().find_documents_mentioning_book(
                self._current_title
            )
        except Exception:
            LOGGER.exception("Could not check for Research Notes documents.")
            return
        if not documents:
            self._research_notes_list.addItem("No research notes for this book yet.")
            return
        for path in documents:
            item = QListWidgetItem(path.stem)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self._research_notes_list.addItem(item)

    def _build_research_notes_manager(self) -> ResearchNotesManager:
        """Test-friendly seam - widget tests monkeypatch this instead of
        touching the real Documents folder/registry (mirrors this
        codebase's other `_build_real_*_service` seams)."""
        return ResearchNotesManager(LocalDocxStorage())

    def copy_citation(self) -> None:
        """Copy a real citation for the current page to the clipboard.

        Uses `format_citation()` (already built, unrelated feature) with
        whatever's already loaded - title, volume number, and the real
        current page. Paragraph index defaults to 1 (true for the
        overwhelming majority of pages - most pages have exactly one
        real paragraph, per the Paragraphs backfill's own data), since
        the reader has no paragraph-level cursor to know a more precise
        one.
        """
        page_number = self.current_page_number()
        if self._current_title is None or page_number is None:
            return
        citation = format_citation(
            self._current_title,
            page_number,
            paragraph_index=1,
            volume_number=self._current_volume_number,
        )
        QGuiApplication.clipboard().setText(citation)

    def _show_content_context_menu(self, position) -> None:
        selected_text = self._content_label.selectedText()
        menu = QMenu(self)
        actions = {
            "copy": menu.addAction("Copy"),
            "copy_citation": menu.addAction("Copy with Citation"),
            "save_notes": menu.addAction("Save to Research Notes"),
        }
        for action in actions.values():
            action.setEnabled(bool(selected_text))
        menu.addSeparator()
        actions["open_notes"] = menu.addAction("Open Current Notes")

        chosen = menu.exec(self._content_label.mapToGlobal(position))
        for name, action in actions.items():
            if chosen is action:
                self._handle_context_menu_action(name, selected_text)
                return

    def _handle_context_menu_action(self, action: str, selected_text: str) -> None:
        """Directly-callable, test-friendly seam - a real QMenu popup has
        no place in a headless test (mirrors search_screen.py's
        `_on_recording_captured`), so tests call this with a synthetic
        action name instead of driving a real popup menu."""
        if action == "copy":
            QGuiApplication.clipboard().setText(selected_text)
        elif action == "copy_citation":
            self._copy_selection_with_citation(selected_text)
        elif action == "save_notes":
            self._save_selection_to_research_notes(selected_text)
        elif action == "open_notes":
            open_current_notes(self)

    def _copy_selection_with_citation(self, selected_text: str) -> None:
        page_number = self.current_page_number()
        if self._current_title is None or page_number is None:
            return
        citation = format_citation(
            self._current_title,
            page_number,
            paragraph_index=1,
            volume_number=self._current_volume_number,
        )
        QGuiApplication.clipboard().setText(f"{selected_text}\n\n{citation}")

    def _save_selection_to_research_notes(self, selected_text: str) -> None:
        page_number = self.current_page_number()
        if self._current_book_id is None or self._current_title is None or page_number is None:
            return
        show_save_to_notes_dialog(
            self,
            self._browser,
            self._current_book_id,
            self._current_title,
            page_number,
            selected_text,
        )

    def load_book(self, book_id: int, bookmarked_pages: set[int] | None = None) -> bool:
        """Load one book's pages into the viewer. Returns False if not found."""
        detail = self._browser.get_book_detail(book_id)
        if detail is None:
            return False
        title, author, pages = detail
        metadata = self._browser.get_book_metadata(book_id)
        self._pages = pages
        self._current_index = 0
        self._current_book_id = book_id
        self._current_title = title
        self._current_volume_number = metadata.volume_number if metadata else None
        self._current_language = metadata.language if metadata else None
        self._bookmarked_pages = set(bookmarked_pages or ())
        self._title_label.setText(title or "(untitled)")
        self._author_label.setText(author or "Unknown author")
        self._empty_label.setVisible(False)
        self._reader.setVisible(True)
        self._pdf_fallback_banner.setVisible(False)
        self._reload_toc(book_id)
        self._reload_bookmarks_list()
        self._reload_research_notes_list()
        self._render_current_page()
        return True

    def set_pdf_fallback_available(self, available: bool) -> None:
        """Show or hide the "a scanned PDF may be available" banner for the loaded book."""
        self._pdf_fallback_banner.setVisible(available)

    def jump_to_page_number(self, page_number: int) -> None:
        """Jump directly to a specific page number, if it exists among the loaded pages."""
        for index, page in enumerate(self._pages):
            if page.page_number == page_number:
                self._current_index = index
                self._render_current_page()
                return

    def _go_previous(self) -> None:
        if self._current_index > 0:
            self._current_index -= 1
            self._render_current_page()

    def _go_next(self) -> None:
        if self._current_index < len(self._pages) - 1:
            self._current_index += 1
            self._render_current_page()

    def _jump_to_entered_page(self) -> None:
        text = self._page_input.text().strip()
        if text.isdigit():
            target = int(text) - 1
            if 0 <= target < len(self._pages):
                self._current_index = target
                self._render_current_page()

    def _change_font_size(self, delta: float) -> None:
        self._font_px = max(MIN_FONT_PX, min(MAX_FONT_PX, self._font_px + delta))
        self._apply_font_size()

    def _change_font_family(self, display_name: str) -> None:
        self._font_family = display_name
        self._apply_font_size()

    def _apply_font_size(self) -> None:
        font_stack = _font_stack_for(self._font_family)
        resolved_family = resolve_installed_font_family(font_stack)
        self._content_label.setStyleSheet(
            f"padding: 16px 24px; font-size: {self._font_px}px; line-height: 160%; "
            f"font-family: '{resolved_family}';"
        )

    def selected_font_family(self) -> str:
        """Return the currently selected reading font's display name."""
        return self._font_family

    def has_content(self) -> bool:
        """Return whether the loaded book has any real extracted page text.

        `load_book()` returns True as soon as a matching `Books` row
        exists, even for the ~9,172 real PDF-only books with `PageCount=0`
        (no OCR has been run on them) - this is the real signal callers
        need to decide whether to fall back to `PdfViewerScreen` instead.
        """
        return len(self._pages) > 0

    def current_page_number(self) -> int | None:
        """Return the real page number currently shown, or None if nothing is loaded."""
        if not self._pages:
            return None
        return self._pages[self._current_index].page_number

    def current_book_id(self) -> int | None:
        """Return the book id of the currently loaded book, if any."""
        return self._current_book_id

    def toggle_bookmark(self) -> None:
        """Toggle the bookmark on the current page (also reachable via Ctrl+B)."""
        page_number = self.current_page_number()
        if self._current_book_id is None or page_number is None:
            return
        now_bookmarked = page_number not in self._bookmarked_pages
        if now_bookmarked:
            self._bookmarked_pages.add(page_number)
        else:
            self._bookmarked_pages.discard(page_number)
        self._update_bookmark_button()
        self._reload_bookmarks_list()
        self.bookmark_toggled.emit(self._current_book_id, page_number, now_bookmarked)

    def _update_bookmark_button(self) -> None:
        page_number = self.current_page_number()
        is_bookmarked = page_number is not None and page_number in self._bookmarked_pages
        self._bookmark_button.setText(
            "★ Bookmarked" if is_bookmarked else "Bookmark this page"
        )

    def _render_current_page(self) -> None:
        self._stop_narration()
        if not self._pages:
            return
        page = self._pages[self._current_index]
        # Real bug reported directly against the running app: ~471,000
        # real pages (mostly Maktaba Jibreel) carry raw structural markup
        # (`<urh1>...</urh1>`) that was already being stripped for
        # narration (PageNarrationService.narrate()) but never for the
        # on-screen text itself - the same shared strip_html_to_text()
        # applies here now, so headings render as plain text instead of
        # literal tags.
        self._content_label.setText(strip_html_to_text(page.content_f) or "(no content)")
        self._page_input.setText(str(self._current_index + 1))
        self._page_count_label.setText(f"/ {len(self._pages)}")
        self._prev_button.setEnabled(self._current_index > 0)
        self._next_button.setEnabled(self._current_index < len(self._pages) - 1)
        self._update_bookmark_button()

    def _current_narration_key(self) -> tuple[int | None, int | None]:
        return (self._current_book_id, self.current_page_number())

    def _on_play_pause_clicked(self) -> None:
        state = self._media_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._media_player.pause()
            self._play_pause_button.setIcon(button_icon("play"))
            return
        if (
            state == QMediaPlayer.PlaybackState.PausedState
            and self._media_player.source().isValid()
        ):
            self._media_player.play()
            self._play_pause_button.setIcon(button_icon("pause"))
            return
        self._start_narration()

    def _start_narration(self) -> None:
        if not self._pages:
            return
        page = self._pages[self._current_index]
        if not page.content_f:
            return
        self._play_pause_button.setEnabled(False)
        worker = TtsWorker(
            self._get_or_build_tts_narration_service,
            page.content_f,
            self._current_language,
            self._current_narration_key(),
            self,
        )
        worker.narration_ready.connect(self._on_narration_ready)
        worker.narration_failed.connect(self._on_narration_failed)
        self._tts_worker = worker
        worker.start()

    def _get_or_build_tts_narration_service(self) -> PageNarrationService | None:
        """Return the cached narration service, building it at most once.

        Runs on the worker thread - guarded by a lock so two overlapping
        Play clicks can't both attempt the (real, ~1s+) model load at once.
        Mirrors `SearchScreen._get_or_build_semantic_service` exactly.
        """
        with self._tts_lock:
            if self._tts_narration_service is None and self._enable_lazy_tts:
                if not self._tts_attempted:
                    self._tts_attempted = True
                    self._tts_narration_service = self._build_real_tts_narration_service()
            return self._tts_narration_service

    def _build_real_tts_narration_service(self) -> PageNarrationService | None:
        """Build the real local MMS-TTS narration service, or None on any failure.

        Failure is expected and normal here - the optional "tts" extra
        (`transformers`/`torch`/`scipy`) may not be installed, or model
        loading may fail for other reasons. Either way, reading/navigation
        must keep working unaffected.
        """
        try:
            from islamic_research_hub.infrastructure.ai.mms_tts_speaker import MmsTtsSpeaker

            return PageNarrationService(MmsTtsSpeaker())
        except Exception:
            LOGGER.exception("Text-to-speech unavailable.")
            return None

    def _on_narration_ready(self, wav_path: str, request_key: object) -> None:
        self._play_pause_button.setEnabled(True)
        if request_key != self._current_narration_key():
            Path(wav_path).unlink(missing_ok=True)  # stale - page changed while synthesizing
            return
        self._cleanup_narration_file()
        self._tts_wav_path = wav_path
        self._media_player.setSource(QUrl.fromLocalFile(wav_path))
        self._media_player.play()
        self._play_pause_button.setIcon(button_icon("pause"))

    def _on_narration_failed(self, request_key: object) -> None:
        self._play_pause_button.setEnabled(True)
        if request_key != self._current_narration_key():
            return
        self._play_pause_button.setIcon(button_icon("play"))
        self._play_pause_button.setToolTip("Text-to-speech unavailable")

    def _stop_narration(self) -> None:
        self._media_player.stop()
        # Real bug found writing this feature's own tests: on Windows,
        # QMediaPlayer.stop() does not synchronously release its lock on the
        # source file - deleting the temp WAV immediately afterward raised a
        # real PermissionError, which would have crashed page navigation
        # (_go_next/_go_previous both funnel through this). Clearing the
        # source explicitly is what actually releases the file handle.
        self._media_player.setSource(QUrl())
        self._cleanup_narration_file()
        self._play_pause_button.setIcon(button_icon("play"))

    def _cleanup_narration_file(self) -> None:
        if self._tts_wav_path is not None:
            path, self._tts_wav_path = self._tts_wav_path, None
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                # Still locked despite clearing the source (a delayed OS
                # release) - a lingering temp file is a far better failure
                # mode than crashing real page navigation over cleanup.
                LOGGER.warning("Could not delete temporary narration file: %s", path)


def _toolbar_separator() -> QFrame:
    """A thin vertical divider - groups the reader toolbar's controls
    (navigation / bookmark+narration / citation / font) instead of one
    long undifferentiated row of equal-weight buttons."""
    line = QFrame()
    line.setFrameShape(QFrame.Shape.VLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def _font_stack_for(display_name: str) -> str:
    """Return the CSS-style font-family fallback chain for a chosen font's display name."""
    for name, font_stack in FONT_CHOICES:
        if name == display_name:
            return font_stack
    return FONT_CHOICES[0][1]


def _chapter_tree_item(chapter: Chapter) -> QTreeWidgetItem:
    item = QTreeWidgetItem([chapter.title or "(untitled)"])
    item.setData(0, Qt.ItemDataRole.UserRole, chapter.page_number)
    for child in chapter.children:
        item.addChild(_chapter_tree_item(child))
    return item
