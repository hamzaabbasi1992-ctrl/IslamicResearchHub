"""Background worker: generate real scholarly book reviews off the GUI thread."""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.book_review_extraction import (
    ExtractedBookReview,
    parse_extracted_book_review,
)

LOGGER = logging.getLogger(__name__)


class BookReviewWorker(QThread):
    """Generate scholarly book reviews off the GUI thread."""

    generation_finished = Signal(object)  # ExtractedBookReview | None
    generation_unavailable = Signal(str)

    def __init__(
        self,
        get_service: Callable[[], AiAgentService | None],
        book_title: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._book_title = book_title

    def run(self) -> None:
        service = self._get_service()
        if service is None:
            self.generation_unavailable.emit(
                "AI Agent is unavailable - check it's enabled and an API key is set."
            )
            return

        try:
            prompt = f"Generate a scholarly book review for the book: {self._book_title}"
            result = service.answer_question(prompt)
            review = parse_extracted_book_review(result.answer)
            self.generation_finished.emit(review)
        except Exception as err:
            LOGGER.warning("Book review generation failed: %s", err)
            self.generation_finished.emit(None)
