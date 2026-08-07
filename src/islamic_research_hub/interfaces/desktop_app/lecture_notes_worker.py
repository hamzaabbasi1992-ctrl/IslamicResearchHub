"""Background worker: generate real lecture-notes content from one book,
chunk by chunk, off the GUI thread.

A real tool-calling loop per chunk (`AiAgentService.generate_lecture_notes()`)
makes real network round trips - this must never block the GUI thread.
Mirrors `SlideDeckGenerationWorker`'s exact shape (per-chunk
cancellation, progress signal, partial-failure-is-not-fatal discipline)
- generated sections are collected in memory and handed back as one
ordered set, not persisted as reviewable DB candidates, since a lecture
note is a formatted restatement of real content rather than an
asserted fact needing explicit human confirmation.
"""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.lecture_notes_extraction import (
    ExtractedLectureSection,
    parse_extracted_lecture_sections,
)

LOGGER = logging.getLogger(__name__)


class LectureNotesGenerationWorker(QThread):
    """Generate real lecture-notes content from one book's real chunks, off the GUI thread."""

    chunk_processed = Signal(int, int)  # done, total
    generation_finished = Signal(object)  # tuple[ExtractedLectureSection, ...], in document order
    generation_unavailable = Signal(str)  # reason - service is None, not configured

    def __init__(
        self,
        get_service: Callable[[], AiAgentService | None],
        book_id: int,
        chunks: tuple[tuple[int, int], ...],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._book_id = book_id
        self._chunks = chunks

    def request_cancellation(self) -> None:
        """Ask a still-running worker to stop before its next chunk's
        generation (the expensive, non-interruptible step)."""
        self.requestInterruption()

    def run(self) -> None:
        service = self._get_service()
        if service is None:
            self.generation_unavailable.emit(
                "AI Agent is unavailable - check it's enabled and a real "
                "API key is set in Settings."
            )
            return
        sections: list[ExtractedLectureSection] = []
        total = len(self._chunks)
        for index, (start_page, end_page) in enumerate(self._chunks):
            if self.isInterruptionRequested():
                break
            try:
                result = service.generate_lecture_notes(self._book_id, start_page, end_page)
                sections.extend(parse_extracted_lecture_sections(result.answer))
            except Exception:
                LOGGER.warning(
                    "Lecture notes generation failed for book_id=%d pages %d-%d; skipping this chunk.",
                    self._book_id,
                    start_page,
                    end_page,
                )
            self.chunk_processed.emit(index + 1, total)
        self.generation_finished.emit(tuple(sections))
