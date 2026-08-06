"""Background worker: generate real multiple-choice study questions from
one book, chunk by chunk, off the GUI thread.

A real tool-calling loop per chunk (`AiAgentService.generate_mcqs()`)
makes real network round trips - this must never block the GUI thread.
Mirrors `FlashcardExtractionWorker`'s exact shape (per-chunk
cancellation, progress signal, partial-failure-is-not-fatal
discipline).
"""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.mcq_extraction import parse_extracted_mcqs
from islamic_research_hub.infrastructure.persistence.mcq_candidate_repository import (
    McqCandidateRepository,
)

LOGGER = logging.getLogger(__name__)


class McqExtractionWorker(QThread):
    """Generate real MCQs from one book's real chunks, off the GUI thread."""

    chunk_processed = Signal(int, int)  # done, total
    extraction_finished = Signal(int)  # total MCQs stored
    extraction_unavailable = Signal(str)  # reason - service is None, not configured

    def __init__(
        self,
        get_service: Callable[[], AiAgentService | None],
        repository: McqCandidateRepository,
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
        generation (the expensive, non-interruptible step)."""
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
                result = service.generate_mcqs(self._book_id, start_page, end_page)
                mcqs = parse_extracted_mcqs(result.answer)
            except Exception:
                LOGGER.warning(
                    "MCQ generation failed for book_id=%d pages %d-%d; skipping this chunk.",
                    self._book_id,
                    start_page,
                    end_page,
                )
                self.chunk_processed.emit(index + 1, total)
                continue
            for mcq in mcqs:
                self._repository.add_candidate(self._book_id, start_page, end_page, mcq)
                stored += 1
            self.chunk_processed.emit(index + 1, total)
        self.extraction_finished.emit(stored)
