"""Background worker: generate a real narrated-podcast audio track for
one book, off the GUI thread.

Two real phases, each reusing existing infrastructure rather than
building new plumbing: (1) chunk-by-chunk AI script generation
(`AiAgentService.generate_podcast_script()`, mirrors the other chunked
extraction/generation workers' cancellation and partial-failure
discipline), then (2) the full script handed to the same chunked TTS
synthesis path `TtsWorker` uses (`PageNarrationService.
prepare_chunked_narration()`/`synthesize_chunk()`) - the one real
difference being every synthesized chunk's samples are concatenated
into a single track here, instead of being written to separate
temp-file chunks for progressive playback.
"""

import logging
from collections.abc import Callable

from PySide6.QtCore import QThread, Signal

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.application.page_narration import PageNarrationService

LOGGER = logging.getLogger(__name__)


class PodcastGenerationWorker(QThread):
    """Generate a real narration script for one book, then synthesize it
    into one real audio track, off the GUI thread."""

    script_chunk_processed = Signal(int, int)  # done, total
    narration_chunk_processed = Signal(int, int)  # done, total
    generation_finished = Signal(object, int)  # samples: tuple[float, ...], sample_rate
    generation_unavailable = Signal(str)  # reason - a service is None, not configured
    generation_failed = Signal(str)  # reason - no real script/audio could be produced

    def __init__(
        self,
        get_ai_service: Callable[[], AiAgentService | None],
        get_tts_service: Callable[[], PageNarrationService | None],
        book_id: int,
        chunks: tuple[tuple[int, int], ...],
        language: str | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._get_ai_service = get_ai_service
        self._get_tts_service = get_tts_service
        self._book_id = book_id
        self._chunks = chunks
        self._language = language

    def request_cancellation(self) -> None:
        """Ask a still-running worker to stop before its next chunk's
        generation/synthesis (the expensive, non-interruptible step)."""
        self.requestInterruption()

    def run(self) -> None:
        ai_service = self._get_ai_service()
        if ai_service is None:
            self.generation_unavailable.emit(
                "AI Agent is unavailable - check it's enabled and a real "
                "API key is set in Settings."
            )
            return
        tts_service = self._get_tts_service()
        if tts_service is None:
            self.generation_unavailable.emit(
                "Text-to-speech is unavailable - check the optional "
                "'tts' dependency group is installed."
            )
            return

        script = self._generate_script(ai_service)
        if self.isInterruptionRequested():
            return
        if not script.strip():
            self.generation_failed.emit(
                "No real narratable content was found in this book."
            )
            return

        self._synthesize_script(tts_service, script)

    def _generate_script(self, ai_service: AiAgentService) -> str:
        segments: list[str] = []
        total = len(self._chunks)
        for index, (start_page, end_page) in enumerate(self._chunks):
            if self.isInterruptionRequested():
                break
            try:
                result = ai_service.generate_podcast_script(self._book_id, start_page, end_page)
                segment = result.answer.strip()
                if segment:
                    segments.append(segment)
            except Exception:
                LOGGER.warning(
                    "Podcast script generation failed for book_id=%d pages %d-%d; skipping this chunk.",
                    self._book_id,
                    start_page,
                    end_page,
                )
            self.script_chunk_processed.emit(index + 1, total)
        return "\n\n".join(segments)

    def _synthesize_script(self, tts_service: PageNarrationService, script: str) -> None:
        try:
            plan = tts_service.prepare_chunked_narration(script, self._language)
        except ValueError:
            self.generation_failed.emit("No real narratable content was found in this book.")
            return

        all_samples: list[float] = []
        sample_rate: int | None = None
        total = len(plan.chunk_texts)
        for index, chunk_text in enumerate(plan.chunk_texts):
            if self.isInterruptionRequested():
                break
            try:
                samples, chunk_sample_rate = tts_service.synthesize_chunk(chunk_text, plan.language)
                all_samples.extend(samples)
                sample_rate = chunk_sample_rate
            except Exception:
                LOGGER.warning(
                    "Podcast narration synthesis failed for chunk %d/%d; skipping.",
                    index + 1,
                    total,
                )
            self.narration_chunk_processed.emit(index + 1, total)

        if not all_samples or sample_rate is None:
            self.generation_failed.emit("Narration synthesis produced no real audio.")
            return
        self.generation_finished.emit(tuple(all_samples), sample_rate)
