"""Background worker: run text translation off the GUI thread.

Loading a local MarianMT model costs real, measured-elsewhere-in-this-
project time (the same class of cost as `TtsWorker`'s MMS-TTS model load)
- must not block the GUI thread. Unlike TTS's chunked streaming, a single
selection's translation is one request/response - no chunking needed.
"""

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.text_translation import PageTranslationService

LOGGER = logging.getLogger(__name__)


class TranslationWorker(QThread):
    """Build (if needed, once) the translation service and translate one
    selection, off the GUI thread."""

    translation_ready = Signal(str, object)  # translated_text, request_key
    translation_failed = Signal(object)  # request_key
    translation_unavailable = Signal(object)  # request_key - service is None (not configured)

    def __init__(
        self,
        get_service: Callable[[], PageTranslationService | None],
        text: str,
        source_language: str,
        request_key: Any,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._text = text
        self._source_language = source_language
        self._request_key = request_key

    def run(self) -> None:
        service = self._get_service()
        if service is None:
            self.translation_unavailable.emit(self._request_key)
            return
        try:
            translated = service.translate_to_english(self._text, self._source_language)
        except Exception:
            LOGGER.exception("Translation failed.")
            self.translation_failed.emit(self._request_key)
            return
        self.translation_ready.emit(translated, self._request_key)
