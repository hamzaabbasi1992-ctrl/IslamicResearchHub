"""Typed model for the desktop app header bar's live corpus stats."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HeaderStats:
    """Corpus-wide counts shown in the app header (books/libraries/authors/...)."""

    book_count: int
    library_count: int
    author_count: int
    category_count: int
    series_count: int
