"""Background worker: generate word-by-word morphological & root analysis off the GUI thread."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.grammar_breakdown import (
    ExtractedPassageGrammar,
    parse_grammar_breakdown,
)

LOGGER = logging.getLogger(__name__)


class GrammarBreakdownWorker(QThread):
    """Generate passage grammar & root-word breakdown off the GUI thread."""

    generation_finished = Signal(object)  # ExtractedPassageGrammar | None
    generation_unavailable = Signal(str)

    def __init__(
        self,
        get_service: Callable[[], AiAgentService | None],
        passage_text: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._passage_text = passage_text

    def run(self) -> None:
        service = self._get_service()
        if service is None:
            self.generation_unavailable.emit(
                "AI Agent is unavailable - check it's enabled and an API key is set."
            )
            return

        try:
            prompt = f"Provide a word-by-word morphological and root analysis for passage: {self._passage_text}"
            result = service.answer_question(prompt)
            grammar = parse_grammar_breakdown(result.answer)
            self.generation_finished.emit(grammar)
        except Exception as err:
            LOGGER.warning("Grammar breakdown generation failed: %s", err)
            self.generation_finished.emit(None)
