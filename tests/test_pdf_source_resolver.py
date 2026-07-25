"""Tests for resolving a book's real PDF path across library types."""

from pathlib import Path

from islamic_research_hub.application.pdf_source_resolver import resolve_pdf_path


def test_resolves_original_pdf_archive_library(tmp_path: Path) -> None:
    """Maktaba Jibreel (PDF Archive) stores the real PDF path as Source."""
    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    resolved = resolve_pdf_path(
        "Maktaba Jibreel (PDF Archive)", str(pdf_path), tmp_path / "maknoon_pdfs"
    )

    assert resolved == pdf_path


def test_resolves_maknoon_pdf_archive_library(tmp_path: Path) -> None:
    """Maktaba Al-Maknoon (PDF Archive), added this session, also resolves directly."""
    pdf_path = tmp_path / "book.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    resolved = resolve_pdf_path(
        "Maktaba Al-Maknoon (PDF Archive)", str(pdf_path), tmp_path / "maknoon_pdfs"
    )

    assert resolved == pdf_path


def test_resolves_jumma_bayanat_library(tmp_path: Path) -> None:
    """Jumma Bayanat, added this session, also resolves directly."""
    pdf_path = tmp_path / "bayan.pdf"
    pdf_path.write_bytes(b"%PDF-1.4")

    resolved = resolve_pdf_path(
        "Jumma Bayanat", str(pdf_path), tmp_path / "maknoon_pdfs"
    )

    assert resolved == pdf_path


def test_resolves_original_maknoon_library_via_stem_lookup(tmp_path: Path) -> None:
    """The original Maknoon library's Source is a stale .pdf.txt path."""
    maknoon_pdf_folder = tmp_path / "maknoon_pdfs"
    maknoon_pdf_folder.mkdir()
    real_pdf = maknoon_pdf_folder / "Book One.pdf"
    real_pdf.write_bytes(b"%PDF-1.4")
    stale_source = str(tmp_path / "extracted" / "Book One.pdf.txt")

    resolved = resolve_pdf_path("Maktaba Al-Maknoon", stale_source, maknoon_pdf_folder)

    assert resolved == real_pdf


def test_returns_none_when_file_does_not_exist(tmp_path: Path) -> None:
    """A Source path that doesn't actually exist on disk resolves to None."""
    resolved = resolve_pdf_path(
        "Maktaba Jibreel (PDF Archive)",
        str(tmp_path / "missing.pdf"),
        tmp_path / "maknoon_pdfs",
    )

    assert resolved is None


def test_returns_none_for_text_only_libraries(tmp_path: Path) -> None:
    """Libraries with no PDF source at all (Jibreel Mobile/Desktop) return None."""
    resolved = resolve_pdf_path(
        "Maktaba Jibreel (Mobile)", "F:\\some\\source.mjbz", tmp_path / "maknoon_pdfs"
    )

    assert resolved is None


def test_returns_none_for_unknown_library(tmp_path: Path) -> None:
    """An unrecognized/missing library name returns None rather than guessing."""
    resolved = resolve_pdf_path(None, "F:\\some\\source", tmp_path / "maknoon_pdfs")

    assert resolved is None
