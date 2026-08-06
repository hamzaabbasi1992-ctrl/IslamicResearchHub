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


def candidate_pdf_path(
    library: str | None, source: str, maknoon_pdf_folder: Path
) -> Path | None:
    """Return the real path a book's PDF *should* be at, regardless of
    whether a file currently exists there.

    Shared by `resolve_pdf_path` (which additionally checks existence) and
    by UI error messages that need to tell the user exactly where to place
    a missing file (e.g. an external drive that isn't currently plugged
    in) - the two must never compute this path differently.
    """
    if library in PDF_SOURCE_LIBRARIES:
        return Path(source)
    if library == MAKNOON_TEXT_LIBRARY:
        return maknoon_pdf_folder / Path(source).stem
    return None


def resolve_pdf_path(
    library: str | None, source: str, maknoon_pdf_folder: Path
) -> Path | None:
    """Return the real PDF path for a book, or None if it has no PDF available.

    Metadata-only PDF libraries store the real PDF path as `Source`
    directly. The original Maknoon library stores a stale pre-extracted
    text file path instead - its real PDF (if any) lives in a separate
    folder, found by filename stem (`"X.pdf.txt"` -> `"X.pdf"`).
    """
    path = candidate_pdf_path(library, source, maknoon_pdf_folder)
    return path if path is not None and path.is_file() else None
