"""Library-level analysis over Book objects retained in memory."""

from collections import Counter

from islamic_research_hub.application.mjbz_folder_scanner import FolderScanResult
from islamic_research_hub.domain.models.book import Book, Category, Chapter, Page
from islamic_research_hub.domain.models.library_report import (
    BookSize,
    DuplicateMetadataValue,
    LibraryReport,
)

# These keys are verified from the Information table in the supplied MJBZ file.
TITLE_KEY = "Name"
AUTHOR_KEY = "ANAME"
PUBLISHER_KEY = "PNAME"
LANGUAGE_KEY = "Language"
CATEGORY_KEY = "MJCN"


class LibraryAnalyzer:
    """Analyze successful in-memory extractions without persisting books."""

    def analyze(self, scan_result: FolderScanResult) -> LibraryReport:
        """Build quality, size, and duplicate statistics for all books."""
        books = scan_result.books
        book_sizes = tuple(_book_size(book) for book in books)
        total_books = len(books)
        total_pages = sum(size.pages for size in book_sizes)
        total_chapters = sum(size.chapters for size in book_sizes)

        return LibraryReport(
            total_books=total_books,
            total_pages=total_pages,
            total_toc_entries=total_chapters,
            total_categories=sum(_count_categories(book.categories) for book in books),
            metadata_quality={
                "missing_title": _missing_metadata_count(books, TITLE_KEY),
                "missing_author": _missing_metadata_count(books, AUTHOR_KEY),
                "missing_publisher": _missing_metadata_count(books, PUBLISHER_KEY),
                "missing_language": _missing_metadata_count(books, LANGUAGE_KEY),
                "missing_category": _missing_metadata_count(books, CATEGORY_KEY),
            },
            content_quality={
                "empty_pages": sum(_empty_page_count(book.pages) for book in books),
                "duplicate_page_numbers": sum(
                    _duplicate_page_number_count(book.pages) for book in books
                ),
                "duplicate_toc_entries": sum(
                    _duplicate_toc_entry_count(book.table_of_contents)
                    for book in books
                ),
                "books_with_zero_pages": sum(
                    not book.pages for book in books
                ),
                "books_with_zero_toc": sum(
                    not book.table_of_contents for book in books
                ),
            },
            largest_book=_select_book_size(book_sizes, largest=True),
            smallest_book=_select_book_size(book_sizes, largest=False),
            average_pages=_average(total_pages, total_books),
            average_chapters=_average(total_chapters, total_books),
            duplicate_titles=_duplicate_metadata_values(books, TITLE_KEY),
            duplicate_authors=_duplicate_metadata_values(books, AUTHOR_KEY),
        )


def _book_size(book: Book) -> BookSize:
    """Create size metrics for one book using verified in-memory fields."""
    return BookSize(
        title=_metadata_value(book, TITLE_KEY),
        pages=len(book.pages),
        chapters=_count_chapters(book.table_of_contents),
    )


def _metadata_value(book: Book, key: str) -> str | None:
    """Return a non-empty value from a verified Information key."""
    value = book.information.get(key)
    if value is None:
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _missing_metadata_count(books: tuple[Book, ...], key: str) -> int:
    """Count books whose verified metadata key is absent or blank."""
    return sum(_metadata_value(book, key) is None for book in books)


def _count_categories(categories: tuple[Category, ...]) -> int:
    """Count every category in a hierarchy."""
    return sum(1 + _count_categories(category.children) for category in categories)


def _count_chapters(chapters: tuple[Chapter, ...]) -> int:
    """Count every TOC entry in a hierarchy."""
    return sum(1 + _count_chapters(chapter.children) for chapter in chapters)


def _empty_page_count(pages: tuple[Page, ...]) -> int:
    """Count pages whose ContentF and ContentP are both missing or blank."""
    return sum(
        _is_blank(page.content_f) and _is_blank(page.content_p) for page in pages
    )


def _duplicate_page_number_count(pages: tuple[Page, ...]) -> int:
    """Count repeat page-number occurrences within one book."""
    page_numbers = (page.page_number for page in pages if page.page_number is not None)
    return sum(count - 1 for count in Counter(page_numbers).values() if count > 1)


def _duplicate_toc_entry_count(chapters: tuple[Chapter, ...]) -> int:
    """Count repeated TOC records with the same title, page, and parent."""
    identifiers = (
        (chapter.title, chapter.page_number, chapter.parent_id)
        for chapter in _flatten_chapters(chapters)
    )
    return sum(count - 1 for count in Counter(identifiers).values() if count > 1)


def _flatten_chapters(chapters: tuple[Chapter, ...]) -> tuple[Chapter, ...]:
    """Return every TOC node in depth-first order."""
    flattened: list[Chapter] = []
    for chapter in chapters:
        flattened.append(chapter)
        flattened.extend(_flatten_chapters(chapter.children))
    return tuple(flattened)


def _select_book_size(
    book_sizes: tuple[BookSize, ...],
    largest: bool,
) -> BookSize | None:
    """Select the largest or smallest book by page count, then chapters."""
    if not book_sizes:
        return None
    return (max if largest else min)(
        book_sizes,
        key=lambda size: (size.pages, size.chapters, size.title or ""),
    )


def _average(total: int, count: int) -> float:
    """Return a stable two-decimal average for an empty or non-empty library."""
    return round(total / count, 2) if count else 0.0


def _duplicate_metadata_values(
    books: tuple[Book, ...],
    key: str,
) -> tuple[DuplicateMetadataValue, ...]:
    """Return non-empty metadata values occurring in more than one book."""
    counts = Counter(
        value for book in books if (value := _metadata_value(book, key)) is not None
    )
    return tuple(
        DuplicateMetadataValue(value=value, count=count)
        for value, count in sorted(counts.items(), key=lambda item: item[0].casefold())
        if count > 1
    )


def _is_blank(value: str | None) -> bool:
    """Return whether an optional content string contains no usable text."""
    return value is None or not value.strip()
