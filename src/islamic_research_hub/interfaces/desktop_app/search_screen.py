"""Search screen: category/author browsing, query+filters+results, an inline detail panel."""

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QIODevice, QObject, QSettings, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeyEvent
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.pdf_source_resolver import resolve_pdf_path
from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.application.voice_transcription import VoiceSearchService
from islamic_research_hub.domain.models.book_metadata import BookMetadata
from islamic_research_hub.domain.models.book_summary import BookSummary
from islamic_research_hub.domain.models.category_node import CategoryNode
from islamic_research_hub.domain.models.search_result import SearchResult
from islamic_research_hub.domain.models.semantic_search_result import SemanticSearchResult
from islamic_research_hub.infrastructure.audio.pcm_conversion import pcm16_bytes_to_samples
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    MAX_BROWSE_RESULTS,
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.book_rating_repository import (
    BookRatingRepository,
)
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (
    RecentBookRepository,
)
from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
    BookSearchError,
    SqliteBookSearchRepository,
)
from islamic_research_hub.interfaces.desktop_app.animations import animate_splitter_size
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.i18n import (
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
)
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.list_row_button import list_row_button
from islamic_research_hub.interfaces.desktop_app.panel_toggle import PanelToggle
from islamic_research_hub.interfaces.desktop_app.search_history import RecentSearchStore
from islamic_research_hub.interfaces.desktop_app.semantic_search_worker import (
    SemanticSearchWorker,
)
from islamic_research_hub.interfaces.desktop_app.theme import (
    DANGER,
    MUTED_LABEL_STYLE,
    RTL_TEXT_STYLE,
    SURFACE_RAISED,
    Spacing,
    Type,
)
from islamic_research_hub.interfaces.desktop_app.voice_search_worker import VoiceSearchWorker
from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text
from islamic_research_hub.shared.citation_formatting import format_citation
from islamic_research_hub.shared.excerpt_highlighting import highlight_excerpt_html

LOGGER = logging.getLogger(__name__)

DEFAULT_LIMIT = 30
ALL_LIBRARIES_LABEL = "All libraries"
LEFT_PANE_WIDTH = 230
RIGHT_PANE_WIDTH = 220
"""UI Polish Pass 2: narrowed from 260 - the detail panel's real content
(a handful of label/value rows, a rating dropdown, 1-2 buttons) never
needed the extra width; freed space goes to the reader/results instead."""
VOICE_SEARCH_SAMPLE_RATE = 16000
"""Whisper's native rate - capturing directly at this rate avoids a
resampling step (see faster_whisper_transcriber.py)."""
MAX_RECORDING_MS = 12_000
"""A spoken search query placeholder ceiling - tuned against real spoken
queries during manual verification, not a hard product requirement."""
_EXCERPT_MAX_HEIGHT_PX = 40
"""Caps a result card's excerpt to ~2 lines (Type.BODY=13px x 150% line-height
x 2) - dense desktop result rows instead of unbounded, mobile-card-style growth."""


class SearchScreen(QWidget):
    """Browse categories/authors, search the master database, view a result's details."""

    open_in_viewer_requested = Signal(int, int)  # book_id, page_number

    def __init__(
        self,
        database_path: Path,
        maknoon_pdf_folder: Path,
        search_service: BookSearchService | None = None,
        browser: BookBrowserRepository | None = None,
        recent_books: RecentBookRepository | None = None,
        ratings: BookRatingRepository | None = None,
        semantic_search_service: SemanticBookSearchService | None = None,
        enable_lazy_semantic_search: bool = False,
        recent_search_store: RecentSearchStore | None = None,
        enable_lazy_voice_search: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._maknoon_pdf_folder = maknoon_pdf_folder
        self._search_service = search_service or BookSearchService(
            SqliteBookSearchRepository(database_path)
        )
        self._enable_lazy_semantic_search = enable_lazy_semantic_search
        self._semantic_search_lock = threading.Lock()
        self._semantic_worker: SemanticSearchWorker | None = None
        self._current_query = ""
        self._current_title_count = 0
        self._current_content_count = 0
        self._current_exclude_keys: set[tuple[int, int | None]] = set()
        self._semantic_search_attempted = False
        self._browser = browser or BookBrowserRepository(database_path)
        self._semantic_search_service = semantic_search_service
        self._recent_books = recent_books or RecentBookRepository(database_path)
        self._ratings = ratings or BookRatingRepository(database_path)
        self._recent_searches = recent_search_store or RecentSearchStore(
            QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        )
        self._selected_card_index = -1
        self._detail_panel_animation = None

        # Voice search: same lazy-build-at-most-once-behind-a-lock pattern
        # as semantic search / TTS (see `_get_or_build_voice_search_service`).
        self._enable_lazy_voice_search = enable_lazy_voice_search
        self._voice_search_lock = threading.Lock()
        self._voice_search_service: VoiceSearchService | None = None
        self._voice_search_attempted = False
        self._voice_worker: VoiceSearchWorker | None = None
        self._audio_source: QAudioSource | None = None
        self._audio_io_device: QIODevice | None = None
        self._audio_buffer = bytearray()
        self._max_record_timer = QTimer(self)
        self._max_record_timer.setSingleShot(True)
        self._max_record_timer.setInterval(MAX_RECORDING_MS)
        self._max_record_timer.timeout.connect(self._stop_recording)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # A QSplitter, not a plain QHBoxLayout, so the browse/detail panes are
        # user-resizable (and collapsible) instead of permanently fixed-width -
        # each pane's own internal content/scrolling is unchanged either way.
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._build_left_pane())
        self._splitter.addWidget(self._build_middle_pane())
        self._splitter.addWidget(self._build_right_pane())
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setStretchFactor(2, 0)
        self._splitter.setSizes([LEFT_PANE_WIDTH, 640, RIGHT_PANE_WIDTH])
        layout.addWidget(self._splitter)
        self._detail_panel_toggle = PanelToggle(self._splitter, index=2, expanded_width=RIGHT_PANE_WIDTH)
        self._install_search_completer()
        self._query_edit.installEventFilter(self)

    # ---------------------------------------------------------------- left

    def _build_left_pane(self) -> QWidget:
        # A plain (non-scrolling) fixed-width pane: the category tree and the
        # author list both scroll themselves internally (a QTreeWidget always
        # does; the author list is wrapped in its own QScrollArea below) - an
        # outer QScrollArea around the whole pane would fight that, since
        # QScrollArea gives its content exactly the height its sizeHint
        # wants, and a QTreeWidget's sizeHint wants to show every row at once.
        pane = QWidget()
        pane.setObjectName("searchLeftPane")
        pane.setMinimumWidth(180)
        # Responsive Desktop fix: no maximum was set, so a manually-dragged
        # splitter handle could let this nav pane crowd out the results
        # pane (the primary content) on a wide monitor - it holds a tree/
        # list, not primary content, so it's capped.
        pane.setMaximumWidth(420)
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.SM)
        layout.setSpacing(Spacing.XS)

        tab_row = QHBoxLayout()
        self._categories_tab_button = QPushButton("Categories")
        self._categories_tab_button.setCheckable(True)
        self._categories_tab_button.setChecked(True)
        self._categories_tab_button.setObjectName("navTab")
        self._categories_tab_button.clicked.connect(lambda: self._show_browse_tab(0))
        tab_row.addWidget(self._categories_tab_button)

        self._authors_tab_button = QPushButton("Authors")
        self._authors_tab_button.setCheckable(True)
        self._authors_tab_button.setObjectName("navTab")
        self._authors_tab_button.clicked.connect(lambda: self._show_browse_tab(1))
        tab_row.addWidget(self._authors_tab_button)

        self._recent_tab_button = QPushButton("Recent")
        self._recent_tab_button.setCheckable(True)
        self._recent_tab_button.setObjectName("navTab")
        self._recent_tab_button.clicked.connect(lambda: self._show_browse_tab(2))
        tab_row.addWidget(self._recent_tab_button)
        layout.addLayout(tab_row)

        # 691 real categories and 650 real authors are too many to scroll
        # through blindly - a live filter narrows either list as you type.
        self._browse_filter_edit = QLineEdit()
        self._browse_filter_edit.setPlaceholderText("Filter...")
        self._browse_filter_edit.textChanged.connect(self._apply_browse_filter)
        layout.addWidget(self._browse_filter_edit)

        self._browse_stack = QStackedWidget()
        self._category_tree = self._build_category_tree()
        self._browse_stack.addWidget(self._category_tree)
        self._author_list, self._author_row_buttons = self._build_author_list()
        self._browse_stack.addWidget(self._author_list)
        self._recent_list, self._recent_list_layout = self._build_recent_pane()
        self._browse_stack.addWidget(self._recent_list)
        layout.addWidget(self._browse_stack, stretch=1)

        layout.addWidget(_pane_title("Libraries"))
        self._library_chip_layout = QVBoxLayout()
        self._library_chip_layout.setSpacing(4)
        self._rebuild_library_chips()
        layout.addLayout(self._library_chip_layout)

        return pane

    def _build_category_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        for node in self._browser.get_category_tree():
            tree.addTopLevelItem(_category_tree_item(node))
        tree.itemClicked.connect(self._on_category_clicked)
        return tree

    def _build_author_list(self) -> tuple[QScrollArea, list[tuple[str, QPushButton]]]:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        row_buttons: list[tuple[str, QPushButton]] = []
        for name, count in self._browser.list_authors_with_counts():
            button = list_row_button(f"{name}  ({count})", object_name="authorRow")
            button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            button.clicked.connect(lambda _checked, n=name: self._filter_by_author(n))
            layout.addWidget(button)
            row_buttons.append((name, button))
        layout.addStretch(1)

        scroll_area.setWidget(container)
        return scroll_area, row_buttons

    def _build_recent_pane(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)
        scroll_area.setWidget(container)
        return scroll_area, layout

    def _refresh_recent_list(self) -> None:
        """Rebuild the Recent tab from the real recently-opened-books list.

        Queried fresh each time the tab is shown (rather than kept in sync
        via a signal) since it's cheap and only needs to be current at the
        moment the user looks at it.
        """
        while self._recent_list_layout.count():
            item = self._recent_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        recent = self._recent_books.list_recent()
        if not recent:
            empty_label = EmptyStateLabel("No recently opened books yet - search for one below.")
            self._recent_list_layout.addWidget(empty_label)
        else:
            for summary in recent:
                button = list_row_button(
                    f"{summary.title}  ({summary.author or 'Unknown author'})",
                    object_name="authorRow",
                )
                button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
                last_page = self._recent_books.last_page_number(summary.book_id) or 1
                button.clicked.connect(
                    lambda _checked, bid=summary.book_id, page=last_page: (
                        self.open_in_viewer_requested.emit(bid, page)
                    )
                )
                self._recent_list_layout.addWidget(button)
        self._recent_list_layout.addStretch(1)

    def _rebuild_library_chips(self) -> None:
        while self._library_chip_layout.count():
            item = self._library_chip_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        all_chip = list_row_button(
            f"{ALL_LIBRARIES_LABEL}  ({self._browser.get_header_stats().book_count})",
            object_name="libraryChip",
        )
        all_chip.clicked.connect(lambda: self._filter_by_library(ALL_LIBRARIES_LABEL))
        self._library_chip_layout.addWidget(all_chip)
        for name, count in self._browser.list_libraries_with_counts():
            chip = list_row_button(f"{name}  ({count})", object_name="libraryChip")
            chip.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            chip.clicked.connect(lambda _checked, n=name: self._filter_by_library(n))
            self._library_chip_layout.addWidget(chip)

    def _show_browse_tab(self, index: int) -> None:
        self._browse_stack.setCurrentIndex(index)
        self._categories_tab_button.setChecked(index == 0)
        self._authors_tab_button.setChecked(index == 1)
        self._recent_tab_button.setChecked(index == 2)
        self._browse_filter_edit.clear()
        self._browse_filter_edit.setEnabled(index != 2)
        if index == 2:
            self._refresh_recent_list()

    def _apply_browse_filter(self, text: str) -> None:
        """Narrow whichever browse list (categories or authors) is currently shown.

        The Recent tab isn't filterable - it's capped at
        `RecentBookRepository.MAX_RECENT_BOOKS` (20) real books, short
        enough that a filter box adds no value.
        """
        needle = (normalize_search_text(text.strip()) or "").casefold()
        if self._browse_stack.currentIndex() == 0:
            root = self._category_tree.invisibleRootItem()
            for index in range(root.childCount()):
                self._filter_category_item(root.child(index), needle)
        elif self._browse_stack.currentIndex() == 1:
            for name, button in self._author_row_buttons:
                button.setVisible(needle in (normalize_search_text(name) or "").casefold())

    def _filter_category_item(self, item: QTreeWidgetItem, needle: str) -> bool:
        """Hide a category node unless it or a real descendant matches; return match state."""
        own_name = normalize_search_text(item.data(0, Qt.ItemDataRole.UserRole) or "") or ""
        self_matches = needle in own_name.casefold()
        child_matches = False
        for index in range(item.childCount()):
            if self._filter_category_item(item.child(index), needle):
                child_matches = True
        visible = not needle or self_matches or child_matches
        item.setHidden(not visible)
        if child_matches and needle:
            item.setExpanded(True)
        return visible

    def _on_category_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if not name:
            return
        self._category_edit.setText(name)
        if self._query_edit.text().strip():
            self._run_search()
        else:
            self._browse(self._browser.list_books_in_category(name), f'Books in "{name}"')

    def _filter_by_author(self, name: str) -> None:
        self._author_edit.setText(name)
        if self._query_edit.text().strip():
            self._run_search()
        else:
            self._browse(self._browser.list_books_by_author(name), f"Books by {name}")

    def _filter_by_library(self, name: str) -> None:
        index = self._library_combo.findText(name)
        if index >= 0:
            self._library_combo.setCurrentIndex(index)
        if self._query_edit.text().strip():
            self._run_search()
        elif name != ALL_LIBRARIES_LABEL:
            self._browse(self._browser.list_books_in_library(name), f"Books in {name}")
        else:
            self._clear_results()
            self._status_label.setText(
                "Type a search, or pick a specific category/author/library to browse."
            )

    def _browse(self, summaries: tuple[BookSummary, ...], heading: str) -> None:
        """Show a directly-openable list of books - no search query, no excerpts."""
        self._clear_results()
        if not summaries:
            self._status_label.setText(f"{heading}: no books found.")
            return
        suffix = f" (showing first {len(summaries)})" if len(summaries) == MAX_BROWSE_RESULTS else ""
        self._status_label.setText(f"{heading} - {len(summaries)} book(s){suffix}")
        for summary in summaries:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, self._build_summary_card(summary)
            )

    # -------------------------------------------------------------- middle

    def _build_middle_pane(self) -> QWidget:
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        layout.setSpacing(Spacing.SM)

        # The query box is the primary action on this screen, so it gets its
        # own full-width row with a visibly larger height/font, instead of
        # competing for space in a single crowded row with every filter.
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self._query_edit = QLineEdit()
        self._query_edit.setPlaceholderText(
            "Search by content, title, author... "
            '(content search supports AND / OR / NOT, "phrases")'
        )
        self._query_edit.setObjectName("mainSearchBox")
        self._query_edit.setMinimumHeight(40)
        self._query_edit.returnPressed.connect(self._run_search)
        search_row.addWidget(self._query_edit, stretch=1)

        search_button = QPushButton("Search")
        search_button.setObjectName("primaryButton")
        search_button.setMinimumHeight(40)
        search_button.setDefault(True)
        search_button.clicked.connect(self._run_search)
        search_row.addWidget(search_button)

        self._mic_button = QPushButton()
        self._mic_button.setIcon(button_icon("mic"))
        self._mic_button.setIconSize(button_icon_size())
        self._mic_button.setToolTip("Speak a search query")
        self._mic_button.setMinimumHeight(40)
        # Visible only when voice search is actually enabled (Settings
        # toggle, wired via MainWindow) - same visibility-gating discipline
        # as ViewerScreen's TTS play button.
        self._mic_button.setVisible(self._enable_lazy_voice_search)
        self._mic_button.clicked.connect(self._on_mic_button_clicked)
        search_row.addWidget(self._mic_button)
        layout.addLayout(search_row)

        # Two rows, not one: six controls in a single unwrapped QHBoxLayout
        # measured a real ~1040px combined minimum width (confirmed by
        # constructing the real widget tree and reading minimumSizeHint()),
        # which was the direct cause of the whole window being forced open
        # wider than the screen on narrower monitors - Qt never lets a
        # window shrink below its layout's true minimum size.
        filter_row_1 = QHBoxLayout()
        self._library_combo = QComboBox()
        # Real fix: a QComboBox's default AdjustToContentsOnFirstShow policy
        # sizes the closed box to its WIDEST item - one real library name
        # ("Maktaba Al-Maknoon (PDF Archive)  (3128)") measured 414px on its
        # own, which was a direct contributor to the window being forced
        # open wider than the screen. An Ignored horizontal size policy
        # stops the combo's own content from dictating the row's minimum
        # width (confirmed directly: it drops a widget's contribution to
        # its container's minimumSizeHint to near-zero) - the dropdown
        # popup still shows every name in full when opened.
        self._library_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._library_combo.addItem(ALL_LIBRARIES_LABEL)
        for library in self._browser.list_libraries():
            self._library_combo.addItem(library)
        filter_row_1.addWidget(self._library_combo)

        self._author_edit = QLineEdit()
        self._author_edit.setPlaceholderText("Author (exact)")
        filter_row_1.addWidget(self._author_edit)

        self._category_edit = QLineEdit()
        self._category_edit.setPlaceholderText("Category (exact)")
        filter_row_1.addWidget(self._category_edit)

        self._exact_match_checkbox = QCheckBox("Exact match")
        self._exact_match_checkbox.setToolTip(
            "On: literal spelling only.\n"
            "Off (default): tolerant of real spelling/keyboard variants "
            "(e.g. علي/علی, ك/ک)."
        )
        self._exact_match_checkbox.toggled.connect(self._on_exact_match_toggled)
        filter_row_1.addWidget(self._exact_match_checkbox)
        layout.addLayout(filter_row_1)

        filter_row_2 = QHBoxLayout()
        self._search_target_combo = QComboBox()
        self._search_target_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._search_target_combo.addItem("Name + content", "both")
        self._search_target_combo.addItem("Book name only", "title")
        self._search_target_combo.addItem("Book content only", "content")
        self._search_target_combo.setToolTip(
            "Search by book name (title), inside book content, or both."
        )
        self._search_target_combo.currentIndexChanged.connect(self._on_search_target_changed)
        filter_row_2.addWidget(self._search_target_combo)

        self._scope_combo = QComboBox()
        self._scope_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._scope_combo.addItem("Main text", "content")
        self._scope_combo.addItem("Footnotes", "footnotes")
        self._scope_combo.addItem("Both", "both")
        self._scope_combo.setToolTip(
            "When searching book content: main page text, footnotes/"
            "commentary only, or both."
        )
        self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        filter_row_2.addWidget(self._scope_combo)
        filter_row_2.addStretch(1)

        self._detail_toggle_button = QPushButton()
        self._detail_toggle_button.setCheckable(True)
        self._detail_toggle_button.setChecked(True)
        self._detail_toggle_button.setToolTip("Show/hide the details panel")
        self._detail_toggle_button.setFlat(True)
        self._detail_toggle_button.setIcon(button_icon("prev"))
        self._detail_toggle_button.setIconSize(button_icon_size())
        self._detail_toggle_button.toggled.connect(self._on_detail_panel_toggled)
        filter_row_2.addWidget(self._detail_toggle_button)

        self._detail_maximize_button = QPushButton()
        self._detail_maximize_button.setFlat(True)
        self._detail_maximize_button.setIcon(button_icon("maximize"))
        self._detail_maximize_button.setIconSize(button_icon_size())
        self._detail_maximize_button.setToolTip("Maximize the details panel")
        self._detail_maximize_button.clicked.connect(self._on_detail_maximize_clicked)
        filter_row_2.addWidget(self._detail_maximize_button)
        layout.addLayout(filter_row_2)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet(MUTED_LABEL_STYLE)
        layout.addWidget(self._status_label)

        self._results_area = QScrollArea()
        self._results_area.setWidgetResizable(True)
        self._results_area.setFrameShape(QFrame.Shape.NoFrame)
        self._results_container = QWidget()
        self._results_layout = QVBoxLayout(self._results_container)
        self._results_layout.setContentsMargins(0, 0, Spacing.XS, 0)
        self._results_layout.setSpacing(Spacing.XS)
        self._results_layout.addStretch(1)
        self._results_area.setWidget(self._results_container)
        layout.addWidget(self._results_area, stretch=1)
        return pane

    def focus_search_box(self) -> None:
        """Move keyboard focus to the search box (also reachable via Ctrl+F/Ctrl+K)."""
        self._query_edit.setFocus()

    def _install_search_completer(self) -> None:
        """Attach a QCompleter to the search box from data already loaded for
        the Categories/Authors tabs, plus recent searches - no new query."""
        category_names = [
            node.name for node in _flatten_categories(self._browser.get_category_tree())
        ]
        author_names = [name for name, _button in self._author_row_buttons]
        suggestions = list(
            dict.fromkeys(  # de-duplicated, order-preserving
                self._recent_searches.list_recent() + author_names + category_names
            )
        )
        completer = QCompleter(suggestions, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._query_edit.setCompleter(completer)

    def _on_exact_match_toggled(self, _checked: bool) -> None:
        if self._query_edit.text().strip():
            self._run_search()

    def _on_scope_changed(self, _index: int) -> None:
        if self._query_edit.text().strip():
            self._run_search()

    def _on_search_target_changed(self, _index: int) -> None:
        if self._query_edit.text().strip():
            self._run_search()

    def _run_search(self) -> None:
        query = self._query_edit.text().strip()
        self._clear_results()

        library = self._library_combo.currentText()
        library = None if library == ALL_LIBRARIES_LABEL else library
        author = self._author_edit.text().strip() or None
        category = self._category_edit.text().strip() or None
        exact = self._exact_match_checkbox.isChecked()
        scope = self._scope_combo.currentData()
        search_target = self._search_target_combo.currentData()  # "both" | "title" | "content"

        if not query:
            # No search text - the Author/Category/Library filters can still
            # be used on their own (e.g. typed directly into the Author or
            # Category box, then Search clicked) to browse straight to the
            # matching books, same as clicking a name in the left pane does.
            if author or category or library:
                self._browse_by_filters(library, author, category)
            else:
                self._status_label.setText("")
            return

        self._recent_searches.record(query)

        # Book-name search and content search each run only when the real
        # "Search in" choice includes them - "Name + content" (the default)
        # runs both and shows two clearly labeled groups, title matches
        # first since that's usually what a name-shaped query means.
        title_matches: tuple[BookSummary, ...] = ()
        if search_target in ("title", "both"):
            title_matches = self._browser.search_by_title(
                query, DEFAULT_LIMIT, library, author, category, exact
            )

        results: tuple[SearchResult, ...] = ()
        if search_target in ("content", "both"):
            try:
                results = self._search_service.search(
                    query, DEFAULT_LIMIT, library, author, category, exact, scope
                )
            except BookSearchError:
                self._status_label.setText(
                    "That search couldn't be run - check your query and try again."
                )
                return
            except ValueError:
                self._status_label.setText("Enter a search term.")
                return

        matched_keys = {(result.book_id, result.page_number) for result in results}
        self._current_query = query
        self._current_title_count = len(title_matches)
        self._current_content_count = len(results)

        content_search_active = search_target in ("content", "both")
        semantic_available = (
            self._semantic_search_service is not None or self._enable_lazy_semantic_search
        )
        semantic_will_run = (
            content_search_active and semantic_available and not exact and scope != "footnotes"
        )

        if not results and not title_matches:
            status = (
                f'No matches found for "{query}" yet - checking related pages...'
                if semantic_will_run
                else f'No matches found for "{query}".'
            )
            self._status_label.setText(status)
        else:
            status_bits = []
            if title_matches:
                status_bits.append(f"{len(title_matches)} title match(es)")
            if content_search_active:
                status_bits.append(f"{len(results)} content result(s)")
            self._status_label.setText(", ".join(status_bits))

        if title_matches:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, _pane_title("Matching titles")
            )
            for summary in title_matches:
                self._results_layout.insertWidget(
                    self._results_layout.count() - 1, self._build_summary_card(summary)
                )
        for result in results:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, self._build_result_card(result)
            )

        if semantic_will_run:
            self._start_semantic_search(query, library, matched_keys)

    def _start_semantic_search(
        self, query: str, library: str | None, exclude_keys: set[tuple[int, int | None]]
    ) -> None:
        """Kick off semantic search in a background thread - never blocks the GUI.

        `_get_or_build_semantic_service` (passed to the worker, called on
        the worker thread) does the lazy, at-most-once real construction;
        `self._semantic_search_lock` guards it so two overlapping searches
        can't both try to build the model at once. A stale result (the
        user searched again before this one finished) is silently
        discarded in the completion handler, not displayed.
        """
        self._current_exclude_keys = exclude_keys
        worker = SemanticSearchWorker(
            self._get_or_build_semantic_service, query, DEFAULT_LIMIT, library, self
        )
        worker.search_succeeded.connect(self._on_semantic_search_succeeded)
        worker.search_failed.connect(self._on_semantic_search_failed)
        self._semantic_worker = worker
        worker.start()

    def _get_or_build_semantic_service(self) -> SemanticBookSearchService | None:
        """Return the cached semantic service, building it at most once.

        Runs on the worker thread (real, one-time ~20+ second import cost
        for `sentence_transformers`/`torch`, confirmed directly - see
        CHANGELOG) - guarded by a lock so two overlapping background
        searches can't both attempt the build simultaneously.
        """
        with self._semantic_search_lock:
            if self._semantic_search_service is None and self._enable_lazy_semantic_search:
                if not self._semantic_search_attempted:
                    self._semantic_search_attempted = True
                    self._semantic_search_service = self._build_real_semantic_search_service()
            return self._semantic_search_service

    def _on_semantic_search_succeeded(
        self, query: str, results: tuple[SemanticSearchResult, ...]
    ) -> None:
        if query != self._current_query:
            return  # stale - a newer search has already started
        semantic_results = tuple(
            result
            for result in results
            if (result.book_id, result.page_number) not in self._current_exclude_keys
        )
        self._finalize_semantic_results(semantic_results)

    def _on_semantic_search_failed(self, query: str) -> None:
        if query != self._current_query:
            return
        self._finalize_semantic_results(())

    def _finalize_semantic_results(
        self, semantic_results: tuple[SemanticSearchResult, ...]
    ) -> None:
        if not semantic_results:
            if self._current_title_count == 0 and self._current_content_count == 0:
                self._status_label.setText(f'No matches found for "{self._current_query}".')
            return

        status_bits = []
        if self._current_title_count:
            status_bits.append(f"{self._current_title_count} title match(es)")
        status_bits.append(f"{self._current_content_count} content result(s)")
        status_bits.append(f"{len(semantic_results)} related page(s)")
        self._status_label.setText(", ".join(status_bits))

        self._results_layout.insertWidget(
            self._results_layout.count() - 1, _pane_title("Related pages")
        )
        for semantic_result in semantic_results:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1,
                self._build_semantic_result_card(semantic_result),
            )

    def _build_real_semantic_search_service(self) -> SemanticBookSearchService | None:
        """Build the real local-model semantic search service, or None on any failure.

        Failure is expected and normal here - the optional "ai" extra
        (`sentence-transformers`) may not be installed, or model loading
        may fail for other reasons. Either way, keyword search must keep
        working unaffected.
        """
        try:
            from islamic_research_hub.infrastructure.ai.sentence_transformer_embedder import (
                SentenceTransformerEmbedder,
            )
            from islamic_research_hub.infrastructure.persistence.sqlite_page_embedding_repository import (
                SqlitePageEmbeddingRepository,
            )

            embedder = SentenceTransformerEmbedder()
            store = SqlitePageEmbeddingRepository(self._database_path)
            return SemanticBookSearchService(embedder, store)
        except Exception:
            LOGGER.exception("Semantic search unavailable - falling back to keyword-only.")
            return None

    # ----------------------------------------------------------- voice search

    def _on_mic_button_clicked(self) -> None:
        if self._audio_source is not None:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            self._status_label.setText("No microphone was found.")
            return
        audio_format = QAudioFormat()
        audio_format.setSampleRate(VOICE_SEARCH_SAMPLE_RATE)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(audio_format):
            self._status_label.setText(
                "This microphone doesn't support the required audio format."
            )
            return

        self._audio_buffer = bytearray()
        source = QAudioSource(device, audio_format, self)
        io_device = source.start()
        if io_device is None:
            self._status_label.setText("Could not start recording from the microphone.")
            return
        io_device.readyRead.connect(self._on_audio_data_ready)
        self._audio_source = source
        self._audio_io_device = io_device
        self._mic_button.setIcon(button_icon("mic", DANGER))
        self._mic_button.setToolTip("Recording... click to stop")
        self._status_label.setText("Listening...")
        self._max_record_timer.start()

    def _on_audio_data_ready(self) -> None:
        if self._audio_io_device is not None:
            self._audio_buffer.extend(self._audio_io_device.readAll().data())

    def _stop_recording(self) -> None:
        self._max_record_timer.stop()
        if self._audio_source is not None:
            self._audio_source.stop()
        if self._audio_io_device is not None:
            try:
                self._audio_io_device.readyRead.disconnect(self._on_audio_data_ready)
            except (TypeError, RuntimeError):
                pass
        self._audio_source = None
        self._audio_io_device = None
        samples = pcm16_bytes_to_samples(bytes(self._audio_buffer))
        self._audio_buffer = bytearray()
        self._on_recording_captured(samples, VOICE_SEARCH_SAMPLE_RATE)

    def _on_recording_captured(self, samples: tuple[float, ...], sample_rate: int) -> None:
        """Directly-callable completion seam, separate from `_stop_recording`'s
        real `QAudioSource` plumbing - a real microphone doesn't exist in a
        headless test, so widget tests call this with synthetic samples
        instead of driving real hardware."""
        self._mic_button.setEnabled(False)
        self._mic_button.setIcon(button_icon("mic"))
        self._mic_button.setToolTip("Speak a search query")
        self._status_label.setText("Transcribing...")
        worker = VoiceSearchWorker(
            self._get_or_build_voice_search_service, samples, sample_rate, self
        )
        worker.transcription_ready.connect(self._on_transcription_ready)
        worker.transcription_failed.connect(self._on_transcription_failed)
        self._voice_worker = worker
        worker.start()

    def _get_or_build_voice_search_service(self) -> VoiceSearchService | None:
        """Return the cached voice search service, building it at most once.

        Runs on the worker thread - guarded by a lock so two overlapping
        attempts can't both try to build the model at once. Mirrors
        `_get_or_build_semantic_service`.
        """
        with self._voice_search_lock:
            if self._voice_search_service is None and self._enable_lazy_voice_search:
                if not self._voice_search_attempted:
                    self._voice_search_attempted = True
                    self._voice_search_service = self._build_real_voice_search_service()
            return self._voice_search_service

    def _build_real_voice_search_service(self) -> VoiceSearchService | None:
        """Build the real local faster-whisper voice search service, or None on any failure.

        Failure is expected and normal here - the optional "voice" extra
        (`faster-whisper`) may not be installed, or model loading may fail
        for other reasons. Either way, typed search must keep working
        unaffected.
        """
        try:
            from islamic_research_hub.infrastructure.ai.faster_whisper_transcriber import (
                FasterWhisperTranscriber,
            )

            return VoiceSearchService(FasterWhisperTranscriber())
        except Exception:
            LOGGER.exception("Voice search unavailable.")
            return None

    def _on_transcription_ready(self, text: str) -> None:
        self._mic_button.setEnabled(True)
        self._query_edit.setText(text)
        self._run_search()

    def _on_transcription_failed(self) -> None:
        self._mic_button.setEnabled(True)
        self._status_label.setText("Could not understand the recording - please try again.")

    def _browse_by_filters(
        self, library: str | None, author: str | None, category: str | None
    ) -> None:
        """Browse straight to books matching Author/Category/Library filters alone."""
        summaries = self._browser.list_books_by_filters(library, author, category)
        heading_bits = []
        if author:
            heading_bits.append(f"author {author}")
        if category:
            heading_bits.append(f'category "{category}"')
        if library:
            heading_bits.append(f"library {library}")
        self._browse(summaries, "Books matching " + ", ".join(heading_bits))

    def _clear_results(self) -> None:
        while self._results_layout.count() > 1:
            item = self._results_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._selected_card_index = -1

    # ----------------------------------------------------- keyboard nav

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Arrow keys move a real selection through the result cards; Enter
        opens the selected one - keyboard-only result navigation, the
        query box stays focused throughout (no click needed)."""
        if watched is self._query_edit and event.type() == QEvent.Type.KeyPress:
            key_event = event
            if isinstance(key_event, QKeyEvent):
                if key_event.key() == Qt.Key.Key_Down:
                    self._move_selection(1)
                    return True
                if key_event.key() == Qt.Key.Key_Up:
                    self._move_selection(-1)
                    return True
                if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if self._selected_card_index >= 0:
                        self._open_selected_result()
                        return True
        return super().eventFilter(watched, event)

    def _result_cards(self) -> list[QFrame]:
        """Every real result/summary card currently shown, in display order
        (the results layout's last item is always the trailing stretch)."""
        return [
            self._results_layout.itemAt(index).widget()
            for index in range(self._results_layout.count() - 1)
        ]

    def _move_selection(self, delta: int) -> None:
        cards = self._result_cards()
        if not cards:
            return
        if self._selected_card_index == -1:
            new_index = 0 if delta > 0 else len(cards) - 1
        else:
            new_index = max(0, min(len(cards) - 1, self._selected_card_index + delta))
        self._set_selected_card_index(new_index)
        self._results_area.ensureWidgetVisible(cards[new_index])

    def _set_selected_card_index(self, index: int) -> None:
        cards = self._result_cards()
        for card_index, card in enumerate(cards):
            card.setProperty("selected", card_index == index)
            card.style().unpolish(card)
            card.style().polish(card)
        self._selected_card_index = index

    def _open_selected_result(self) -> None:
        cards = self._result_cards()
        if not (0 <= self._selected_card_index < len(cards)):
            return
        card = cards[self._selected_card_index]
        book_id = card.property("book_id")
        page_number = card.property("page_number")
        if book_id is not None:
            self.open_in_viewer_requested.emit(book_id, page_number or 1)

    def _copy_card_citation(self, book_id: int, page_number: int | None) -> None:
        """Copy a real citation for a result card's book/page to the
        clipboard - same `format_citation()` mechanism as the Viewer's
        Copy Citation button, reused rather than duplicated."""
        metadata = self._browser.get_book_metadata(book_id)
        if metadata is None or metadata.title is None:
            return
        citation = format_citation(
            metadata.title,
            page_number or 1,
            paragraph_index=1,
            volume_number=metadata.volume_number,
        )
        QGuiApplication.clipboard().setText(citation)

    def _build_result_card(self, result: SearchResult) -> QFrame:
        card = QFrame()
        card.setObjectName("resultCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setProperty("book_id", result.book_id)
        card.setProperty("page_number", result.page_number)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(Spacing.SM, Spacing.XS, Spacing.SM, Spacing.XS)
        card_layout.setSpacing(Spacing.XS)

        title = QLabel(result.title or "(untitled)")
        title.setStyleSheet(f"font-size: {Type.BODY_LG}px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [result.author or "Unknown author", result.library or "Unknown library"]
        if result.page_number is not None:
            meta_bits.append(f"page {result.page_number}")
        if result.source == "footnote":
            meta_bits.append("footnote match")
        meta = QLabel(" · ".join(meta_bits))
        meta.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.BODY_SM}px;")
        card_layout.addWidget(meta)

        excerpt = QLabel(highlight_excerpt_html(result.excerpt))
        excerpt.setTextFormat(Qt.TextFormat.RichText)
        excerpt.setWordWrap(True)
        excerpt.setMaximumHeight(_EXCERPT_MAX_HEIGHT_PX)
        excerpt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        excerpt.setStyleSheet(f"font-size: {Type.BODY}px; line-height: 150%; {RTL_TEXT_STYLE}")
        _enable_height_for_width(excerpt)
        card_layout.addWidget(excerpt)

        card.mousePressEvent = lambda _event, r=result: self._show_details(r.book_id, r.page_number)

        open_row = self._build_open_row(result.book_id, result.page_number)
        if open_row is not None:
            card_layout.addWidget(open_row)

        return card

    def _build_semantic_result_card(self, result: SemanticSearchResult) -> QFrame:
        """A result card for a semantically (not keyword-) matched page.

        No `**highlight**` markers - a semantic match has no literal
        matched term to bold, unlike a keyword excerpt.
        """
        card = QFrame()
        card.setObjectName("resultCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setProperty("book_id", result.book_id)
        card.setProperty("page_number", result.page_number)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(Spacing.SM, Spacing.XS, Spacing.SM, Spacing.XS)
        card_layout.setSpacing(Spacing.XS)

        title = QLabel(result.title or "(untitled)")
        title.setStyleSheet(f"font-size: {Type.BODY_LG}px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [result.author or "Unknown author", result.library or "Unknown library"]
        if result.page_number is not None:
            meta_bits.append(f"page {result.page_number}")
        meta = QLabel(" · ".join(meta_bits))
        meta.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.BODY_SM}px;")
        card_layout.addWidget(meta)

        excerpt = QLabel(result.excerpt)
        excerpt.setWordWrap(True)
        excerpt.setMaximumHeight(_EXCERPT_MAX_HEIGHT_PX)
        excerpt.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        excerpt.setStyleSheet(f"font-size: {Type.BODY}px; line-height: 150%; {RTL_TEXT_STYLE}")
        _enable_height_for_width(excerpt)
        card_layout.addWidget(excerpt)

        card.mousePressEvent = lambda _event, r=result: self._show_details(r.book_id, r.page_number)

        open_row = self._build_open_row(result.book_id, result.page_number)
        if open_row is not None:
            card_layout.addWidget(open_row)

        return card

    def _build_summary_card(self, summary: BookSummary) -> QFrame:
        """A directly-openable book card for browse results - no search excerpt."""
        card = QFrame()
        card.setObjectName("resultCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setProperty("book_id", summary.book_id)
        card.setProperty("page_number", None)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(Spacing.SM, Spacing.XS, Spacing.SM, Spacing.XS)
        card_layout.setSpacing(Spacing.XS)

        title = QLabel(summary.title or "(untitled)")
        title.setStyleSheet(f"font-size: {Type.BODY_LG}px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [summary.author or "Unknown author", summary.library or "Unknown library"]
        meta = QLabel(" · ".join(meta_bits))
        meta.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.BODY_SM}px;")
        card_layout.addWidget(meta)

        card.mousePressEvent = lambda _event, s=summary: self._show_details(s.book_id)

        open_row = self._build_open_row(summary.book_id, None)
        if open_row is not None:
            card_layout.addWidget(open_row)

        return card

    def _build_open_row(self, book_id: int, page_number: int | None) -> QWidget | None:
        source = self._browser.get_book_source(book_id)
        if source is None:
            return None
        pdf_path = resolve_pdf_path(source[1], source[0], self._maknoon_pdf_folder)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 0)
        if pdf_path is not None:
            pdf_button = QPushButton("Open PDF")
            pdf_button.setIcon(button_icon("open-pdf"))
            pdf_button.setIconSize(button_icon_size())
            pdf_button.clicked.connect(lambda: QDesktopServices.openUrl(_file_url(pdf_path)))
            row_layout.addWidget(pdf_button)

        target_page = page_number or 1
        read_button = QPushButton("Read in app")
        read_button.setIcon(button_icon("viewer"))
        read_button.setIconSize(button_icon_size())
        read_button.clicked.connect(
            lambda: self.open_in_viewer_requested.emit(book_id, target_page)
        )
        row_layout.addWidget(read_button)

        details_button = QPushButton("Details")
        details_button.clicked.connect(lambda: self._show_details(book_id, page_number))
        row_layout.addWidget(details_button)

        citation_button = QPushButton("Copy citation")
        citation_button.setToolTip("Copy a citation for this page to the clipboard.")
        citation_button.clicked.connect(
            lambda: self._copy_card_citation(book_id, page_number)
        )
        row_layout.addWidget(citation_button)

        row_layout.addStretch(1)
        return row

    # --------------------------------------------------------------- right

    def _build_right_pane(self) -> QWidget:
        pane = QScrollArea()
        pane.setObjectName("resultCard")
        pane.setFrameShape(QFrame.Shape.NoFrame)
        pane.setMinimumWidth(RIGHT_PANE_WIDTH)
        # Responsive Desktop fix: same reasoning as the left pane - a detail
        # panel shouldn't be able to crowd out the results pane either.
        pane.setMaximumWidth(480)
        pane.setWidgetResizable(True)
        self._detail_pane = pane

        self._detail_content = QWidget()
        self._detail_layout = QVBoxLayout(self._detail_content)
        self._detail_layout.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        self._detail_layout.setSpacing(Spacing.XS)
        self._show_detail_empty_state()
        pane.setWidget(self._detail_content)
        return pane

    def _on_detail_panel_toggled(self, checked: bool) -> None:
        """Collapse/expand the right (detail) pane - mirrors ViewerScreen's
        TOC toggle (same `animate_splitter_size` mechanism, same
        fixed-target-width shape), added so the reader/results can claim
        that width back when the details panel isn't currently needed.

        Real bug found writing this feature's own test: without relaxing
        the pane's permanent 220px floor, `QSplitter.setSizes()` refused
        to shrink it at all (same already-documented issue `WorkspaceScreen`
        hit with the AI panel). Relaxing it gets the pane down to a small
        residual width (a `QScrollArea`'s own real `minimumSizeHint()`,
        confirmed directly - `setMinimumWidth(0)` alone doesn't fully
        override it the way it does for a plain `QWidget`-based panel like
        the AI panel), not literally 0px - a real, acceptable Qt
        limitation for a cosmetic collapse, not worth chasing further.
        """
        self._detail_toggle_button.setIcon(button_icon("prev" if checked else "next"))
        self._detail_pane.setMinimumWidth(RIGHT_PANE_WIDTH if checked else 0)
        target = RIGHT_PANE_WIDTH if checked else 0
        self._detail_panel_animation = animate_splitter_size(self._splitter, index=2, end=target)

    def _on_detail_maximize_clicked(self) -> None:
        """Maximize/restore the details panel - if it's currently
        collapsed, expand it first so maximizing always shows something
        real rather than a maximized-but-invisible panel."""
        if not self._detail_toggle_button.isChecked():
            self._detail_toggle_button.setChecked(True)
        self._detail_panel_toggle.toggle_maximized()
        self._detail_maximize_button.setIcon(
            button_icon("restore" if self._detail_panel_toggle.is_maximized else "maximize")
        )

    def _show_detail_empty_state(self) -> None:
        """The detail pane before anything is selected - a real message,
        not a blank rectangle."""
        self._detail_layout.addWidget(
            EmptyStateLabel(
                "Select a result to see its details here.", centered=True
            )
        )
        self._detail_layout.addStretch(1)

    def _on_rating_changed(self, book_id: int) -> None:
        value = self._rating_combo.currentData()
        if value is None:
            self._ratings.clear_rating(book_id)
        else:
            self._ratings.set_rating(book_id, value)

    def _show_details(self, book_id: int, page_number: int | None = None) -> None:
        metadata = self._browser.get_book_metadata(book_id)
        if metadata is None:
            return
        self._clear_detail_panel()
        self._populate_detail_panel(metadata, page_number)

    def _clear_detail_panel(self) -> None:
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_detail_panel(self, metadata: BookMetadata, page_number: int | None) -> None:
        title = QLabel(metadata.title or "(untitled)")
        title.setWordWrap(True)
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; {RTL_TEXT_STYLE}")
        self._detail_layout.addWidget(title)

        rows: list[tuple[str, str | None]] = [
            ("Author", metadata.author),
            ("Publisher", metadata.publisher),
            ("Language", metadata.language),
            ("Category", metadata.category),
            ("Library", metadata.library),
        ]
        if metadata.series_title:
            series_text = metadata.series_title
            if metadata.volume_number is not None:
                series_text += f" (volume {metadata.volume_number})"
            rows.append(("Series", series_text))
        rows.append(("Pages", str(metadata.page_count)))
        rows.append(("Chapters", str(metadata.chapter_count)))
        if page_number is not None:
            rows.append(("Matched page", str(page_number)))

        for label_text, value in rows:
            self._detail_layout.addWidget(_detail_row(label_text, value))

        self._detail_layout.addWidget(_pane_title("Your rating"))
        self._rating_combo = QComboBox()
        self._rating_combo.addItem("Not rated", None)
        for value in range(1, 6):
            self._rating_combo.addItem("★" * value, value)
        current_rating = self._ratings.get_rating(metadata.book_id)
        self._rating_combo.setCurrentIndex(max(self._rating_combo.findData(current_rating), 0))
        self._rating_combo.currentIndexChanged.connect(
            lambda _index, book_id=metadata.book_id: self._on_rating_changed(book_id)
        )
        self._detail_layout.addWidget(self._rating_combo)

        open_viewer_button = QPushButton("Open in Viewer")
        open_viewer_button.setObjectName("primaryButton")
        open_viewer_button.setIcon(button_icon("viewer", SURFACE_RAISED))
        open_viewer_button.setIconSize(button_icon_size())
        target_page = page_number or 1
        open_viewer_button.clicked.connect(
            lambda: self.open_in_viewer_requested.emit(metadata.book_id, target_page)
        )
        self._detail_layout.addWidget(open_viewer_button)

        source = self._browser.get_book_source(metadata.book_id)
        if source is not None:
            pdf_path = resolve_pdf_path(source[1], source[0], self._maknoon_pdf_folder)
            if pdf_path is not None:
                pdf_button = QPushButton("Open source PDF")
                pdf_button.setIcon(button_icon("open-pdf"))
                pdf_button.setIconSize(button_icon_size())
                pdf_button.clicked.connect(lambda: QDesktopServices.openUrl(_file_url(pdf_path)))
                self._detail_layout.addWidget(pdf_button)

        self._detail_layout.addStretch(1)


def _pane_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px; font-weight: 600; margin-top: 6px;"
    )
    return label


def _detail_row(label_text: str, value: str | None) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    caption = QLabel(label_text)
    caption.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px;")
    layout.addWidget(caption)
    value_label = QLabel(value or "Unknown")
    value_label.setWordWrap(True)
    value_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    layout.addWidget(value_label)
    return row


def _category_tree_item(node: CategoryNode) -> QTreeWidgetItem:
    item = QTreeWidgetItem([f"{node.name}  ({node.book_count})"])
    item.setData(0, Qt.ItemDataRole.UserRole, node.name)
    for child in node.children:
        item.addChild(_category_tree_item(child))
    return item


def _flatten_categories(nodes: tuple[CategoryNode, ...]) -> list[CategoryNode]:
    """Flatten a category tree into a single list, for completer suggestions."""
    flat: list[CategoryNode] = []
    for node in nodes:
        flat.append(node)
        flat.extend(_flatten_categories(node.children))
    return flat


def _file_url(path: Path) -> QUrl:
    return QUrl.fromLocalFile(str(path))


def _enable_height_for_width(label: QLabel) -> None:
    """Make a word-wrapped rich-text QLabel report its real wrapped height to the layout.

    Without this, Qt's QVBoxLayout sizes such a label using its unwrapped
    sizeHint (a single line) instead of the multi-line height it actually
    needs at its assigned width, clipping the excerpt to one line's height.
    """
    policy = label.sizePolicy()
    policy.setHeightForWidth(True)
    label.setSizePolicy(policy)
