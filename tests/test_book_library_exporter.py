"""Tests for exporting scanned books as Markdown files grouped by subject."""

from pathlib import Path

from islamic_research_hub.application.mjbz_folder_scanner import FolderScanResult
from islamic_research_hub.domain.models.book import Book, Category, Page
from islamic_research_hub.infrastructure.reporting.book_library_exporter import (
    BookLibraryExporter,
)


def _book(**information: str) -> Book:
    """Build a minimal book with the given Information entries."""
    return Book(
        information=information,
        categories=(
            Category(
                mjcn=1,
                name="Fiqh",
                parent_mjcn=None,
                sort_key=1,
                children=(
                    Category(mjcn=2, name="Worship", parent_mjcn=1, sort_key=1),
                ),
            ),
        ),
        table_of_contents=(),
        pages=(Page(1, 1, "Formatted content", "Plain content"),),
    )


def test_export_writes_markdown_under_resolved_subject(tmp_path: Path) -> None:
    """A book is written to <output>/<root subject>/<title>.md with metadata and content."""
    book = _book(Name="Book One", ANAME="Author One", PNAME="Publisher", Language="ar", MJCN="2")
    scan_result = FolderScanResult(
        books=(book,),
        processed_count=1,
        failed_count=0,
        sources=(tmp_path / "book-one.mjbz",),
    )
    output_directory = tmp_path / "library"

    result = BookLibraryExporter().export(scan_result, output_directory)

    assert result.exported_count == 1
    assert result.skipped_count == 0
    file_path = output_directory / "Fiqh" / "Book One.md"
    content = file_path.read_text(encoding="utf-8")
    assert "# Book One" in content
    assert "**Author:** Author One" in content
    assert "Formatted content" in content
    assert "Plain content" not in content


def test_export_falls_back_to_uncategorized_when_mjcn_is_unresolvable(
    tmp_path: Path,
) -> None:
    """A missing or unresolvable MJCN value falls back to an Uncategorized folder."""
    book = _book(Name="Book Two", MJCN="999")
    scan_result = FolderScanResult(
        books=(book,),
        processed_count=1,
        failed_count=0,
        sources=(tmp_path / "book-two.mjbz",),
    )
    output_directory = tmp_path / "library"

    BookLibraryExporter().export(scan_result, output_directory)

    assert (output_directory / "Uncategorized" / "Book Two.md").is_file()


def test_export_sanitizes_titles_with_invalid_filename_characters(
    tmp_path: Path,
) -> None:
    """Titles containing filesystem-reserved characters are cleaned for the filename."""
    book = _book(Name="Fiqh: Chapter/One?", MJCN="2")
    scan_result = FolderScanResult(
        books=(book,),
        processed_count=1,
        failed_count=0,
        sources=(tmp_path / "book.mjbz",),
    )
    output_directory = tmp_path / "library"

    BookLibraryExporter().export(scan_result, output_directory)

    exported_files = list((output_directory / "Fiqh").iterdir())
    assert len(exported_files) == 1
    assert exported_files[0].name == "Fiqh Chapter One.md"


def test_export_disambiguates_same_run_title_collisions(tmp_path: Path) -> None:
    """Two different sources sharing a subject and title do not overwrite each other."""
    first_book = _book(Name="Shared Title", MJCN="2")
    second_book = _book(Name="Shared Title", MJCN="2")
    scan_result = FolderScanResult(
        books=(first_book, second_book),
        processed_count=2,
        failed_count=0,
        sources=(tmp_path / "first.mjbz", tmp_path / "second.mjbz"),
    )
    output_directory = tmp_path / "library"

    result = BookLibraryExporter().export(scan_result, output_directory)

    assert result.exported_count == 2
    exported_files = {path.name for path in (output_directory / "Fiqh").iterdir()}
    assert exported_files == {"Shared Title.md", "Shared Title (second).md"}
