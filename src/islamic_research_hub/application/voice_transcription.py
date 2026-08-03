"""Application service for local speech-to-text transcription of a spoken
search query."""

import re
from typing import Protocol

_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
"""Matches Whisper's own auto-added punctuation (periods, commas, question
marks...) without touching real word characters in any script (Arabic/
Urdu/Latin letters, digits) - real bug found via this feature's own
end-to-end verification: a raw transcript like "hadith about prayer and
fasting." fed straight into the app's FTS5-backed search crashed both
title search and content search (FTS5's MATCH operator treats punctuation
as query syntax) - confirmed directly against the real database, not
assumed. Whisper reliably adds terminal punctuation to nearly every real
transcript, so without this the feature would work (no crash - title/
content search each already degrade to "no results"/a friendly error) but
practically never find anything - defeating the point of feeding transcripts
into "the existing keyword search pipeline" (PROJECT.md)."""


class VoiceTranscriber(Protocol):
    """Contract for turning a real spoken-audio waveform into text."""

    def transcribe(self, samples: tuple[float, ...], sample_rate: int) -> str:
        """Return the transcribed text for a real audio clip."""


class VoiceSearchService:
    """Validate a recorded clip and delegate to a transcriber.

    Deliberately a real service layer, not skipped, even though its
    validation surface is thinner than `PageNarrationService`'s language
    resolution - keeps the same Protocol+Service seam every other AI
    feature in this codebase uses, and gives callers (and their tests)
    one method to depend on.
    """

    def __init__(self, transcriber: VoiceTranscriber) -> None:
        self._transcriber = transcriber

    def transcribe_query(self, samples: tuple[float, ...], sample_rate: int) -> str:
        """Transcribe a recorded clip into search-ready query text.

        Raises `ValueError` if there's no real audio to transcribe (an
        empty clip), or if the transcript comes back blank (real silence
        that passed the recording-duration gate) - the same failure path
        as a hard transcriber error, so callers don't need a separate
        "silence" signal to handle.
        """
        if not samples:
            raise ValueError("Recorded audio must not be empty.")
        transcript = self._transcriber.transcribe(samples, sample_rate)
        without_punctuation = _PUNCTUATION_PATTERN.sub(" ", transcript)
        normalized_transcript = " ".join(without_punctuation.split())
        if not normalized_transcript:
            raise ValueError("No speech was recognized in the recording.")
        return normalized_transcript
