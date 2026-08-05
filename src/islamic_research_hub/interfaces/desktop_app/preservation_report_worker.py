"""Background worker: generate the Digital Preservation Report off the GUI thread.

Real, measured cost against the full production corpus: the underlying
queries (a full `Pages` scan to find sparse/heading-only books, mirroring
`PdfMatchCandidateRepository`'s own stub-detection query) take well over
two minutes - far too long to ever run on the GUI thread, same reasoning
as `CitationDetectionWorker`/`TtsWorker`.
"""

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.infrastructure.persistence.preservation_report_repository import (
    IncompleteBook,
    PreservationReportRepository,
)


class PreservationReportWorker(QThread):
    """Run `PreservationReportRepository`'s real queries off the GUI thread."""

    report_ready = Signal(int, tuple)  # pending_duplicate_count, incomplete_books

    def __init__(self, repository: PreservationReportRepository, parent=None) -> None:
        super().__init__(parent)
        self._repository = repository

    def run(self) -> None:
        pending_duplicates = self._repository.count_pending_duplicates()
        incomplete_books: tuple[IncompleteBook, ...] = self._repository.list_incomplete_books()
        self.report_ready.emit(pending_duplicates, incomplete_books)
