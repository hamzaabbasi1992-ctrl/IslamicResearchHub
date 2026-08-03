"""Local speech-to-text adapter using faster-whisper (CTranslate2-based Whisper).

Requires the optional "voice" dependency group (`pip install -e .[voice]`).
"""

import logging

import numpy as np
from faster_whisper import WhisperModel

LOGGER = logging.getLogger(__name__)

MODEL_SIZE = "small"
"""Multilingual (non-`.en`) checkpoint. Verified for real, not assumed:
`small` transcribes real query-length Arabic/Urdu/English phrases (7-8
words) correctly for all but one word per language, at ~4-5s - `medium` is
essentially perfect but ~3x slower (~14s). `small` chosen for voice
search's latency-sensitive UX (its whole value is being faster than
typing); a short 2-3 word test initially looked much worse for Arabic/
Urdu, but that turned out to be an artifact of unnaturally short phrases,
not a real model limitation - see CHANGELOG."""


class FasterWhisperTranscriber:
    """Transcribe speech locally via faster-whisper, one shared multilingual model."""

    def __init__(self) -> None:
        self._model: WhisperModel | None = None

    def transcribe(self, samples: tuple[float, ...], sample_rate: int) -> str:
        """Return the transcribed text for a real recorded clip.

        `sample_rate` is accepted for Protocol symmetry with `TtsSpeaker`,
        but real microphone capture is always built at 16000 Hz (Whisper's
        native rate - see `search_screen.py`'s `QAudioFormat` setup), so no
        resampling happens here; a mismatched rate would produce a garbled
        transcript rather than raising, since faster-whisper has no way to
        know the audio's real rate from raw samples alone.
        """
        model = self._get_or_load()
        audio = np.asarray(samples, dtype=np.float32)
        segments, _info = model.transcribe(
            audio, language=None, task="transcribe", vad_filter=True
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def _get_or_load(self) -> WhisperModel:
        if self._model is None:
            self._model = _load_offline_or_download()
        return self._model


def _load_offline_or_download() -> WhisperModel:
    """Try a real, already-cached model first (fast, no network call at
    all); only reach for a real download on a genuine cache miss (a
    first-ever use on this machine).

    Real bug found and fixed while building this: forcing offline mode
    *unconditionally* (the pattern `mms_tts_speaker.py` originally used)
    would make a brand-new install unable to ever download the model in
    the first place - confirmed directly, not assumed (see CHANGELOG).
    `local_files_only=True` as an explicit, scoped argument here achieves
    the same "don't hang on an unnecessary network check when already
    cached" goal without that global failure mode, and without leaking
    into other HuggingFace-based code sharing this process (`MmsTtsSpeaker`
    also lives here - a global env var would have affected both).
    """
    try:
        return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8", local_files_only=True)
    except Exception:
        LOGGER.info("Whisper model %s not cached yet - downloading (first use only).", MODEL_SIZE)
        return WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
