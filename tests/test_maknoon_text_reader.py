"""Tests for reading Maknoon's pre-extracted PDF text files."""

from pathlib import Path

from islamic_research_hub.infrastructure.persistence.maknoon_text_reader import (
    read_maknoon_text_file,
)


def test_reads_a_file_with_real_arabic_text(tmp_path: Path) -> None:
    """A file containing substantial Arabic/Urdu text becomes a Book."""
    text_path = tmp_path / "Some Book.pdf.txt"
    text_path.write_text("بسم الله الرحمن الرحيم " * 40, encoding="utf-8")

    book = read_maknoon_text_file(text_path)

    assert book is not None
    assert book.information["Name"] == "Some Book"
    assert len(book.pages) == 1
    assert book.pages[0].content_f is not None
    assert "بسم" in book.pages[0].content_f


def test_skips_a_placeholder_only_file(tmp_path: Path) -> None:
    """A file with only page-marker noise and no real text returns None."""
    text_path = tmp_path / "Blank Book.pdf.txt"
    text_path.write_text(
        "\n".join(f"oooooo {n} oooooo" for n in range(1, 30)), encoding="utf-8"
    )

    assert read_maknoon_text_file(text_path) is None
