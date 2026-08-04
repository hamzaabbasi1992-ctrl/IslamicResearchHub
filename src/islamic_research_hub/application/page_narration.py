"""Application service for local text-to-speech narration of page content."""

from typing import NamedTuple, Protocol

from islamic_research_hub.application.tts_text_chunking import chunk_narration_text
from islamic_research_hub.shared.html_text_extraction import strip_html_to_text
from islamic_research_hub.shared.language_names import (
    canonical_language_name,
    detect_language_from_text,
)


class TtsSpeaker(Protocol):
    """Contract for turning text into a synthesized speech waveform."""

    def synthesize(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
        """Return (samples, sample_rate) for the given text, spoken in `language`."""


class ChunkedNarrationPlan(NamedTuple):
    """A page's narration text, split into TTS-sized chunks with the
    resolved language - everything `TtsWorker` needs to synthesize and
    play the page chunk by chunk."""

    language: str
    chunk_texts: tuple[str, ...]


class PageNarrationService:
    """Validate and normalize a narration request, then delegate to a speaker.

    `language` is resolved here, not left to the caller: a raw
    `Books.Language` value is normalized via the same canonical map
    `TaxonomyRepository` uses (so "ur"/"Urdu" are never treated as two
    different languages), and a missing value falls back to a real
    script-based heuristic rather than failing outright - about 9% of
    this corpus has no recorded `Language` at all.
    """

    def __init__(self, speaker: TtsSpeaker) -> None:
        self._speaker = speaker

    def narrate(self, text: str, language: str | None) -> tuple[tuple[float, ...], int]:
        """Synthesize speech for one page's real content.

        `text` is run through `strip_html_to_text` first - real page
        content from some libraries (confirmed: ~471,000 pages, mostly
        Maktaba Jibreel) still carries raw structural markup tags
        (`<urh1>...`) that render invisibly in the Qt viewer but would be
        read aloud literally if not stripped first.
        """
        plain_text = strip_html_to_text(text) or ""
        normalized_text = " ".join(plain_text.split())
        if not normalized_text:
            raise ValueError("Narration text must not be empty.")
        resolved_language = canonical_language_name(language) or detect_language_from_text(
            normalized_text
        )
        return self._speaker.synthesize(normalized_text, resolved_language)

    def prepare_chunked_narration(self, text: str, language: str | None) -> ChunkedNarrationPlan:
        """Resolve language and split `text` into TTS-sized chunks, doing no synthesis.

        Mirrors `narrate()`'s own text handling (HTML stripping, blank-text
        rejection, language resolution) so the two paths never disagree
        about what counts as this page's real content - it only diverges
        by chunking instead of collapsing everything into one blob, and by
        not calling the speaker itself. Synthesis is left to the caller
        (`synthesize_chunk()`) so it can check for cancellation between
        chunks - the expensive step.
        """
        plain_text = strip_html_to_text(text) or ""
        chunk_texts = chunk_narration_text(plain_text)
        if not chunk_texts:
            raise ValueError("Narration text must not be empty.")
        collapsed_text = " ".join(plain_text.split())
        resolved_language = canonical_language_name(language) or detect_language_from_text(
            collapsed_text
        )
        return ChunkedNarrationPlan(language=resolved_language, chunk_texts=chunk_texts)

    def synthesize_chunk(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
        """Synthesize one already-chunked piece of text."""
        return self._speaker.synthesize(text, language)
