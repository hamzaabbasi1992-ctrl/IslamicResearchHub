"""Tests for aggregation of in-memory library data."""

from islamic_research_hub.application.library_analyzer import LibraryAnalyzer
from islamic_research_hub.application.mjbz_folder_scanner import FolderScanResult
from islamic_research_hub.domain.models.book import Book, Category, Chapter, Page


def test_analyzer_reports_metadata_content_and_duplicates() -> None:
    """The analyzer derives requested statistics without writing book data."""
    shared_information = {
        "Name": "Shared Title",
        "ANAME": "Shared Author",
        "PNAME": "Publisher",
        "MJCN": "1",
        "Language": "ur",
    }
    first_book = Book(
        information=shared_information,
        categories=(Category(1, "Root", None, 1),),
        table_of_contents=(
            Chapter(1, "Chapter", 1, None, 1),
            Chapter(2, "Chapter", 1, None, 2),
        ),
        pages=(
            Page(1, 1, "", ""),
            Page(2, 1, "Text", "Plain"),
        ),
    )
    second_book = Book(
        information=dict(shared_information),
        categories=(),
        table_of_contents=(),
        pages=(),
    )

    report = LibraryAnalyzer().analyze(
        FolderScanResult(
            books=(first_book, second_book),
            processed_count=2,
            failed_count=0,
        )
    )

    assert report.total_books == 2
    assert report.total_pages == 2
    assert report.total_toc_entries == 2
    assert report.total_categories == 1
    assert report.content_quality["empty_pages"] == 1
    assert report.content_quality["duplicate_page_numbers"] == 1
    assert report.content_quality["duplicate_toc_entries"] == 1
    assert report.content_quality["books_with_zero_pages"] == 1
    assert report.content_quality["books_with_zero_toc"] == 1
    assert report.duplicate_titles[0].count == 2
    assert report.duplicate_authors[0].count == 2
