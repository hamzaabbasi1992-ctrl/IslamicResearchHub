"""Background worker: run one AI Agent turn off the GUI thread.

A real tool-calling loop (`AiAgentService.converse()`) can make several
real network round trips (one per tool call plus the final answer) - this
must never block the GUI thread, same reasoning as `TtsWorker`/
`VoiceSearchWorker`/`SemanticSearchWorker`.
"""

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService


_NOT_CONFIGURED_MESSAGE = (
    "AI Agent is unavailable - check it's enabled and a real API key is "
    "set in Settings."
)


class AiAgentWorker(QThread):
    """Build (if needed, once) the AI Agent service and run one
    conversational turn, off the GUI thread."""

    answer_ready = Signal(str, object)  # answer_text, tool_calls_made: tuple[str, ...]
    answer_failed = Signal(str)  # user-facing error message - both failure cases below
    answer_unavailable = Signal(str)  # reason - only the "not configured" case, for a popup
    """Emitted only when get_service() returns None (not enabled, or no
    API key) - a real, actionable misconfiguration, distinct from a
    genuine mid-request runtime error (network/API failure), which stays
    inline-only via answer_failed since it's often transient/retry-worthy
    and less deserving of a hard interrupt."""

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
                self.answer_failed.emit(_NOT_CONFIGURED_MESSAGE)
                self.answer_unavailable.emit(_NOT_CONFIGURED_MESSAGE)
                return
            result = service.converse(self._question)
        except Exception:
            self.answer_failed.emit("Something went wrong answering that question.")
            return
        self.answer_ready.emit(result.answer, result.tool_calls_made)
