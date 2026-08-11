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
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
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
from islamic_research_hub.application.pdf_source_resolver import candidate_pdf_path
from islamic_research_hub.application.semantic_book_search import SemanticBookSearchService
from islamic_research_hub.application.voice_transcription import VoiceSearchService
from islamic_research_hub.domain.models.book_metadata import BookMetadata
from islamic_research_hub.domain.models.book_summary import BookSummary
from islamic_research_hub.domain.models.category_node import CategoryNode
from islamic_research_hub.domain.models.saved_search import SavedSearch
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
from islamic_research_hub.infrastructure.persistence.saved_search_repository import (
    SavedSearchNameTakenError,
    SavedSearchRepository,
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
    Translator,
)
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.library_scope_dialog import LibraryScopeDialog
from islamic_research_hub.interfaces.desktop_app.list_row_button import list_row_button
from islamic_research_hub.interfaces.desktop_app.panel_toggle import PanelToggle
from islamic_research_hub.interfaces.desktop_app.search_history import RecentSearchStore
from islamic_research_hub.interfaces.desktop_app.semantic_search_worker import (
    SemanticSearchWorker,
)
from islamic_research_hub.shared.category_names import translated_category_name
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
LEFT_PANE_WIDTH = 280
"""Real bug fixed here: at 230px, the three English tab labels
("Categories"/"Author"/"Recent") didn't fit side by side and got
silently clipped ("ategori", "uthor") - English needs more room per word
than the Urdu/Arabic labels this was originally tuned against."""
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
    ai_quick_ask_requested = Signal(str)  # question
    """A real question asked from the empty detail pane's quick-ask box -
    `MainWindow` forwards it into the real `AiAssistantPanel` (expanding
    it if collapsed) rather than this screen duplicating the AI Agent's
    lazy-build/pre-flight/worker logic."""
    collapsed_changed = Signal(bool)
    """This whole screen's collapsed state, as embedded in `WorkspaceScreen`'s
    outer splitter - mirrors `AiAssistantPanel`'s own `collapsed_changed`
    exactly: this screen just owns the button/icon/local flag, the actual
    splitter-segment resize is `WorkspaceScreen`'s job."""

    def __init__(
        self,
        database_path: Path,
        maknoon_pdf_folder: Path,
        translator: Translator,
        search_service: BookSearchService | None = None,
        browser: BookBrowserRepository | None = None,
        recent_books: RecentBookRepository | None = None,
        ratings: BookRatingRepository | None = None,
        semantic_search_service: SemanticBookSearchService | None = None,
        enable_lazy_semantic_search: bool = False,
        recent_search_store: RecentSearchStore | None = None,
        enable_lazy_voice_search: bool = False,
        saved_searches: SavedSearchRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._maknoon_pdf_folder = maknoon_pdf_folder
        self._translator = translator
        self._status_is_idle = True
        self._detail_panel_is_empty = True
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
        self._saved_searches = saved_searches or SavedSearchRepository(database_path)
        self._selected_card_index = -1
        self._detail_panel_animation = None
        self._collapsed = False

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

        self._translator.language_changed.connect(self._retranslate)

    def _retranslate(self, _language: str) -> None:
        tr = self._translator.tr
        self._categories_tab_button.setText(tr("tab-categories"))
        self._authors_tab_button.setText(tr("tab-authors"))
        self._recent_tab_button.setText(tr("search-tab-recent"))
        self._browse_filter_edit.setPlaceholderText(tr("search-filter-placeholder"))
        self._libraries_pane_title_label.setText(tr("pane-libraries"))
        self._rebuild_library_chips()
        self._populate_category_tree(self._category_tree)
        if self._browse_stack.currentIndex() == 2:
            self._refresh_recent_list()
        self._query_edit.setPlaceholderText(tr("search-query-placeholder"))
        self._search_button.setText(tr("search-run-button"))
        self._mic_button.setToolTip(tr("search-mic-tooltip"))
        self._library_combo.setItemText(0, tr("all-libraries"))
        self._libraries_button.setToolTip(tr("search-scope-dialog-hint"))
        self._update_libraries_button_label()
        self._author_edit.setPlaceholderText(tr("search-author-placeholder"))
        self._category_edit.setPlaceholderText(tr("search-category-placeholder"))
        self._exact_match_checkbox.setText(tr("search-exact-match"))
        self._exact_match_checkbox.setToolTip(tr("search-exact-match-tooltip"))
        for index, key in enumerate(("search-target-both", "search-target-title", "search-target-content")):
            self._search_target_combo.setItemText(index, tr(key))
        self._search_target_combo.setToolTip(tr("search-target-tooltip"))
        for index, key in enumerate(("search-scope-main", "search-scope-footnotes", "search-scope-both")):
            self._scope_combo.setItemText(index, tr(key))
        self._scope_combo.setToolTip(tr("search-scope-tooltip"))
        for index, key in enumerate(
            ("search-match-all-words", "search-match-any-word", "search-match-exact-phrase")
        ):
            self._match_mode_combo.setItemText(index, tr(key))
        self._match_mode_combo.setToolTip(tr("search-match-tooltip"))
        self._save_search_button.setToolTip(tr("search-save-search-tooltip"))
        self._saved_searches_button.setToolTip(tr("search-saved-searches-tooltip"))
        self._detail_toggle_button.setToolTip(tr("search-detail-toggle-tooltip"))
        self._detail_maximize_button.setToolTip(tr("search-detail-maximize-tooltip"))
        self._collapse_self_button.setToolTip(tr("search-collapse-panel-tooltip"))
        if self._status_is_idle:
            self._status_label.setText(tr("search-status-idle"))
        if self._detail_panel_is_empty:
            self._clear_detail_panel()
            self._show_detail_empty_state()
        self._retranslate_result_cards()

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
        self._categories_tab_button = QPushButton(self._translator.tr("tab-categories"))
        self._categories_tab_button.setCheckable(True)
        self._categories_tab_button.setChecked(True)
        self._categories_tab_button.setObjectName("navTab")
        self._categories_tab_button.clicked.connect(lambda: self._show_browse_tab(0))
        tab_row.addWidget(self._categories_tab_button)

        self._authors_tab_button = QPushButton(self._translator.tr("tab-authors"))
        self._authors_tab_button.setCheckable(True)
        self._authors_tab_button.setObjectName("navTab")
        self._authors_tab_button.clicked.connect(lambda: self._show_browse_tab(1))
        tab_row.addWidget(self._authors_tab_button)

        self._recent_tab_button = QPushButton(self._translator.tr("search-tab-recent"))
        self._recent_tab_button.setCheckable(True)
        self._recent_tab_button.setObjectName("navTab")
        self._recent_tab_button.clicked.connect(lambda: self._show_browse_tab(2))
        tab_row.addWidget(self._recent_tab_button)
        layout.addLayout(tab_row)

        # 691 real categories and 650 real authors are too many to scroll
        # through blindly - a live filter narrows either list as you type.
        self._browse_filter_edit = QLineEdit()
        self._browse_filter_edit.setPlaceholderText(self._translator.tr("search-filter-placeholder"))
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

        self._libraries_pane_title_label = _pane_title(self._translator.tr("pane-libraries"))
        layout.addWidget(self._libraries_pane_title_label)
        # Real bug fixed here: the library chip list used to be appended
        # directly with no scroll capability of its own - with 10+ real
        # libraries, its natural height could exceed what was actually
        # left in the window, and the overflow was simply pushed past the
        # pane's bounds with no way to reach it ("the list is hidden, I
        # have to scroll but there's nothing to scroll"). Wrapping it in
        # its own QScrollArea and giving it a real stretch factor (shared
        # with the tree/author list above) lets both sections shrink and
        # scroll independently instead of one silently starving the other.
        library_scroll_area = QScrollArea()
        library_scroll_area.setWidgetResizable(True)
        library_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        library_chip_container = QWidget()
        self._library_chip_layout = QVBoxLayout(library_chip_container)
        self._library_chip_layout.setContentsMargins(0, 0, 0, 0)
        self._library_chip_layout.setSpacing(4)
        self._rebuild_library_chips()
        library_scroll_area.setWidget(library_chip_container)
        layout.addWidget(library_scroll_area, stretch=1)

        return pane

    def _build_category_tree(self) -> QTreeWidget:
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._populate_category_tree(tree)
        tree.itemClicked.connect(self._on_category_clicked)
        return tree

    def _populate_category_tree(self, tree: QTreeWidget) -> None:
        tree.clear()
        language = self._translator.language
        for node in self._browser.get_category_tree():
            tree.addTopLevelItem(_category_tree_item(node, language))

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
            empty_label = EmptyStateLabel(self._translator.tr("search-no-recent-books"))
            self._recent_list_layout.addWidget(empty_label)
        else:
            for summary in recent:
                button = list_row_button(
                    f"{summary.title}  ({summary.author or self._translator.tr('common-unknown-author')})",
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

        all_libraries_label = self._translator.tr("all-libraries")
        all_chip = list_row_button(
            f"{all_libraries_label}  ({self._browser.get_header_stats().book_count})",
            object_name="libraryChip",
        )
        all_chip.clicked.connect(lambda: self._filter_by_library(all_libraries_label))
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
            self._browse(
                self._browser.list_books_in_category(name),
                self._translator.tr("search-heading-category").format(name=name),
            )

    def _filter_by_author(self, name: str) -> None:
        self._author_edit.setText(name)
        if self._query_edit.text().strip():
            self._run_search()
        else:
            self._browse(
                self._browser.list_books_by_author(name),
                self._translator.tr("search-heading-author").format(name=name),
            )

    def _filter_by_library(self, name: str) -> None:
        index = self._library_combo.findText(name)
        if index >= 0:
            self._library_combo.setCurrentIndex(index)
        if self._query_edit.text().strip():
            self._run_search()
        elif name != self._translator.tr("all-libraries"):
            self._browse(
                self._browser.list_books_in_library(name),
                self._translator.tr("search-heading-library").format(name=name),
            )
        else:
            self._clear_results()
            self._status_is_idle = True
            self._status_label.setText(self._translator.tr("search-status-idle"))

    def _browse(self, summaries: tuple[BookSummary, ...], heading: str) -> None:
        """Show a directly-openable list of books - no search query, no excerpts."""
        self._clear_results()
        self._status_is_idle = False
        if not summaries:
            self._status_label.setText(
                self._translator.tr("search-status-browse-empty").format(heading=heading)
            )
            return
        suffix = (
            self._translator.tr("search-status-showing-first").format(count=len(summaries))
            if len(summaries) == MAX_BROWSE_RESULTS
            else ""
        )
        self._status_label.setText(
            self._translator.tr("search-status-browse-count").format(
                heading=heading, count=len(summaries), suffix=suffix
            )
        )
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
        self._query_edit.setPlaceholderText(self._translator.tr("search-query-placeholder"))
        self._query_edit.setObjectName("mainSearchBox")
        self._query_edit.setMinimumHeight(40)
        self._query_edit.returnPressed.connect(self._run_search)
        search_row.addWidget(self._query_edit, stretch=1)

        self._search_button = QPushButton(self._translator.tr("search-run-button"))
        self._search_button.setObjectName("primaryButton")
        self._search_button.setMinimumHeight(40)
        self._search_button.setDefault(True)
        self._search_button.clicked.connect(self._run_search)
        search_row.addWidget(self._search_button)

        self._mic_button = QPushButton()
        self._mic_button.setIcon(button_icon("mic"))
        self._mic_button.setIconSize(button_icon_size())
        self._mic_button.setToolTip(self._translator.tr("search-mic-tooltip"))
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
        self._library_combo.addItem(self._translator.tr("all-libraries"))
        for library in self._browser.list_libraries():
            self._library_combo.addItem(library)
        self._library_combo.currentIndexChanged.connect(self._on_library_combo_changed)
        filter_row_1.addWidget(self._library_combo)

        # Multi-library search scope (Maktaba Jibreel's own search dialog
        # offers a real checklist of libraries to search at once, not
        # just one at a time) - a separate button rather than replacing
        # the combo outright, so the common single-library case stays as
        # simple as it already was. `None` means no multi-selection is
        # active and the combo above is the real source of truth.
        self._multi_library_selection: tuple[str, ...] | None = None
        self._libraries_button = QPushButton(self._translator.tr("search-libraries-button"))
        self._libraries_button.setToolTip(self._translator.tr("search-scope-dialog-hint"))
        self._libraries_button.clicked.connect(self._on_libraries_button_clicked)
        filter_row_1.addWidget(self._libraries_button)

        self._author_edit = QLineEdit()
        self._author_edit.setPlaceholderText(self._translator.tr("search-author-placeholder"))
        filter_row_1.addWidget(self._author_edit)

        self._category_edit = QLineEdit()
        self._category_edit.setPlaceholderText(self._translator.tr("search-category-placeholder"))
        filter_row_1.addWidget(self._category_edit)

        self._exact_match_checkbox = QCheckBox(self._translator.tr("search-exact-match"))
        self._exact_match_checkbox.setToolTip(self._translator.tr("search-exact-match-tooltip"))
        self._exact_match_checkbox.toggled.connect(self._on_exact_match_toggled)
        filter_row_1.addWidget(self._exact_match_checkbox)
        layout.addLayout(filter_row_1)

        filter_row_2 = QHBoxLayout()
        self._search_target_combo = QComboBox()
        self._search_target_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._search_target_combo.addItem(self._translator.tr("search-target-both"), "both")
        self._search_target_combo.addItem(self._translator.tr("search-target-title"), "title")
        self._search_target_combo.addItem(self._translator.tr("search-target-content"), "content")
        self._search_target_combo.setToolTip(self._translator.tr("search-target-tooltip"))
        self._search_target_combo.currentIndexChanged.connect(self._on_search_target_changed)
        filter_row_2.addWidget(self._search_target_combo)

        self._scope_combo = QComboBox()
        self._scope_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._scope_combo.addItem(self._translator.tr("search-scope-main"), "content")
        self._scope_combo.addItem(self._translator.tr("search-scope-footnotes"), "footnotes")
        self._scope_combo.addItem(self._translator.tr("search-scope-both"), "both")
        self._scope_combo.setToolTip(self._translator.tr("search-scope-tooltip"))
        self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        filter_row_2.addWidget(self._scope_combo)

        # How multiple search words combine - a friendly UI over FTS5's own
        # MATCH syntax (implicit AND / "OR" / a quoted phrase), which
        # already works if typed by hand (see search_by_title()'s
        # docstring) but requires knowing that syntax exists at all.
        self._match_mode_combo = QComboBox()
        self._match_mode_combo.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self._match_mode_combo.addItem(self._translator.tr("search-match-all-words"), "all")
        self._match_mode_combo.addItem(self._translator.tr("search-match-any-word"), "any")
        self._match_mode_combo.addItem(self._translator.tr("search-match-exact-phrase"), "phrase")
        self._match_mode_combo.setToolTip(self._translator.tr("search-match-tooltip"))
        self._match_mode_combo.currentIndexChanged.connect(self._on_match_mode_changed)
        filter_row_2.addWidget(self._match_mode_combo)
        filter_row_2.addStretch(1)

        self._save_search_button = QPushButton()
        self._save_search_button.setFlat(True)
        self._save_search_button.setIcon(button_icon("star"))
        self._save_search_button.setIconSize(button_icon_size())
        self._save_search_button.setToolTip(self._translator.tr("search-save-search-tooltip"))
        self._save_search_button.clicked.connect(self._on_save_search_clicked)
        filter_row_2.addWidget(self._save_search_button)

        self._saved_searches_button = QPushButton()
        self._saved_searches_button.setFlat(True)
        self._saved_searches_button.setIcon(button_icon("clock"))
        self._saved_searches_button.setIconSize(button_icon_size())
        self._saved_searches_button.setToolTip(
            self._translator.tr("search-saved-searches-tooltip")
        )
        self._saved_searches_button.clicked.connect(self._on_view_saved_searches_clicked)
        filter_row_2.addWidget(self._saved_searches_button)

        self._detail_toggle_button = QPushButton()
        self._detail_toggle_button.setCheckable(True)
        self._detail_toggle_button.setChecked(True)
        self._detail_toggle_button.setToolTip(self._translator.tr("search-detail-toggle-tooltip"))
        self._detail_toggle_button.setFlat(True)
        self._detail_toggle_button.setIcon(button_icon("prev"))
        self._detail_toggle_button.setIconSize(button_icon_size())
        self._detail_toggle_button.toggled.connect(self._on_detail_panel_toggled)
        filter_row_2.addWidget(self._detail_toggle_button)

        self._detail_maximize_button = QPushButton()
        self._detail_maximize_button.setFlat(True)
        self._detail_maximize_button.setIcon(button_icon("maximize"))
        self._detail_maximize_button.setIconSize(button_icon_size())
        self._detail_maximize_button.setToolTip(self._translator.tr("search-detail-maximize-tooltip"))
        self._detail_maximize_button.clicked.connect(self._on_detail_maximize_clicked)
        filter_row_2.addWidget(self._detail_maximize_button)

        # Real bug fixed here: this whole screen's segment of the outer
        # WorkspaceScreen splitter had no collapse control at all
        # (`setCollapsible(0, False)`) - on a real window it could crowd
        # out the reader with no way to shrink it back. Mirrors
        # AiAssistantPanel's own collapse button exactly: this widget owns
        # the button/icon/local flag, `WorkspaceScreen` does the actual
        # splitter-segment resize in response to `collapsed_changed`.
        self._collapse_self_button = QPushButton()
        self._collapse_self_button.setFlat(True)
        self._collapse_self_button.setIcon(button_icon("prev"))
        self._collapse_self_button.setIconSize(button_icon_size())
        self._collapse_self_button.setToolTip(self._translator.tr("search-collapse-panel-tooltip"))
        self._collapse_self_button.clicked.connect(self.toggle_collapsed)
        filter_row_2.addWidget(self._collapse_self_button)
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

    def _on_match_mode_changed(self, _index: int) -> None:
        if self._query_edit.text().strip():
            self._run_search()

    def _on_library_combo_changed(self, _index: int) -> None:
        # Picking a single library the plain way (chip click, saved
        # search, or the combo itself) supersedes any earlier multi-
        # library scope selection - one clear source of truth at a time.
        self._multi_library_selection = None
        self._update_libraries_button_label()

    def _on_libraries_button_clicked(self) -> None:
        dialog = LibraryScopeDialog(
            self._browser.list_libraries_with_counts(),
            self._multi_library_selection,
            self._translator,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._multi_library_selection = dialog.selected_libraries()
        self._update_libraries_button_label()
        if self._query_edit.text().strip() or self._author_edit.text().strip() or self._category_edit.text().strip():
            self._run_search()

    def _update_libraries_button_label(self) -> None:
        tr = self._translator.tr
        if self._multi_library_selection is None:
            self._libraries_button.setText(tr("search-libraries-button"))
        else:
            self._libraries_button.setText(
                tr("search-libraries-count").format(count=len(self._multi_library_selection))
            )

    def _effective_library_filter(self) -> str | tuple[str, ...] | None:
        """Return the real library filter to search/browse with - the
        multi-library scope picker's selection when active, otherwise
        whatever the plain single-library combo shows."""
        if self._multi_library_selection is not None:
            return self._multi_library_selection
        library = self._library_combo.currentText()
        return None if library == self._translator.tr("all-libraries") else library

    def _run_search(self) -> None:
        query = self._query_edit.text().strip()
        self._clear_results()
        self._status_is_idle = False

        library = self._effective_library_filter()
        author = self._author_edit.text().strip() or None
        category = self._category_edit.text().strip() or None
        exact = self._exact_match_checkbox.isChecked()
        scope = self._scope_combo.currentData()
        search_target = self._search_target_combo.currentData()  # "both" | "title" | "content"
        match_mode = self._match_mode_combo.currentData()  # "all" | "any" | "phrase"

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
        match_query = _apply_match_mode(query, match_mode)

        # Book-name search and content search each run only when the real
        # "Search in" choice includes them - "Name + content" (the default)
        # runs both and shows two clearly labeled groups, title matches
        # first since that's usually what a name-shaped query means.
        title_matches: tuple[BookSummary, ...] = ()
        if search_target in ("title", "both"):
            title_matches = self._browser.search_by_title(
                match_query, DEFAULT_LIMIT, library, author, category, exact
            )

        results: tuple[SearchResult, ...] = ()
        if search_target in ("content", "both"):
            try:
                results = self._search_service.search(
                    match_query, DEFAULT_LIMIT, library, author, category, exact, scope
                )
            except BookSearchError:
                self._status_label.setText(self._translator.tr("search-error-could-not-run"))
                return
            except ValueError:
                self._status_label.setText(self._translator.tr("search-error-enter-term"))
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
                self._translator.tr("search-status-no-matches-checking-related").format(query=query)
                if semantic_will_run
                else self._translator.tr("search-status-no-matches").format(query=query)
            )
            self._status_label.setText(status)
        else:
            status_bits = []
            if title_matches:
                status_bits.append(
                    self._translator.tr("search-status-title-matches").format(count=len(title_matches))
                )
            if content_search_active:
                status_bits.append(
                    self._translator.tr("search-status-content-results").format(count=len(results))
                )
            self._status_label.setText(", ".join(status_bits))

        if title_matches:
            self._results_layout.insertWidget(
                self._results_layout.count() - 1, _pane_title(self._translator.tr("search-matching-titles"))
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
                self._status_label.setText(
                    self._translator.tr("search-status-no-matches").format(query=self._current_query)
                )
            return

        status_bits = []
        if self._current_title_count:
            status_bits.append(
                self._translator.tr("search-status-title-matches").format(count=self._current_title_count)
            )
        status_bits.append(
            self._translator.tr("search-status-content-results").format(count=self._current_content_count)
        )
        status_bits.append(
            self._translator.tr("search-status-related-pages").format(count=len(semantic_results))
        )
        self._status_label.setText(", ".join(status_bits))

        self._results_layout.insertWidget(
            self._results_layout.count() - 1, _pane_title(self._translator.tr("search-related-pages-heading"))
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
            self._status_label.setText(self._translator.tr("search-no-microphone"))
            return
        audio_format = QAudioFormat()
        audio_format.setSampleRate(VOICE_SEARCH_SAMPLE_RATE)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(audio_format):
            self._status_label.setText(self._translator.tr("search-mic-format-unsupported"))
            return

        self._audio_buffer = bytearray()
        source = QAudioSource(device, audio_format, self)
        io_device = source.start()
        if io_device is None:
            self._status_label.setText(self._translator.tr("search-mic-start-failed"))
            return
        io_device.readyRead.connect(self._on_audio_data_ready)
        self._audio_source = source
        self._audio_io_device = io_device
        self._mic_button.setIcon(button_icon("mic", DANGER))
        self._mic_button.setToolTip(self._translator.tr("search-mic-recording-tooltip"))
        self._status_label.setText(self._translator.tr("search-mic-listening"))
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
        self._mic_button.setToolTip(self._translator.tr("search-mic-tooltip"))
        self._status_label.setText(self._translator.tr("search-mic-transcribing"))
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
        self._status_label.setText(self._translator.tr("search-mic-transcribe-failed"))

    def _on_save_search_clicked(self) -> None:
        """Save the current real query + every real active filter, so
        re-running it later reproduces the exact same search - only
        possible once a real search has actually run (`_current_query`
        is empty otherwise)."""
        if not self._current_query:
            QMessageBox.information(
                self,
                self._translator.tr("search-save-search-tooltip"),
                self._translator.tr("search-save-search-run-first"),
            )
            return
        name, confirmed = QInputDialog.getText(
            self,
            self._translator.tr("search-save-search-tooltip"),
            self._translator.tr("search-save-search-name-prompt"),
        )
        if not confirmed or not name.strip():
            return
        library = self._library_combo.currentText()
        library = None if library == self._translator.tr("all-libraries") else library
        try:
            self._saved_searches.save_search(
                name,
                self._current_query,
                library,
                self._author_edit.text().strip() or None,
                self._category_edit.text().strip() or None,
                self._exact_match_checkbox.isChecked(),
                self._scope_combo.currentData(),
                self._search_target_combo.currentData(),
            )
        except SavedSearchNameTakenError as error:
            QMessageBox.warning(self, self._translator.tr("search-save-search-tooltip"), str(error))

    def _on_view_saved_searches_clicked(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(self._translator.tr("search-saved-searches-tooltip"))
        dialog.resize(420, 360)
        layout = QVBoxLayout(dialog)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area, stretch=1)
        close_button = QPushButton(self._translator.tr("common-close"))
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        def _refresh() -> None:
            content = QWidget()
            content_layout = QVBoxLayout(content)
            saved_searches = self._saved_searches.list_searches()
            if not saved_searches:
                content_layout.addWidget(QLabel(self._translator.tr("search-saved-searches-empty")))
            for saved in saved_searches:
                content_layout.addWidget(_build_saved_search_row(saved, self._translator, _run, _delete))
            content_layout.addStretch(1)
            scroll_area.setWidget(content)

        def _run(saved: SavedSearch) -> None:
            dialog.close()
            self._run_saved_search(saved)

        def _delete(saved_search_id: int) -> None:
            self._saved_searches.delete_search(saved_search_id)
            _refresh()

        _refresh()
        dialog.exec()

    def _run_saved_search(self, saved: SavedSearch) -> None:
        """Repopulate every real filter from a saved search, then run it -
        signals on the auto-rerunning filter widgets are blocked while
        restoring so this fires exactly one real search, not one per
        widget touched along the way."""
        self._query_edit.setText(saved.query)
        if saved.library is not None:
            index = self._library_combo.findText(saved.library)
            self._library_combo.setCurrentIndex(index if index >= 0 else 0)
        else:
            self._library_combo.setCurrentIndex(0)
        self._author_edit.setText(saved.author or "")
        self._category_edit.setText(saved.category or "")

        for widget in (self._exact_match_checkbox, self._scope_combo, self._search_target_combo):
            widget.blockSignals(True)
        try:
            self._exact_match_checkbox.setChecked(saved.exact)
            scope_index = self._scope_combo.findData(saved.scope)
            if scope_index >= 0:
                self._scope_combo.setCurrentIndex(scope_index)
            target_index = self._search_target_combo.findData(saved.search_target)
            if target_index >= 0:
                self._search_target_combo.setCurrentIndex(target_index)
        finally:
            for widget in (self._exact_match_checkbox, self._scope_combo, self._search_target_combo):
                widget.blockSignals(False)
        self._run_search()

    def _browse_by_filters(
        self, library: str | None, author: str | None, category: str | None
    ) -> None:
        """Browse straight to books matching Author/Category/Library filters alone."""
        summaries = self._browser.list_books_by_filters(library, author, category)
        heading_bits = []
        if author:
            heading_bits.append(self._translator.tr("search-filter-bit-author").format(author=author))
        if category:
            heading_bits.append(self._translator.tr("search-filter-bit-category").format(category=category))
        if library:
            heading_bits.append(self._translator.tr("search-filter-bit-library").format(library=library))
        self._browse(
            summaries,
            self._translator.tr("search-heading-matching-prefix") + ", ".join(heading_bits),
        )

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

        title = QLabel(result.title or self._translator.tr("common-untitled"))
        title.setStyleSheet(f"font-size: {Type.BODY_LG}px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [
            result.author or self._translator.tr("common-unknown-author"),
            result.library or self._translator.tr("common-unknown-library"),
        ]
        if result.page_number is not None:
            meta_bits.append(self._translator.tr("search-meta-page").format(page=result.page_number))
        if result.source == "footnote":
            meta_bits.append(self._translator.tr("search-meta-footnote-match"))
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

        title = QLabel(result.title or self._translator.tr("common-untitled"))
        title.setStyleSheet(f"font-size: {Type.BODY_LG}px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [
            result.author or self._translator.tr("common-unknown-author"),
            result.library or self._translator.tr("common-unknown-library"),
        ]
        if result.page_number is not None:
            meta_bits.append(self._translator.tr("search-meta-page").format(page=result.page_number))
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

        title = QLabel(summary.title or self._translator.tr("common-untitled"))
        title.setStyleSheet(f"font-size: {Type.BODY_LG}px; font-weight: 600; {RTL_TEXT_STYLE}")
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        card_layout.addWidget(title)

        meta_bits = [
            summary.author or self._translator.tr("common-unknown-author"),
            summary.library or self._translator.tr("common-unknown-library"),
        ]
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
        # Real bug fixed here: when the file wasn't found on disk right now
        # (e.g. an external drive isn't plugged in), this button used to
        # just not appear at all - indistinguishable from "no PDF was ever
        # recorded for this book." A real Source is still evidence a PDF
        # should exist, so the button stays, and clicking it while the
        # file's genuinely missing tells the user exactly where to put it
        # back instead of the app looking like it forgot the book existed.
        expected_pdf_path = candidate_pdf_path(source[1], source[0], self._maknoon_pdf_folder)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 0)
        if expected_pdf_path is not None:
            pdf_button = QPushButton(self._translator.tr("search-open-pdf"))
            pdf_button.setObjectName("resultCardOpenPdfButton")
            pdf_button.setIcon(button_icon("open-pdf"))
            pdf_button.setIconSize(button_icon_size())
            pdf_button.clicked.connect(
                lambda: self._open_or_report_missing_pdf(expected_pdf_path)
            )
            row_layout.addWidget(pdf_button)

        target_page = page_number or 1
        read_button = QPushButton(self._translator.tr("common-read-in-app"))
        read_button.setObjectName("resultCardReadButton")
        read_button.setIcon(button_icon("viewer"))
        read_button.setIconSize(button_icon_size())
        read_button.clicked.connect(
            lambda: self.open_in_viewer_requested.emit(book_id, target_page)
        )
        row_layout.addWidget(read_button)

        details_button = QPushButton(self._translator.tr("search-details-button"))
        details_button.setObjectName("resultCardDetailsButton")
        details_button.clicked.connect(lambda: self._show_details(book_id, page_number))
        row_layout.addWidget(details_button)

        citation_button = QPushButton(self._translator.tr("viewer-copy-citation"))
        citation_button.setObjectName("resultCardCitationButton")
        citation_button.setToolTip(self._translator.tr("search-copy-citation-tooltip"))
        citation_button.clicked.connect(
            lambda: self._copy_card_citation(book_id, page_number)
        )
        row_layout.addWidget(citation_button)

        row_layout.addStretch(1)
        return row

    def _open_or_report_missing_pdf(self, expected_path: Path) -> None:
        """Open a book's real PDF, or explain exactly where it's missing from.

        Re-checks on disk at click time (not just whatever was true when
        the card was built) - the drive it lives on may have been plugged
        in since. Real bug fixed here: this used to just do nothing when
        the file wasn't found, with no message at all.
        """
        if expected_path.is_file():
            QDesktopServices.openUrl(_file_url(expected_path))
            return
        QMessageBox.warning(
            self,
            self._translator.tr("pdf-missing-title"),
            self._translator.tr("pdf-missing-message").format(path=expected_path),
        )

    def _retranslate_result_cards(self) -> None:
        """Refresh already-rendered result cards' button text in place.

        Real bug fixed here: these cards are only ever (re)built by a new
        search/browse action, not by `_retranslate()` - switching the app
        language with results already on screen left every visible card's
        action buttons (Copy/Details/Read in app/Open PDF) stuck in
        whatever language was active when that card was first built.
        Walking the existing widgets and resetting their text is cheap and
        avoids re-running the real search/browse query (which would also
        double-record it in Recent Searches) just to relabel buttons.
        """
        for object_name, key in (
            ("resultCardOpenPdfButton", "search-open-pdf"),
            ("resultCardReadButton", "common-read-in-app"),
            ("resultCardDetailsButton", "search-details-button"),
        ):
            for button in self._results_container.findChildren(QPushButton, object_name):
                button.setText(self._translator.tr(key))
        for button in self._results_container.findChildren(QPushButton, "resultCardCitationButton"):
            button.setText(self._translator.tr("viewer-copy-citation"))
            button.setToolTip(self._translator.tr("search-copy-citation-tooltip"))

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

    @property
    def is_collapsed(self) -> bool:
        """Whether this whole screen (as a `WorkspaceScreen` splitter
        segment) is currently collapsed."""
        return self._collapsed

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state and notify listeners (the owning
        `WorkspaceScreen`'s splitter) if it actually changed - mirrors
        `AiAssistantPanel.set_collapsed()` exactly."""
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._collapse_self_button.setIcon(button_icon("next" if collapsed else "prev"))
        self.collapsed_changed.emit(collapsed)

    def _show_detail_empty_state(self) -> None:
        """The detail pane before anything is selected - real content in
        both halves, not one long blank rectangle: the top half explains
        what will show up here once a result is selected, the bottom
        half is a real, working quick-start into the AI Agent (reused,
        not duplicated - see `_on_quick_ask_clicked`) so the otherwise-
        idle space does something useful.
        """
        self._detail_panel_is_empty = True
        self._detail_layout.addWidget(
            EmptyStateLabel(self._translator.tr("search-detail-empty-state"), centered=True),
            stretch=1,
        )

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        self._detail_layout.addWidget(divider)

        quick_ask_container = QWidget()
        quick_ask_layout = QVBoxLayout(quick_ask_container)
        quick_ask_layout.setContentsMargins(0, 0, 0, 0)
        quick_ask_layout.setSpacing(Spacing.XS)
        heading = _pane_title(self._translator.tr("search-quick-ask-heading"))
        quick_ask_layout.addWidget(heading)
        self._quick_ask_edit = QLineEdit()
        self._quick_ask_edit.setPlaceholderText(
            self._translator.tr("search-quick-ask-placeholder")
        )
        self._quick_ask_edit.returnPressed.connect(self._on_quick_ask_clicked)
        quick_ask_layout.addWidget(self._quick_ask_edit)
        self._quick_ask_button = QPushButton(self._translator.tr("search-quick-ask-button"))
        self._quick_ask_button.setObjectName("primaryButton")
        self._quick_ask_button.clicked.connect(self._on_quick_ask_clicked)
        quick_ask_layout.addWidget(self._quick_ask_button)
        self._detail_layout.addWidget(quick_ask_container, stretch=1)

    def _on_quick_ask_clicked(self) -> None:
        question = self._quick_ask_edit.text().strip()
        if not question:
            return
        self._quick_ask_edit.clear()
        self.ai_quick_ask_requested.emit(question)

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
        self._detail_panel_is_empty = False
        self._clear_detail_panel()
        self._populate_detail_panel(metadata, page_number)

    def _clear_detail_panel(self) -> None:
        while self._detail_layout.count():
            item = self._detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _populate_detail_panel(self, metadata: BookMetadata, page_number: int | None) -> None:
        tr = self._translator.tr
        title = QLabel(metadata.title or tr("common-untitled"))
        title.setWordWrap(True)
        title.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; {RTL_TEXT_STYLE}")
        self._detail_layout.addWidget(title)

        rows: list[tuple[str, str | None]] = [
            (tr("search-detail-author"), metadata.author),
            (tr("search-detail-publisher"), metadata.publisher),
            (tr("search-detail-language"), metadata.language),
            (tr("search-detail-category"), metadata.category),
            (tr("search-detail-library"), metadata.library),
        ]
        if metadata.series_title:
            series_text = metadata.series_title
            if metadata.volume_number is not None:
                series_text += tr("search-detail-volume-suffix").format(volume=metadata.volume_number)
            rows.append((tr("search-detail-series"), series_text))
        rows.append((tr("search-detail-pages"), str(metadata.page_count)))
        rows.append((tr("search-detail-chapters"), str(metadata.chapter_count)))
        if page_number is not None:
            rows.append((tr("search-detail-matched-page"), str(page_number)))

        for label_text, value in rows:
            self._detail_layout.addWidget(_detail_row(label_text, value, tr("common-unknown")))

        self._detail_layout.addWidget(_pane_title(tr("search-your-rating")))
        self._rating_combo = QComboBox()
        self._rating_combo.addItem(tr("search-not-rated"), None)
        for value in range(1, 6):
            self._rating_combo.addItem("★" * value, value)
        current_rating = self._ratings.get_rating(metadata.book_id)
        self._rating_combo.setCurrentIndex(max(self._rating_combo.findData(current_rating), 0))
        self._rating_combo.currentIndexChanged.connect(
            lambda _index, book_id=metadata.book_id: self._on_rating_changed(book_id)
        )
        self._detail_layout.addWidget(self._rating_combo)

        open_viewer_button = QPushButton(tr("search-open-in-viewer"))
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
            expected_pdf_path = candidate_pdf_path(source[1], source[0], self._maknoon_pdf_folder)
            if expected_pdf_path is not None:
                pdf_button = QPushButton(tr("search-open-source-pdf"))
                pdf_button.setIcon(button_icon("open-pdf"))
                pdf_button.setIconSize(button_icon_size())
                pdf_button.clicked.connect(
                    lambda: self._open_or_report_missing_pdf(expected_pdf_path)
                )
                self._detail_layout.addWidget(pdf_button)

        self._detail_layout.addStretch(1)


def _build_saved_search_row(
    saved: SavedSearch,
    translator: Translator,
    on_run,
    on_delete,
) -> QWidget:
    """One real saved search's row in the Saved Searches dialog - its
    name, a Run action, and a Delete action."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    name_label = QLabel(saved.name)
    name_label.setWordWrap(True)
    layout.addWidget(name_label, stretch=1)
    run_button = QPushButton(translator.tr("common-run"))
    run_button.clicked.connect(lambda: on_run(saved))
    layout.addWidget(run_button)
    delete_button = QPushButton(translator.tr("common-delete"))
    delete_button.clicked.connect(lambda: on_delete(saved.saved_search_id))
    layout.addWidget(delete_button)
    return row


def _pane_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px; font-weight: 600; margin-top: 6px;"
    )
    return label


def _detail_row(label_text: str, value: str | None, unknown_text: str) -> QWidget:
    row = QWidget()
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    caption = QLabel(label_text)
    caption.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px;")
    layout.addWidget(caption)
    value_label = QLabel(value or unknown_text)
    value_label.setWordWrap(True)
    value_label.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    layout.addWidget(value_label)
    return row


def _category_tree_item(node: CategoryNode, language: str) -> QTreeWidgetItem:
    display_name = translated_category_name(node.name, language)
    item = QTreeWidgetItem([f"{display_name}  ({node.book_count})"])
    # UserRole stays the raw canonical name (never the translated display
    # text) - it's what `_on_category_clicked` passes straight into
    # `list_books_in_category()`, which filters on the real `Categories.Name`.
    item.setData(0, Qt.ItemDataRole.UserRole, node.name)
    for child in node.children:
        item.addChild(_category_tree_item(child, language))
    return item


def _flatten_categories(nodes: tuple[CategoryNode, ...]) -> list[CategoryNode]:
    """Flatten a category tree into a single list, for completer suggestions."""
    flat: list[CategoryNode] = []
    for node in nodes:
        flat.append(node)
        flat.extend(_flatten_categories(node.children))
    return flat


def _apply_match_mode(query: str, mode: str) -> str:
    """Turn a plain typed query into the real FTS5 MATCH syntax for the
    chosen word-combination mode - a friendly UI over syntax that
    already works if typed by hand (a quoted "phrase" or AND/OR/NOT,
    see search_by_title()'s own docstring), for a user who doesn't know
    that syntax exists.

    "all" (the default) returns the query unchanged - FTS5 already
    ANDs space-separated terms implicitly, so this mode is a pure
    no-op, not a real transformation, and matches every search call
    site's pre-existing behavior exactly.
    """
    if mode == "any":
        terms = query.split()
        return " OR ".join(terms) if len(terms) > 1 else query
    if mode == "phrase":
        return f'"{query.replace(chr(34), "")}"'
    return query


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
