"""Background worker: run TTS synthesis off the GUI thread.

Loading a local MMS-TTS model and running real inference both cost real,
measured time (~1s model load once cached, ~10s synthesis for a typical
page, confirmed directly - see CHANGELOG) - neither may block the GUI
thread, same reasoning as `SemanticSearchWorker`.
"""

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.page_narration import PageNarrationService
from islamic_research_hub.infrastructure.audio.wav_writer import write_wav


class TtsWorker(QThread):
    """Build (if needed, once) the narration service, synthesize one page's
    text, and write it to a real temporary WAV file, off the GUI thread."""

    narration_ready = Signal(str, object)  # wav_path, request_key
    narration_failed = Signal(object)  # request_key

    def __init__(
        self,
        get_service: Callable[[], PageNarrationService | None],
        text: str,
        language: str | None,
        request_key: Any,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._text = text
        self._language = language
        self._request_key = request_key

    def run(self) -> None:
        try:
            service = self._get_service()
            if service is None:
                self.narration_failed.emit(self._request_key)
                return
            samples, sample_rate = service.narrate(self._text, self._language)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                wav_path = Path(handle.name)
            write_wav(wav_path, samples, sample_rate)
        except Exception:
            self.narration_failed.emit(self._request_key)
            return
        self.narration_ready.emit(str(wav_path), self._request_key)
