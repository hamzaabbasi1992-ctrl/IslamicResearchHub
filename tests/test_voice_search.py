"""Tests for the VoiceSearchService application layer."""

import pytest

from islamic_research_hub.application.voice_transcription import VoiceSearchService


class FakeVoiceTranscriber:
    """Transcriber returning a fixed string, recording what it was asked to transcribe."""

    def __init__(self, transcript: str = "some query") -> None:
        self._transcript = transcript
        self.last_samples: tuple[float, ...] | None = None
        self.last_sample_rate: int | None = None

    def transcribe(self, samples: tuple[float, ...], sample_rate: int) -> str:
        self.last_samples = samples
        self.last_sample_rate = sample_rate
        return self._transcript


def test_transcribe_query_normalizes_whitespace_and_delegates() -> None:
    transcriber = FakeVoiceTranscriber("  mercy   and forgiveness  ")

    transcript = VoiceSearchService(transcriber).transcribe_query((0.1, 0.2), 16000)

    assert transcript == "mercy and forgiveness"
    assert transcriber.last_samples == (0.1, 0.2)
    assert transcriber.last_sample_rate == 16000


def test_transcribe_query_rejects_empty_samples() -> None:
    with pytest.raises(ValueError):
        VoiceSearchService(FakeVoiceTranscriber()).transcribe_query((), 16000)


def test_transcribe_query_strips_punctuation() -> None:
    """Real bug found via end-to-end verification: Whisper's own transcripts
    reliably include auto-added punctuation ("hadith about prayer.") that
    crashes the app's FTS5-backed search (MATCH treats it as query syntax) -
    stripped here so a spoken query actually finds results, not just avoids
    crashing."""
    transcriber = FakeVoiceTranscriber("Hadith, about prayer's and fasting!")

    transcript = VoiceSearchService(transcriber).transcribe_query((0.1,), 16000)

    assert transcript == "Hadith about prayer s and fasting"


def test_transcribe_query_preserves_arabic_and_urdu_word_characters() -> None:
    """Punctuation-stripping must not touch real Arabic/Urdu text."""
    transcriber = FakeVoiceTranscriber("تفسير القرآن الكريم.")

    transcript = VoiceSearchService(transcriber).transcribe_query((0.1,), 16000)

    assert transcript == "تفسير القرآن الكريم"


def test_transcribe_query_rejects_blank_transcript() -> None:
    """Real silence that passed the recording-duration gate - the transcriber
    returns nothing usable, and that's the same failure path as a hard
    transcriber error, not a separate "silence" signal."""
    with pytest.raises(ValueError):
        VoiceSearchService(FakeVoiceTranscriber("   ")).transcribe_query((0.1,), 16000)
