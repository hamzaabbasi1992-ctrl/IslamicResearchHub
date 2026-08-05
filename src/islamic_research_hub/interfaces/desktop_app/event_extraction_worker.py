"""Background worker: extract real events from one book, chunk by chunk,
off the GUI thread.

A real tool-calling loop per chunk (`AiAgentService.extract_events()`)
makes real network round trips - this must never block the GUI thread,
same reasoning as `TtsWorker`/`CitationDetectionWorker`. Mirrors
`TtsWorker`'s per-chunk cancellation shape (checked before each chunk's
expensive real API call) and `CitationDetectionWorker`'s progress-signal
shape.
"""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.event_extraction import parse_extracted_events
from islamic_research_hub.infrastructure.persistence.event_candidate_repository import (
    EventCandidateRepository,
)

LOGGER = logging.getLogger(__name__)


class EventExtractionWorker(QThread):
    """Extract real events from one book's real chunks, off the GUI thread."""

    chunk_processed = Signal(int, int)  # done, total
    extraction_finished = Signal(int)  # total events stored
    extraction_unavailable = Signal(str)  # reason - service is None, not configured

    def __init__(
        self,
        get_service: Callable[[], AiAgentService | None],
        repository: EventCandidateRepository,
        book_id: int,
        chunks: tuple[tuple[int, int], ...],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._repository = repository
        self._book_id = book_id
        self._chunks = chunks

    def request_cancellation(self) -> None:
        """Ask a still-running worker to stop before its next chunk's
        extraction (the expensive, non-interruptible step)."""
        self.requestInterruption()

    def run(self) -> None:
        service = self._get_service()
        if service is None:
            self.extraction_unavailable.emit(
                "AI Agent is unavailable - check it's enabled and a real "
                "API key is set in Settings."
            )
            return
        stored = 0
        total = len(self._chunks)
        for index, (start_page, end_page) in enumerate(self._chunks):
            if self.isInterruptionRequested():
                break
            try:
                result = service.extract_events(self._book_id, start_page, end_page)
                events = parse_extracted_events(result.answer)
            except Exception:
                LOGGER.warning(
                    "Event extraction failed for book_id=%d pages %d-%d; skipping this chunk.",
                    self._book_id,
                    start_page,
                    end_page,
                )
                self.chunk_processed.emit(index + 1, total)
                continue
            for event in events:
                self._repository.add_candidate(self._book_id, start_page, end_page, event)
                stored += 1
            self.chunk_processed.emit(index + 1, total)
        self.extraction_finished.emit(stored)
