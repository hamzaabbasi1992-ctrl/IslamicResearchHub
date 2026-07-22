"""JSON and Markdown export adapter for library analysis reports."""

import json
from pathlib import Path

from islamic_research_hub.domain.models.library_report import LibraryReport


class LibraryReportExporter:
    """Export a report without persisting any extracted book records."""

    def export(self, report: LibraryReport, output_directory: Path) -> None:
        """Write the requested JSON and Markdown report files."""
        output_directory.mkdir(parents=True, exist_ok=True)
        report_data = report.to_dict()
        (output_directory / "library_report.json").write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_directory / "library_report.md").write_text(
            self._to_markdown(report),
            encoding="utf-8",
        )

    @staticmethod
    def _to_markdown(report: LibraryReport) -> str:
        """Render the analysis as a concise, human-readable Markdown report."""
        lines = [
            "# Library Analysis Report",
            "",
            "## Totals",
            "",
            f"- Total books: {report.total_books}",
            f"- Total pages: {report.total_pages}",
            f"- Total TOC entries: {report.total_toc_entries}",
            f"- Total categories: {report.total_categories}",
            "",
            "## Metadata Quality",
            "",
            *(
                f"- {label.replace('_', ' ').title()}: {count}"
                for label, count in report.metadata_quality.items()
            ),
            "",
            "## Content Quality",
            "",
            *(
                f"- {label.replace('_', ' ').title()}: {count}"
                for label, count in report.content_quality.items()
            ),
            "",
            "Empty pages have blank or missing values in both `ContentF` and "
            "`ContentP`. Duplicate TOC entries have the same title, page number, "
            "and parent ID within one book.",
            "",
            "## Statistics",
            "",
            f"- Largest book: {_format_book_size(report.largest_book)}",
            f"- Smallest book: {_format_book_size(report.smallest_book)}",
            f"- Average pages: {report.average_pages:.2f}",
            f"- Average chapters: {report.average_chapters:.2f}",
            "",
            "## Duplicate Titles",
            "",
            *_format_duplicates(report.duplicate_titles),
            "",
            "## Duplicate Authors",
            "",
            *_format_duplicates(report.duplicate_authors),
            "",
        ]
        return "\n".join(lines)


def _format_book_size(book_size: object) -> str:
    """Format an optional book-size record for Markdown."""
    from islamic_research_hub.domain.models.library_report import BookSize

    if not isinstance(book_size, BookSize):
        return "None"
    title = book_size.title or "(missing title)"
    return f"{title} ({book_size.pages} pages, {book_size.chapters} chapters)"


def _format_duplicates(duplicates: tuple[object, ...]) -> tuple[str, ...]:
    """Format duplicate metadata values for Markdown."""
    from islamic_research_hub.domain.models.library_report import (
        DuplicateMetadataValue,
    )

    formatted = tuple(
        f"- {item.value}: {item.count} books"
        for item in duplicates
        if isinstance(item, DuplicateMetadataValue)
    )
    return formatted or ("- None",)
