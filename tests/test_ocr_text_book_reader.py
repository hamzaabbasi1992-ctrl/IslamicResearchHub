"""Tests for reading real Google-Vision-OCR'd Urdu book text files."""

from pathlib import Path

from islamic_research_hub.infrastructure.persistence.ocr_text_book_reader import (
    read_ocr_text_book_file,
)


def test_reads_a_file_with_real_text(tmp_path: Path) -> None:
    text_path = tmp_path / "Kitab_ut_Tib.txt"
    text_path.write_text("بسم الله الرحمن الرحيم " * 40, encoding="utf-8")

    book = read_ocr_text_book_file(text_path)

    assert book is not None
    assert book.information["Name"] == "Kitab ut Tib"
    assert len(book.pages) == 1
    assert "بسم" in book.pages[0].content_f


def test_title_derived_from_filename_cleans_up_separators(tmp_path: Path) -> None:
    text_path = tmp_path / "Ainak-Laghana-Choriye.txt"
    text_path.write_text("Real content " * 20, encoding="utf-8")

    book = read_ocr_text_book_file(text_path)

    assert book is not None
    assert book.information["Name"] == "Ainak Laghana Choriye"


def test_skips_a_blank_file(tmp_path: Path) -> None:
    text_path = tmp_path / "Empty.txt"
    text_path.write_text("   \n\n  ", encoding="utf-8")

    assert read_ocr_text_book_file(text_path) is None


def test_splits_content_into_real_pages_using_page_number_markers(tmp_path: Path) -> None:
    text_path = tmp_path / "Multi Page Book.txt"
    content = (
        "مقدمة الكتاب " * 10
        + "\n5\n"
        + "محتوى الصفحة الخامسة " * 10
        + "\n6\n"
        + "محتوى الصفحة السادسة " * 10
    )
    text_path.write_text(content, encoding="utf-8")

    book = read_ocr_text_book_file(text_path)

    assert book is not None
    assert len(book.pages) == 2
    assert book.pages[0].page_number == 5
    assert "الخامسة" in book.pages[0].content_f
    assert book.pages[1].page_number == 6
    assert "السادسة" in book.pages[1].content_f
    # Content before the first marker (boilerplate/TOC) is not included as a page.
    assert all("مقدمة" not in page.content_f for page in book.pages)


def test_falls_back_to_single_page_when_no_markers_present(tmp_path: Path) -> None:
    text_path = tmp_path / "No Markers Book.txt"
    text_path.write_text("بسم الله الرحمن الرحيم " * 40, encoding="utf-8")

    book = read_ocr_text_book_file(text_path)

    assert book is not None
    assert len(book.pages) == 1
    assert book.pages[0].page_number == 1


def test_a_repeated_page_number_does_not_falsely_split_a_page(tmp_path: Path) -> None:
    """A real OCR artifact: a running header/footer number repeated
    mid-page (or a duplicated marker) must not be treated as a new
    page - only a strictly higher number counts as a real page break."""
    content = (
        "\n1\n"
        + "پہلے صفحے کا مواد۔ "
        + "\n1\n"  # repeated/duplicated marker, not a real new page
        + "باقی مواد اسی صفحے کا حصہ ہے۔ "
        + "\n2\n"
        + "دوسرے صفحے کا مواد "
    )
    text_path = tmp_path / "Repeated Marker Book.txt"
    text_path.write_text(content, encoding="utf-8")

    book = read_ocr_text_book_file(text_path)

    assert book is not None
    assert len(book.pages) == 2
    assert book.pages[0].page_number == 1
    assert "باقی مواد" in book.pages[0].content_f  # stayed on page 1, not split again
    assert book.pages[1].page_number == 2


def test_an_implausible_sparse_split_falls_back_to_one_honest_page(tmp_path: Path) -> None:
    """Real, confirmed failure mode: a lone standalone number elsewhere
    in the text (a footnote/hadith reference, not a real page number)
    gets accepted as the only marker, producing one huge, wrongly-
    numbered "page". Caught by the average-page-length plausibility
    check and downgraded to one honest page instead."""
    content = "حقیقی متن " * 20000 + "\n8210\n" + "مزید متن "

    text_path = tmp_path / "Suspicious Book.txt"
    text_path.write_text(content, encoding="utf-8")

    book = read_ocr_text_book_file(text_path)

    assert book is not None
    assert len(book.pages) == 1
    assert book.pages[0].page_number == 1
    assert "حقیقی" in book.pages[0].content_f
    assert "مزید" in book.pages[0].content_f


def test_a_page_marker_with_a_trailing_period_is_recognized(tmp_path: Path) -> None:
    content = "مقدمہ " * 3 + "\n2.\n" + "دوسرا صفحہ " * 30
    text_path = tmp_path / "Dotted Markers.txt"
    text_path.write_text(content, encoding="utf-8")

    book = read_ocr_text_book_file(text_path)

    assert book is not None
    assert len(book.pages) == 1
    assert book.pages[0].page_number == 2
