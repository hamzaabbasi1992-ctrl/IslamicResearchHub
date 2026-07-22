"""Markdown export adapter that writes each scanned book as a standalone file."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from islamic_research_hub.application.mjbz_folder_scanner import FolderScanResult
from islamic_research_hub.domain.models.book import Book, Category, Page

LOGGER = logging.getLogger(__name__)

TITLE_KEY = "Name"
AUTHOR_KEY = "ANAME"
PUBLISHER_KEY = "PNAME"
LANGUAGE_KEY = "Language"
CATEGORY_KEY = "MJCN"

UNKNOWN_SUBJECT = "Uncategorized"
UNKNOWN_TITLE = "Untitled"
MAX_COMPONENT_LENGTH = 150

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True, slots=True)
class BookExportResult:
    """Summary of one book-library export run."""

    exported_count: int
    skipped_count: int


class BookLibraryExporter:
    """Write each successfully scanned book as one Markdown file, grouped by subject."""

    def export(
        self,
        scan_result: FolderScanResult,
        output_directory: Path,
    ) -> BookExportResult:
        """Write one `<subject>/<title>.md` file per book under output_directory."""
        exported_count = 0
        skipped_count = 0
        used_paths: set[Path] = set()

        for book, source in zip(scan_result.books, scan_result.sources, strict=True):
            try:
                file_path = self._resolve_file_path(
                    book, source, output_directory, used_paths
                )
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(self._to_markdown(book), encoding="utf-8")
                used_paths.add(file_path)
                exported_count += 1
            except OSError:
                skipped_count += 1
                LOGGER.exception("Failed to export book file: %s", source)

        return BookExportResult(exported_count=exported_count, skipped_count=skipped_count)

    def _resolve_file_path(
        self,
        book: Book,
        source: Path,
        output_directory: Path,
        used_paths: set[Path],
    ) -> Path:
        """Return a unique, sanitized `<subject>/<title>.md` path for one book."""
        subject = _sanitize_component(self._resolve_subject(book)) or UNKNOWN_SUBJECT
        title = _sanitize_component(_metadata_value(book, TITLE_KEY)) or UNKNOWN_TITLE
        candidate = output_directory / subject / f"{title}.md"
        if candidate in used_paths:
            candidate = output_directory / subject / f"{title} ({source.stem}).md"
        return candidate

    @staticmethod
    def _resolve_subject(book: Book) -> str:
        """Resolve the book's root category name from its own MJCN placement."""
        mjcn_value = _metadata_value(book, CATEGORY_KEY)
        if mjcn_value is None:
            return UNKNOWN_SUBJECT
        try:
            category_id = int(mjcn_value)
        except ValueError:
            return UNKNOWN_SUBJECT

        by_id = {
            category.mjcn: category
            for category in _flatten_categories(book.categories)
            if category.mjcn is not None
        }
        node = by_id.get(category_id)
        if node is None:
            return UNKNOWN_SUBJECT

        visited: set[int] = set()
        while (
            node.parent_mjcn is not None
            and node.parent_mjcn in by_id
            and node.mjcn not in visited
        ):
            visited.add(node.mjcn)
            node = by_id[node.parent_mjcn]
        return node.name or UNKNOWN_SUBJECT

    @staticmethod
    def _to_markdown(book: Book) -> str:
        """Render one book as Markdown with a metadata header and page content."""
        title = _metadata_value(book, TITLE_KEY) or UNKNOWN_TITLE
        author = _metadata_value(book, AUTHOR_KEY) or "Unknown"
        publisher = _metadata_value(book, PUBLISHER_KEY) or "Unknown"
        language = _metadata_value(book, LANGUAGE_KEY) or "Unknown"

        lines = [
            f"# {title}",
            "",
            f"- **Author:** {author}",
            f"- **Publisher:** {publisher}",
            f"- **Language:** {language}",
            "",
            "---",
            "",
        ]
        for page in book.pages:
            content = _page_content(page)
            if content is None or not content.strip():
                continue
            lines.append(content)
            lines.append("")
        return "\n".join(lines)


def _metadata_value(book: Book, key: str) -> str | None:
    """Return a non-empty value from a verified Information key."""
    value = book.information.get(key)
    if value is None:
        return None
    normalized_value = value.strip()
    return normalized_value or None


def _flatten_categories(categories: tuple[Category, ...]) -> tuple[Category, ...]:
    """Return each category hierarchy node once in depth-first order."""
    flattened: list[Category] = []
    for category in categories:
        flattened.append(category)
        flattened.extend(_flatten_categories(category.children))
    return tuple(flattened)


def _page_content(page: Page) -> str | None:
    """Return formatted content when available, otherwise plain content."""
    if page.content_f is not None and page.content_f.strip():
        return page.content_f
    return page.content_p


def _sanitize_component(value: str | None) -> str:
    """Return a filesystem-safe path component derived from free-form text."""
    if value is None:
        return ""
    cleaned = _INVALID_FILENAME_CHARS.sub(" ", value)
    cleaned = " ".join(cleaned.split())
    return cleaned.strip(" .")[:MAX_COMPONENT_LENGTH]
