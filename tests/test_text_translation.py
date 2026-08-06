"""Tests for the PageTranslationService application layer."""

import pytest

from islamic_research_hub.application.text_translation import (
    SUPPORTED_SOURCE_LANGUAGES,
    PageTranslationService,
)


class FakeTranslator:
    """Translator returning a fixed string, recording what it was asked to translate."""

    def __init__(self) -> None:
        self.last_text: str | None = None
        self.last_source_language: str | None = None

    def translate_to_english(self, text: str, source_language: str) -> str:
        self.last_text = text
        self.last_source_language = source_language
        return f"[EN] {text}"


def test_translate_to_english_strips_and_delegates() -> None:
    translator = FakeTranslator()

    result = PageTranslationService(translator).translate_to_english(
        "  hello world  ", "Arabic"
    )

    assert translator.last_text == "hello world"
    assert translator.last_source_language == "Arabic"
    assert result == "[EN] hello world"


def test_translate_to_english_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        PageTranslationService(FakeTranslator()).translate_to_english("   ", "Arabic")


def test_translate_to_english_rejects_an_unsupported_source_language() -> None:
    with pytest.raises(ValueError):
        PageTranslationService(FakeTranslator()).translate_to_english("hello", "English")


def test_supported_source_languages_are_the_corpus_real_languages() -> None:
    assert SUPPORTED_SOURCE_LANGUAGES == {"Arabic", "Urdu"}
