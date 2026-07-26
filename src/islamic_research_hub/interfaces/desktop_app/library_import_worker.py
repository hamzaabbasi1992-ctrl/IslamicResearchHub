"""Background worker: run a real importer off the GUI thread, for the Import screen.

Reuses the same application/infrastructure classes the CLI importers use
(`MjbzFolderScanner`, `MasterDatabaseBuilder`, the Maknoon/PDF readers) -
no new import logic, just a `QThread` wrapper so a real scan+import
doesn't freeze the window. Jibreel Desktop (`.mjbx`, encrypted) is
deliberately not wired here: it needs extra configuration (the app's own
SQLite DLL path, a decryption password) that doesn't fit this simple
folder+format form - it stays a CLI-only import, same as before.
"""

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.master_database_builder import MasterDatabaseBuilder
from islamic_research_hub.application.mjbz_book_extraction import MjbzBookExtractionService
from islamic_research_hub.application.mjbz_folder_scanner import FolderScanResult, MjbzFolderScanner
from islamic_research_hub.infrastructure.persistence.maknoon_text_reader import (
    read_maknoon_text_file,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.mjbz_book_reader import SqliteMjbzBookReader
from islamic_research_hub.infrastructure.persistence.mjbz_sqlite_inspector import (
    SqliteMjbzInspector,
)
from islamic_research_hub.infrastructure.persistence.pdf_metadata_reader import read_pdf_metadata

FORMAT_AUTO = "auto"
FORMAT_MJBZ = "mjbz"
FORMAT_MAKNOON = "maknoon"
FORMAT_PDF = "pdf"


class LibraryImportError(Exception):
    """Raised when a folder can't be scanned/imported (bad path, undetectable format)."""


class LibraryImportWorker(QThread):
    """Scan a folder and import it into the master database, off the GUI thread."""

    progress = Signal(int, int)  # completed, total
    import_finished = Signal(int, int, int)  # imported, skipped, failed
    import_failed = Signal(str)

    def __init__(
        self,
        folder_path: Path,
        library_name: str,
        format_key: str,
        database_path: Path,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._folder_path = folder_path
        self._library_name = library_name
        self._format_key = format_key
        self._database_path = database_path

    def run(self) -> None:
        try:
            resolved_format = _resolve_format(self._folder_path, self._format_key)
            scan_result = _scan(resolved_format, self._folder_path, self.progress.emit)
            build_result = MasterDatabaseBuilder(MasterBookRepository()).build(
                scan_result,
                database_path=self._database_path,
                library_name=self._library_name,
                progress=self.progress.emit,
            )
        except (LibraryImportError, NotADirectoryError, OSError) as error:
            self.import_failed.emit(str(error))
            return
        self.import_finished.emit(
            build_result.imported_count, build_result.skipped_count, build_result.failed_count
        )


def _resolve_format(folder_path: Path, format_key: str) -> str:
    """Return the real format to use, auto-detecting from the folder's actual contents."""
    if format_key != FORMAT_AUTO:
        return format_key
    if any(folder_path.rglob("*.mjbz")):
        return FORMAT_MJBZ
    if any(folder_path.glob("*.pdf.txt")):
        return FORMAT_MAKNOON
    if any(folder_path.rglob("*.pdf")):
        return FORMAT_PDF
    raise LibraryImportError(
        "Couldn't detect a known format in this folder "
        "(looked for .mjbz, .pdf.txt, and .pdf files)."
    )


def _scan(format_key: str, folder_path: Path, progress) -> FolderScanResult:
    """Build a FolderScanResult using the same readers the matching CLI importer uses."""
    if format_key == FORMAT_MJBZ:
        service = MjbzBookExtractionService(
            inspector=SqliteMjbzInspector(), reader=SqliteMjbzBookReader()
        )
        return MjbzFolderScanner(service).scan(folder_path, progress=progress)
    if format_key == FORMAT_MAKNOON:
        return _scan_maknoon(folder_path, progress)
    if format_key == FORMAT_PDF:
        return _scan_pdf(folder_path, progress)
    raise LibraryImportError(f"Unsupported format for GUI import: {format_key}")


def _scan_maknoon(folder_path: Path, progress) -> FolderScanResult:
    files = sorted(folder_path.glob("*.pdf.txt"))
    books = []
    sources = []
    failed_count = 0
    for completed, file_path in enumerate(files, start=1):
        try:
            book = read_maknoon_text_file(file_path)
        except OSError:
            failed_count += 1
        else:
            if book is not None:
                books.append(book)
                sources.append(file_path.resolve())
            else:
                failed_count += 1
        if progress is not None:
            progress(completed, len(files))
    return FolderScanResult(
        books=tuple(books), processed_count=len(files), failed_count=failed_count,
        sources=tuple(sources),
    )


def _scan_pdf(folder_path: Path, progress) -> FolderScanResult:
    files = sorted(folder_path.rglob("*.pdf"))
    books = tuple(read_pdf_metadata(file_path) for file_path in files)
    sources = tuple(file_path.resolve() for file_path in files)
    if progress is not None:
        progress(len(files), len(files))
    return FolderScanResult(
        books=books, processed_count=len(files), failed_count=0, sources=sources
    )
