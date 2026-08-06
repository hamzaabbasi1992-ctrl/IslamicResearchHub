"""Home screen: a research dashboard landing page.

Every section is real, backed by data that already existed - `Continue
Reading`/`Recent Searches`/`Statistics` were already wired; `Bookmarks`
(`BookmarkRepository.list_recent_bookmarks`), `Recently Viewed Authors`
(derived in this file from `RecentBookRepository.list_recent()`'s
existing `author` field - no new query), `Recently Viewed Categories`
(`RecentBookRepository.list_recent_categories`, one new read-only JOIN),
and `Library Health` (the existing `DatabaseVerifier`, run on demand via
a button rather than on every `refresh()` - it does real integrity scans
across every table, too expensive to run implicitly) are new consumers
of real data, not new persistence. `Pinned Books`/`Research Projects`/
`Collections` stay honest placeholders: no pin/project/rated-books-list
concept exists anywhere in the schema, and fabricating one would mean
new persistence-layer methods, out of scope for a UI-only refactor.
Recently Imported stays session-only (no `ImportedAt` column exists).
"""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.domain.models.book_summary import BookSummary
from islamic_research_hub.domain.models.recent_bookmark import RecentBookmark
from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
    BookBrowserRepository,
)
from islamic_research_hub.infrastructure.persistence.bookmark_repository import (
    BookmarkRepository,
)
from islamic_research_hub.domain.models.verification_report import VerificationReport
from islamic_research_hub.infrastructure.persistence.database_verifier import DatabaseVerifier
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (
    RecentBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.i18n import (
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
    Translator,
)
from islamic_research_hub.interfaces.desktop_app.list_row_button import list_row_button
from islamic_research_hub.interfaces.desktop_app.search_history import RecentSearchStore
from islamic_research_hub.interfaces.desktop_app.theme import (
    INK,
    MUTED_LABEL_STYLE,
    Spacing,
    Type,
)

_MAX_LISTED_ITEMS = 5
_GRID_COLUMNS = 3
_CARD_MIN_HEIGHT = 180
"""Tall enough for a heading + up to _MAX_LISTED_ITEMS real list rows -
the tallest real card content on this screen."""

_CARD_KEYS = (
    "home-card-continue-reading",
    "home-card-bookmarks",
    "home-card-recent-searches",
    "home-card-statistics",
    "home-card-recent-authors",
    "home-card-recent-categories",
    "home-card-recently-imported",
    "home-card-library-health",
    "home-card-collections",
    "home-card-pinned-books",
    "home-card-ai-suggestions",
)


class HomeScreen(QWidget):
    """Research dashboard: real per-item sections backed by real data,
    honest placeholders where no backend exists - see module docstring."""

    open_in_viewer_requested = Signal(int, int)  # book_id, page_number

    def __init__(
        self,
        database_path: Path,
        translator: Translator,
        browser: BookBrowserRepository | None = None,
        recent_books: RecentBookRepository | None = None,
        bookmarks: BookmarkRepository | None = None,
        recent_search_store: RecentSearchStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._translator = translator
        self._browser = browser or BookBrowserRepository(database_path)
        self._recent_books = recent_books or RecentBookRepository(database_path)
        self._bookmarks = bookmarks or BookmarkRepository(database_path)
        self._recent_searches = recent_search_store or RecentSearchStore(
            QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        )
        self._imported_this_session: list[str] = []
        self._health_report: VerificationReport | None = None
        self._card_headings: dict[str, QLabel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Real bug fixed here: ~10 real dashboard cards in a grid, with no
        # QScrollArea anywhere on this screen - on a real (non-huge)
        # window this clipped the bottom cards with no way to reach them,
        # the same "hidden content, no way to scroll" bug already fixed on
        # SettingsScreen.
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        outer = QVBoxLayout(content)
        outer.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        outer.setSpacing(Spacing.SM)

        self._heading = QLabel(self._translator.tr("home-heading"))
        self._heading.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {INK};")
        outer.addWidget(self._heading)

        self._grid = QGridLayout()
        self._grid.setSpacing(Spacing.MD)
        outer.addLayout(self._grid)
        outer.addStretch(1)

        # Clickable-rows cards (real per-item QPushButton rows via _set_card_rows):
        self._continue_reading_body = self._add_card("home-card-continue-reading", is_list=True)
        self._bookmarks_body = self._add_card("home-card-bookmarks", is_list=True)
        # Plain-text cards (joined-line QLabel via _set_text_lines):
        self._recent_searches_body = self._add_card("home-card-recent-searches")
        self._statistics_body = self._add_card("home-card-statistics")
        self._recent_authors_body = self._add_card("home-card-recent-authors")
        self._recent_categories_body = self._add_card("home-card-recent-categories")
        self._recently_imported_body = self._add_card("home-card-recently-imported")
        self._library_health_body, self._check_health_button = self._add_health_card()
        self._collections_body = self._add_card(
            "home-card-collections", initial_text_key="home-placeholder-collections"
        )
        self._pinned_books_body = self._add_card(
            "home-card-pinned-books", initial_text_key="home-placeholder-pinned-books"
        )
        self._ai_suggestions_body = self._add_card(
            "home-card-ai-suggestions", initial_text_key="home-placeholder-ai-suggestions"
        )

        scroll_area.setWidget(content)
        root.addWidget(scroll_area)

        self.refresh()
        self._translator.language_changed.connect(self._retranslate)

    def _retranslate(self, _language: str) -> None:
        """Update this screen's own labels after the app language changes."""
        self._heading.setText(self._translator.tr("home-heading"))
        for key in _CARD_KEYS:
            self._card_headings[key].setText(self._translator.tr(key))
        self._check_health_button.setText(self._translator.tr("home-check-now"))
        self._collections_body.setText(self._translator.tr("home-placeholder-collections"))
        self._pinned_books_body.setText(self._translator.tr("home-placeholder-pinned-books"))
        self._ai_suggestions_body.setText(self._translator.tr("home-placeholder-ai-suggestions"))
        self._render_health_body()
        self.refresh()

    def refresh(self) -> None:
        """Reload every real-data section from the database/settings."""
        recent_books = self._recent_books.list_recent(limit=_MAX_LISTED_ITEMS)
        self._set_card_rows(
            self._continue_reading_body,
            [(_book_line(self._translator, book), book.book_id, None) for book in recent_books],
            self._translator.tr("home-empty-recent-books"),
        )

        recent_queries = self._recent_searches.list_recent()[:_MAX_LISTED_ITEMS]
        self._set_text_lines(
            self._recent_searches_body, recent_queries, self._translator.tr("home-empty-recent-searches")
        )

        stats = self._browser.get_header_stats()
        self._set_text_lines(
            self._statistics_body,
            [
                self._translator.tr("home-stats-books").format(count=stats.book_count),
                self._translator.tr("home-stats-libraries").format(count=stats.library_count),
                self._translator.tr("home-stats-authors").format(count=stats.author_count),
            ],
            "",
        )

        recent_bookmarks = self._bookmarks.list_recent_bookmarks(limit=_MAX_LISTED_ITEMS)
        self._set_card_rows(
            self._bookmarks_body,
            [
                (_bookmark_line(self._translator, bookmark), bookmark.book_id, bookmark.page_number)
                for bookmark in recent_bookmarks
            ],
            self._translator.tr("home-empty-bookmarks"),
        )

        recent_authors = list(
            dict.fromkeys(
                book.author for book in recent_books if book.author
            )
        )[:_MAX_LISTED_ITEMS]
        self._set_text_lines(
            self._recent_authors_body, recent_authors, self._translator.tr("home-empty-recent-authors")
        )

        recent_categories = self._recent_books.list_recent_categories(limit=_MAX_LISTED_ITEMS)
        self._set_text_lines(
            self._recent_categories_body,
            recent_categories,
            self._translator.tr("home-empty-recent-categories"),
        )

        self._set_text_lines(
            self._recently_imported_body,
            self._imported_this_session,
            self._translator.tr("home-empty-recently-imported"),
        )

    def note_library_imported(self, library_name: str) -> None:
        """Record a library imported during this run (session-only - see
        module docstring on why this isn't a persisted import history)."""
        self._imported_this_session.insert(0, library_name)
        self.refresh()

    def _check_library_health(self) -> None:
        """Run the real integrity checks on demand - a genuine table-scan
        cost, not something to repeat on every dashboard refresh."""
        self._health_report = DatabaseVerifier(self._database_path).verify()
        self._render_health_body()

    def _render_health_body(self) -> None:
        if self._health_report is None:
            self._library_health_body.setText(self._translator.tr("home-library-health-idle"))
        elif not self._health_report.issues:
            self._library_health_body.setText(self._translator.tr("home-library-health-healthy"))
        else:
            self._library_health_body.setText(
                self._translator.tr("home-library-health-issues").format(
                    errors=self._health_report.error_count,
                    warnings=self._health_report.warning_count,
                )
            )

    def _add_card(
        self,
        title_key: str,
        is_list: bool = False,
        initial_text_key: str | None = None,
    ) -> QVBoxLayout | QLabel:
        card, layout = self._new_card(title_key)
        if is_list:
            body_layout = QVBoxLayout()
            body_layout.setSpacing(2)
            layout.addLayout(body_layout)
            self._place_card(card)
            return body_layout
        body = QLabel(self._translator.tr(initial_text_key) if initial_text_key else "")
        body.setStyleSheet(MUTED_LABEL_STYLE)
        body.setWordWrap(True)
        layout.addWidget(body)
        self._place_card(card)
        return body

    def _add_health_card(self) -> tuple[QLabel, QPushButton]:
        card, layout = self._new_card("home-card-library-health")
        body = QLabel(self._translator.tr("home-library-health-idle"))
        body.setStyleSheet(MUTED_LABEL_STYLE)
        body.setWordWrap(True)
        layout.addWidget(body)
        button = QPushButton(self._translator.tr("home-check-now"))
        button.clicked.connect(self._check_library_health)
        layout.addWidget(button)
        self._place_card(card)
        return body, button

    def _new_card(self, title_key: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        # Real UI fix: cards had no shared height floor, so a card with
        # up to 5 real list rows towered over a card with one short
        # placeholder line - a visibly uneven, unfinished-looking grid.
        # A consistent minimum height (tall enough for the tallest real
        # card content) makes every row of the grid line up.
        card.setMinimumHeight(_CARD_MIN_HEIGHT)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(Spacing.SM, Spacing.SM, Spacing.SM, Spacing.SM)
        layout.setSpacing(Spacing.XS)
        heading = QLabel(self._translator.tr(title_key))
        heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        layout.addWidget(heading)
        self._card_headings[title_key] = heading
        return card, layout

    def _place_card(self, card: QFrame) -> None:
        index = self._grid.count()
        self._grid.addWidget(card, index // _GRID_COLUMNS, index % _GRID_COLUMNS)

    def _set_text_lines(
        self, body: QLabel, lines: "list[str] | tuple[str, ...]", empty_text: str
    ) -> None:
        body.setText("\n".join(lines) if lines else empty_text)

    def _set_card_rows(
        self,
        body_layout: QVBoxLayout,
        rows: list[tuple[str, int, int | None]],
        empty_text: str,
    ) -> None:
        """Fill a card's body with real, clickable per-item rows."""
        while body_layout.count():
            item = body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not rows:
            body_layout.addWidget(EmptyStateLabel(empty_text))
            return
        for text, book_id, page_number in rows:
            button = list_row_button(text, object_name="authorRow")
            # Typography fix: real Arabic/Urdu book titles need RTL layout
            # direction, matching every other book-title row in the app
            # (search_screen.py's authorRow buttons already do this).
            button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            button.clicked.connect(
                lambda _checked, bid=book_id, page=page_number: self.open_in_viewer_requested.emit(
                    bid, page or 1
                )
            )
            body_layout.addWidget(button)


def _book_line(translator: Translator, book: BookSummary) -> str:
    title = book.title or translator.tr("home-untitled")
    return f"{title} - {book.author}" if book.author else title


def _bookmark_line(translator: Translator, bookmark: RecentBookmark) -> str:
    title = bookmark.title or translator.tr("home-untitled")
    return translator.tr("home-bookmark-line").format(title=title, page=bookmark.page_number)
