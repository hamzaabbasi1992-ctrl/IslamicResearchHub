"""Tests for the in-memory recursive MJBZ folder scanner."""

from pathlib import Path

from islamic_research_hub.application.mjbz_folder_scanner import MjbzFolderScanner
from islamic_research_hub.domain.models.book import Book, Chapter, Page


class FakeExtractor:
    """Controlled extractor used to test scanner behaviour."""

    def extract_file(self, file_path: str | Path) -> Book:
        """Return a book or simulate an invalid MJBZ file."""
        if Path(file_path).name == "broken.mjbz":
            raise ValueError("Invalid MJBZ file")
        return Book(
            information={},
            categories=(),
            table_of_contents=(Chapter(1, "Chapter", 1, None, 1),),
            pages=(Page(1, 1, "Text", "Plain"),),
        )


def test_scanner_recurses_ignores_other_files_and_continues(tmp_path: Path) -> None:
    """Only MJBZ files are processed and failures do not stop the scan."""
    nested_folder = tmp_path / "nested"
    nested_folder.mkdir()
    (tmp_path / "first.mjbz").touch()
    (nested_folder / "second.MJBZ").touch()
    (nested_folder / "broken.mjbz").touch()
    (nested_folder / "ignored.txt").touch()

    result = MjbzFolderScanner(FakeExtractor()).scan(tmp_path)

    assert result.processed_count == 3
    assert result.succeeded_count == 2
    assert result.failed_count == 1
    assert result.total_pages == 2
    assert result.total_chapters == 2
