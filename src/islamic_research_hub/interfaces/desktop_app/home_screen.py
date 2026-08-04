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
from islamic_research_hub.infrastructure.persistence.database_verifier import DatabaseVerifier
from islamic_research_hub.infrastructure.persistence.recent_book_repository import (
    RecentBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.i18n import (
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
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

_NO_RECENT_BOOKS_TEXT = "No books opened yet - search for one to get started."
_NO_RECENT_SEARCHES_TEXT = "No searches yet."
_NO_BOOKMARKS_TEXT = "No bookmarks yet - open a book and bookmark a page."
_NO_RECENT_AUTHORS_TEXT = "No books opened yet."
_NO_RECENT_CATEGORIES_TEXT = "No books opened yet."
_NO_IMPORTS_THIS_SESSION_TEXT = "No libraries imported this session yet."
_COLLECTIONS_PLACEHOLDER_TEXT = (
    "Browsing your rated/bookmarked books isn't available yet - "
    "open a book to rate or bookmark it."
)
_PINNED_BOOKS_PLACEHOLDER_TEXT = "Pinning books isn't available yet."
_AI_SUGGESTIONS_PLACEHOLDER_TEXT = (
    "Open a book to see related suggestions in the Assistant panel."
)
_LIBRARY_HEALTH_IDLE_TEXT = "Not checked yet this session."


class HomeScreen(QWidget):
    """Research dashboard: real per-item sections backed by real data,
    honest placeholders where no backend exists - see module docstring."""

    open_in_viewer_requested = Signal(int, int)  # book_id, page_number

    def __init__(
        self,
        database_path: Path,
        browser: BookBrowserRepository | None = None,
        recent_books: RecentBookRepository | None = None,
        bookmarks: BookmarkRepository | None = None,
        recent_search_store: RecentSearchStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._database_path = database_path
        self._browser = browser or BookBrowserRepository(database_path)
        self._recent_books = recent_books or RecentBookRepository(database_path)
        self._bookmarks = bookmarks or BookmarkRepository(database_path)
        self._recent_searches = recent_search_store or RecentSearchStore(
            QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
        )
        self._imported_this_session: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        outer.setSpacing(Spacing.SM)

        heading = QLabel("Home")
        heading.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {INK};")
        outer.addWidget(heading)

        self._grid = QGridLayout()
        self._grid.setSpacing(Spacing.MD)
        outer.addLayout(self._grid)
        outer.addStretch(1)

        # Clickable-rows cards (real per-item QPushButton rows via _set_card_rows):
        self._continue_reading_body = self._add_card("Continue Reading", is_list=True)
        self._bookmarks_body = self._add_card("Bookmarks", is_list=True)
        # Plain-text cards (joined-line QLabel via _set_text_lines):
        self._recent_searches_body = self._add_card("Recent Searches")
        self._statistics_body = self._add_card("Statistics")
        self._recent_authors_body = self._add_card("Recently Viewed Authors")
        self._recent_categories_body = self._add_card("Recently Viewed Categories")
        self._recently_imported_body = self._add_card("Recently Imported")
        self._library_health_body, self._check_health_button = self._add_health_card()
        self._collections_body = self._add_card(
            "Collections", initial_text=_COLLECTIONS_PLACEHOLDER_TEXT
        )
        self._pinned_books_body = self._add_card(
            "Pinned Books", initial_text=_PINNED_BOOKS_PLACEHOLDER_TEXT
        )
        self._ai_suggestions_body = self._add_card(
            "AI Suggestions", initial_text=_AI_SUGGESTIONS_PLACEHOLDER_TEXT
        )

        self.refresh()

    def refresh(self) -> None:
        """Reload every real-data section from the database/settings."""
        recent_books = self._recent_books.list_recent(limit=_MAX_LISTED_ITEMS)
        self._set_card_rows(
            self._continue_reading_body,
            [(_book_line(book), book.book_id, None) for book in recent_books],
            _NO_RECENT_BOOKS_TEXT,
        )

        recent_queries = self._recent_searches.list_recent()[:_MAX_LISTED_ITEMS]
        self._set_text_lines(
            self._recent_searches_body, recent_queries, _NO_RECENT_SEARCHES_TEXT
        )

        stats = self._browser.get_header_stats()
        self._set_text_lines(
            self._statistics_body,
            [
                f"{stats.book_count} books",
                f"{stats.library_count} libraries",
                f"{stats.author_count} authors",
            ],
            "",
        )

        recent_bookmarks = self._bookmarks.list_recent_bookmarks(limit=_MAX_LISTED_ITEMS)
        self._set_card_rows(
            self._bookmarks_body,
            [
                (_bookmark_line(bookmark), bookmark.book_id, bookmark.page_number)
                for bookmark in recent_bookmarks
            ],
            _NO_BOOKMARKS_TEXT,
        )

        recent_authors = list(
            dict.fromkeys(
                book.author for book in recent_books if book.author
            )
        )[:_MAX_LISTED_ITEMS]
        self._set_text_lines(
            self._recent_authors_body, recent_authors, _NO_RECENT_AUTHORS_TEXT
        )

        recent_categories = self._recent_books.list_recent_categories(limit=_MAX_LISTED_ITEMS)
        self._set_text_lines(
            self._recent_categories_body, recent_categories, _NO_RECENT_CATEGORIES_TEXT
        )

        self._set_text_lines(
            self._recently_imported_body,
            self._imported_this_session,
            _NO_IMPORTS_THIS_SESSION_TEXT,
        )

    def note_library_imported(self, library_name: str) -> None:
        """Record a library imported during this run (session-only - see
        module docstring on why this isn't a persisted import history)."""
        self._imported_this_session.insert(0, library_name)
        self.refresh()

    def _check_library_health(self) -> None:
        """Run the real integrity checks on demand - a genuine table-scan
        cost, not something to repeat on every dashboard refresh."""
        report = DatabaseVerifier(self._database_path).verify()
        if not report.issues:
            self._library_health_body.setText("Healthy - no issues found.")
        else:
            self._library_health_body.setText(
                f"{report.error_count} error(s), {report.warning_count} warning(s) found."
            )

    def _add_card(
        self,
        title: str,
        is_list: bool = False,
        initial_text: str = "",
    ) -> QVBoxLayout | QLabel:
        card, layout = self._new_card(title)
        if is_list:
            body_layout = QVBoxLayout()
            body_layout.setSpacing(2)
            layout.addLayout(body_layout)
            self._place_card(card)
            return body_layout
        body = QLabel(initial_text)
        body.setStyleSheet(MUTED_LABEL_STYLE)
        body.setWordWrap(True)
        layout.addWidget(body)
        self._place_card(card)
        return body

    def _add_health_card(self) -> tuple[QLabel, QPushButton]:
        card, layout = self._new_card("Library Health")
        body = QLabel(_LIBRARY_HEALTH_IDLE_TEXT)
        body.setStyleSheet(MUTED_LABEL_STYLE)
        body.setWordWrap(True)
        layout.addWidget(body)
        button = QPushButton("Check now")
        button.clicked.connect(self._check_library_health)
        layout.addWidget(button)
        self._place_card(card)
        return body, button

    def _new_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
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
        heading = QLabel(title)
        heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        layout.addWidget(heading)
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


def _book_line(book: BookSummary) -> str:
    title = book.title or "(untitled)"
    return f"{title} - {book.author}" if book.author else title


def _bookmark_line(bookmark: RecentBookmark) -> str:
    title = bookmark.title or "(untitled)"
    return f"{title} - page {bookmark.page_number}"
