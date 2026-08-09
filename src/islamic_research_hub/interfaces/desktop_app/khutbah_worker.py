"""Background worker: generate real Khutbah sermon outlines off the GUI thread.

Mirrors `LectureNotesGenerationWorker`'s PySide6 thread discipline.
"""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.khutbah_extraction import (
    ExtractedKhutbahOutline,
    parse_extracted_khutbah,
)

LOGGER = logging.getLogger(__name__)


class KhutbahGenerationWorker(QThread):
    """Generate real Khutbah sermon outlines off the GUI thread."""

    generation_finished = Signal(object)  # ExtractedKhutbahOutline | None
    generation_unavailable = Signal(str)

    def __init__(
        self,
        get_service: Callable[[], AiAgentService | None],
        topic: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._topic = topic

    def run(self) -> None:
        service = self._get_service()
        if service is None:
            self.generation_unavailable.emit(
                "AI Agent is unavailable - check it's enabled and an API key is set."
            )
            return

        try:
            prompt = f"Generate a structured Friday Khutbah outline for the topic: {self._topic}"
            result = service.answer_question(prompt)
            outline = parse_extracted_khutbah(result.answer)
            self.generation_finished.emit(outline)
        except Exception as err:
            LOGGER.warning("Khutbah generation failed: %s", err)
            self.generation_finished.emit(None)
