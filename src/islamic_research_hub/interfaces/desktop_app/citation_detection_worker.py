"""Background worker: run citation candidate detection off the GUI thread.

Real measured runtime against the full production corpus: 15 minutes
(warm OS page cache) to 2+ hours (cold cache) for the full anchor set -
far too long to ever run on the GUI thread, same reasoning as
`TtsWorker`/`SemanticSearchWorker`.
"""

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.infrastructure.persistence.citation_candidate_repository import (
    CitationCandidateRepository,
)


class CitationDetectionWorker(QThread):
    """Run `CitationCandidateRepository.detect_and_store()` off the GUI thread."""

    detection_progress = Signal(int, int)  # done, total
    detection_finished = Signal(int)  # count found

    def __init__(self, repository: CitationCandidateRepository, parent=None) -> None:
        super().__init__(parent)
        self._repository = repository

    def run(self) -> None:
        count = self._repository.detect_and_store(
            progress_callback=lambda done, total: self.detection_progress.emit(done, total)
        )
        self.detection_finished.emit(count)
