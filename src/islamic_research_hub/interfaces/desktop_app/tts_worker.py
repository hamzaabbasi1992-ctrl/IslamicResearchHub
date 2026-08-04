"""Background worker: run TTS synthesis off the GUI thread.

Loading a local MMS-TTS model and running real inference both cost real,
measured time (~1s model load once cached, ~10s synthesis per ~250-char
chunk, confirmed directly - see CHANGELOG) - neither may block the GUI
thread, same reasoning as `SemanticSearchWorker`.

Synthesizes chunk by chunk (not the whole page in one call) so playback
can start on chunk 1 while later chunks are still synthesizing - a real
1,978-character page previously took ~79s of silence before any sound
played. `PageNarrationService.prepare_chunked_narration()` does the cheap
text-splitting; each chunk's actual synthesis is checked against
`isInterruptionRequested()` first, since that's the expensive,
non-cancellable-mid-call step (a single `VitsModel` forward pass can't be
killed once started - chunks are kept small precisely so cancellation
latency stays bounded to one chunk's synthesis time).
"""

import logging
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.page_narration import PageNarrationService
from islamic_research_hub.infrastructure.audio.wav_writer import write_wav

LOGGER = logging.getLogger(__name__)


class TtsWorker(QThread):
    """Build (if needed, once) the narration service and synthesize one
    page's text chunk by chunk, off the GUI thread, writing each chunk to
    its own real temporary WAV file as it completes."""

    chunk_ready = Signal(str, int, bool, object)  # wav_path, chunk_index, is_last, request_key
    narration_failed = Signal(object)  # request_key - only when no chunk at all could be produced
    narration_finished = Signal(object, int)  # request_key, chunks_produced - always emitted once

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

    def request_cancellation(self) -> None:
        """Ask a still-running worker to stop before its next chunk's
        synthesis. Already-written chunk files are left for the caller to
        clean up."""
        self.requestInterruption()

    def run(self) -> None:
        chunks_produced = 0
        try:
            service = self._get_service()
            if service is None:
                self.narration_failed.emit(self._request_key)
                return
            try:
                plan = service.prepare_chunked_narration(self._text, self._language)
            except ValueError:
                self.narration_failed.emit(self._request_key)
                return
            total = len(plan.chunk_texts)
            temp_dir: Path | None = None
            for index, chunk_text in enumerate(plan.chunk_texts):
                if self.isInterruptionRequested():
                    break
                try:
                    samples, sample_rate = service.synthesize_chunk(chunk_text, plan.language)
                    if temp_dir is None:
                        temp_dir = Path(tempfile.mkdtemp(prefix="irh_tts_"))
                    wav_path = temp_dir / f"chunk_{index:04d}.wav"
                    write_wav(wav_path, samples, sample_rate)
                except Exception:
                    # Covers both a real synthesis failure and the rare race
                    # where the caller cancels and cleans up the chunk
                    # directory between chunks (a fast page turn) while a
                    # write to it is still in flight - either way, stop
                    # producing more chunks rather than crashing the thread.
                    if index == 0:
                        self.narration_failed.emit(self._request_key)
                    else:
                        LOGGER.warning(
                            "TTS chunk %d/%d failed; stopping this page's narration early.",
                            index + 1,
                            total,
                        )
                    break
                chunks_produced += 1
                self.chunk_ready.emit(str(wav_path), index, index == total - 1, self._request_key)
        finally:
            self.narration_finished.emit(self._request_key, chunks_produced)
