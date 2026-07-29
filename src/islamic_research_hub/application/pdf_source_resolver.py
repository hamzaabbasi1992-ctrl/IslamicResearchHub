"""Resolve a book's real, openable PDF file path, when one exists.

Shared between every interface that offers an "open the PDF" action (the
web app, the desktop app) so the library-specific resolution rules exist
in exactly one place.
"""

from pathlib import Path

PDF_SOURCE_LIBRARIES = frozenset(
    {
        "Maktaba Jibreel (PDF Archive)",
        "Maktaba Al-Maknoon (PDF Archive)",
        "Jumma Bayanat",
        "Maktaba Islam (PDF Archive)",
    }
)
MAKNOON_TEXT_LIBRARY = "Maktaba Al-Maknoon"


def resolve_pdf_path(
    library: str | None, source: str, maknoon_pdf_folder: Path
) -> Path | None:
    """Return the real PDF path for a book, or None if it has no PDF available.

    Metadata-only PDF libraries store the real PDF path as `Source`
    directly. The original Maknoon library stores a stale pre-extracted
    text file path instead - its real PDF (if any) lives in a separate
    folder, found by filename stem (`"X.pdf.txt"` -> `"X.pdf"`).
    """
    if library in PDF_SOURCE_LIBRARIES:
        path = Path(source)
        return path if path.is_file() else None
    if library == MAKNOON_TEXT_LIBRARY:
        candidate = maknoon_pdf_folder / Path(source).stem
        return candidate if candidate.is_file() else None
    return None
