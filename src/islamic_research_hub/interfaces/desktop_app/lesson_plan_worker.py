"""Background worker: generate educational lesson plans off the GUI thread."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.lesson_plan_generator import (
    ExtractedLessonPlan,
    parse_extracted_lesson_plan,
)

LOGGER = logging.getLogger(__name__)


class LessonPlanWorker(QThread):
    """Generate educational lesson plans off the GUI thread."""

    generation_finished = Signal(object)  # ExtractedLessonPlan | None
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
            prompt = f"Generate a structured teaching lesson plan for topic: {self._topic}"
            result = service.answer_question(prompt)
            plan = parse_extracted_lesson_plan(result.answer)
            self.generation_finished.emit(plan)
        except Exception as err:
            LOGGER.warning("Lesson plan generation failed: %s", err)
            self.generation_finished.emit(None)
