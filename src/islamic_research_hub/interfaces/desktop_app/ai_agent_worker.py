"""Background worker: run one AI Agent turn off the GUI thread.

A real tool-calling loop (`AiAgentService.converse()`) can make several
real network round trips (one per tool call plus the final answer) - this
must never block the GUI thread, same reasoning as `TtsWorker`/
`VoiceSearchWorker`/`SemanticSearchWorker`.
"""

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService


class AiAgentWorker(QThread):
    """Build (if needed, once) the AI Agent service and run one
    conversational turn, off the GUI thread."""

    answer_ready = Signal(str, object)  # answer_text, tool_calls_made: tuple[str, ...]
    answer_failed = Signal(str)  # user-facing error message

    def __init__(
        self,
        get_service: Callable[[], AiAgentService | None],
        question: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._question = question

    def run(self) -> None:
        try:
            service = self._get_service()
            if service is None:
                self.answer_failed.emit(
                    "AI Agent is unavailable - check it's enabled and a real "
                    "API key is set in Settings."
                )
                return
            result = service.converse(self._question)
        except Exception:
            self.answer_failed.emit("Something went wrong answering that question.")
            return
        self.answer_ready.emit(result.answer, result.tool_calls_made)
