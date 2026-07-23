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


def test_splits_content_into_real_pages_using_page_markers(tmp_path: Path) -> None:
    """Content is split on Maknoon's own page markers, preserving real page numbers."""
    text_path = tmp_path / "Multi Page Book.pdf.txt"
    content = (
        "بسم الله الرحمن الرحيم مقدمة الكتاب " * 10
        + "\nöööööö 5 öööööö\n"
        + "محتوى الصفحة الخامسة " * 10
        + "\nöööööö 6 öööööö\n"
        + "محتوى الصفحة السادسة " * 10
    )
    text_path.write_text(content, encoding="utf-8")

    book = read_maknoon_text_file(text_path)

    assert book is not None
    assert len(book.pages) == 2
    assert book.pages[0].page_number == 5
    assert "الخامسة" in book.pages[0].content_f
    assert book.pages[1].page_number == 6
    assert "السادسة" in book.pages[1].content_f
    # Content before the first marker (boilerplate/header) is not included as a page.
    assert all("مقدمة" not in page.content_f for page in book.pages)


def test_falls_back_to_single_page_when_no_markers_present(tmp_path: Path) -> None:
    """Content without any page markers stays as one page, matching prior behavior."""
    text_path = tmp_path / "No Markers Book.pdf.txt"
    text_path.write_text("بسم الله الرحمن الرحيم " * 40, encoding="utf-8")

    book = read_maknoon_text_file(text_path)

    assert book is not None
    assert len(book.pages) == 1
    assert book.pages[0].page_number == 1
