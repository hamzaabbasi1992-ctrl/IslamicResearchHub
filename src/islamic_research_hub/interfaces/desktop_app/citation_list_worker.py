"""Background worker: generate research bibliographies / citation lists off the GUI thread."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.citation_list_extraction import (
    ExtractedCitationEntry,
    parse_extracted_citation_list,
)

LOGGER = logging.getLogger(__name__)


class CitationListWorker(QThread):
    """Generate research citation bibliographies off the GUI thread."""

    generation_finished = Signal(object)  # tuple[ExtractedCitationEntry, ...]
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
            prompt = f"Generate a citation list and bibliography for topic: {self._topic}"
            result = service.answer_question(prompt)
            citations = parse_extracted_citation_list(result.answer)
            self.generation_finished.emit(citations)
        except Exception as err:
            LOGGER.warning("Citation list generation failed: %s", err)
            self.generation_finished.emit(())
