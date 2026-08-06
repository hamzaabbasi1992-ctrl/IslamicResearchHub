"""Translate a real passage of book text to English.

Milestone 1 of Phase 12 (Translation engine) - deliberately scoped down
from the full "Arabic -> Urdu -> English chain, plus word-by-word
breakdown, grammar notes, and root-word analysis" described in
PROJECT.md: just a real, working "translate this passage to English"
first, on real local models, before layering on anything else. Local by
default per this project's AI provider policy (see PROJECT.md) - no
cloud upgrade path exists yet for this specific capability.
"""

from typing import Protocol

SUPPORTED_SOURCE_LANGUAGES = frozenset({"Arabic", "Urdu"})


class TextTranslator(Protocol):
    """Port for a real local (or, later, cloud) translation backend."""

    def translate_to_english(self, text: str, source_language: str) -> str: ...


class PageTranslationService:
    """Validates input, then delegates to a real `TextTranslator`."""

    def __init__(self, translator: TextTranslator) -> None:
        self._translator = translator

    def translate_to_english(self, text: str, source_language: str) -> str:
        """Return a real English translation of `text`.

        Raises `ValueError` for blank text or an unsupported source
        language - callers should check `SUPPORTED_SOURCE_LANGUAGES`
        themselves to decide whether to offer translation at all, this
        is the safety net.
        """
        normalized = text.strip()
        if not normalized:
            raise ValueError("Text must not be empty.")
        if source_language not in SUPPORTED_SOURCE_LANGUAGES:
            raise ValueError(f"Unsupported source language: {source_language!r}")
        return self._translator.translate_to_english(normalized, source_language)
