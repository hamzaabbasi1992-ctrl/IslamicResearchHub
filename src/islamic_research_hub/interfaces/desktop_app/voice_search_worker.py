"""Background worker: run voice-query transcription off the GUI thread.

Loading a local Whisper model and running real inference both cost real
time (multi-second, even on a short clip) - neither may block the GUI
thread, same reasoning as `TtsWorker`/`SemanticSearchWorker`.
"""

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.voice_transcription import VoiceSearchService


class VoiceSearchWorker(QThread):
    """Build (if needed, once) the voice search service and transcribe one
    recorded clip, off the GUI thread.

    Deliberately simpler than `TtsWorker`: no `request_key`. The mic button
    is disabled for the whole recording+transcribing cycle, so overlapping
    requests can't happen structurally - a considered simplification, not
    an oversight.
    """

    transcription_ready = Signal(str)
    transcription_failed = Signal()

    def __init__(
        self,
        get_service: Callable[[], VoiceSearchService | None],
        samples: tuple[float, ...],
        sample_rate: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_service = get_service
        self._samples = samples
        self._sample_rate = sample_rate

    def run(self) -> None:
        try:
            service = self._get_service()
            if service is None:
                self.transcription_failed.emit()
                return
            transcript = service.transcribe_query(self._samples, self._sample_rate)
        except Exception:
            self.transcription_failed.emit()
            return
        self.transcription_ready.emit(transcript)
