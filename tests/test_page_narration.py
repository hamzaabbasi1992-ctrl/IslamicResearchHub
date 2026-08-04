"""Tests for the PageNarrationService application layer."""

import pytest

from islamic_research_hub.application.page_narration import PageNarrationService


class FakeTtsSpeaker:
    """Speaker returning a fixed waveform, recording what it was asked to say."""

    def __init__(self) -> None:
        self.last_text: str | None = None
        self.last_language: str | None = None

    def synthesize(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
        """Record the input and return one fixed, tiny waveform."""
        self.last_text = text
        self.last_language = language
        return (0.1, 0.2, 0.1), 16000


def test_narrate_normalizes_whitespace_and_delegates() -> None:
    """Extra whitespace is collapsed before reaching the speaker."""
    speaker = FakeTtsSpeaker()

    samples, sample_rate = PageNarrationService(speaker).narrate("  hello   world  ", "English")

    assert speaker.last_text == "hello world"
    assert speaker.last_language == "English"
    assert samples == (0.1, 0.2, 0.1)
    assert sample_rate == 16000


def test_narrate_strips_raw_structural_markup_before_speaking() -> None:
    """Real gap found investigating this: ~471,000 real pages (mostly
    Maktaba Jibreel) still carry raw tags like '<urh1>...</urh1>' that
    render invisibly in the Qt viewer but would be read aloud literally
    if not stripped first."""
    speaker = FakeTtsSpeaker()

    PageNarrationService(speaker).narrate("<urh1>تتمہ</urh1> کفایت المفتی", "Urdu")

    assert "<" not in speaker.last_text
    assert ">" not in speaker.last_text
    assert "تتمہ" in speaker.last_text
    assert "کفایت المفتی" in speaker.last_text


def test_narrate_normalizes_known_language_variants() -> None:
    """'ur' and 'Urdu' route to the same canonical language, matching
    TaxonomyRepository's own normalization - not treated as two languages."""
    speaker = FakeTtsSpeaker()
    service = PageNarrationService(speaker)

    service.narrate("متن", "ur")
    assert speaker.last_language == "Urdu"

    service.narrate("متن", "Urdu")
    assert speaker.last_language == "Urdu"


def test_narrate_falls_back_to_script_detection_when_language_is_missing() -> None:
    """~9% of this corpus has no recorded Books.Language - a real script-based
    fallback is used instead of failing outright."""
    speaker = FakeTtsSpeaker()
    service = PageNarrationService(speaker)

    service.narrate("یہ اردو کا متن ہے", None)
    assert speaker.last_language == "Urdu"

    service.narrate("هذا نص عربي", None)
    assert speaker.last_language == "Arabic"

    service.narrate("This is English text", None)
    assert speaker.last_language == "English"


def test_narrate_rejects_blank_text() -> None:
    """Text that's blank (or becomes blank after stripping markup) is
    rejected before ever reaching the speaker."""
    with pytest.raises(ValueError):
        PageNarrationService(FakeTtsSpeaker()).narrate("   ", "English")


def test_narrate_rejects_text_that_is_pure_markup() -> None:
    """Text with no real content once markup is stripped is still blank."""
    with pytest.raises(ValueError):
        PageNarrationService(FakeTtsSpeaker()).narrate("<urref>\n</urref>", "Urdu")


def test_prepare_chunked_narration_resolves_language_and_splits_without_synthesizing() -> None:
    """The whole point of the "prepare" step is that it's cheap - it must
    never call the speaker itself."""
    speaker = FakeTtsSpeaker()

    plan = PageNarrationService(speaker).prepare_chunked_narration("hello world", "ur")

    assert plan.language == "Urdu"
    assert plan.chunk_texts == ("hello world",)
    assert speaker.last_text is None


def test_prepare_chunked_narration_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        PageNarrationService(FakeTtsSpeaker()).prepare_chunked_narration("   ", "English")


def test_prepare_chunked_narration_aligns_chunks_to_real_line_structure() -> None:
    speaker = FakeTtsSpeaker()

    plan = PageNarrationService(speaker).prepare_chunked_narration(
        "<span class='mb1'>مقدمہ</span><br>باقی متن", "Urdu"
    )

    assert plan.chunk_texts == ("مقدمہ", "باقی متن")


def test_synthesize_chunk_is_a_pure_pass_through_to_the_speaker() -> None:
    speaker = FakeTtsSpeaker()

    samples, sample_rate = PageNarrationService(speaker).synthesize_chunk("a chunk", "English")

    assert speaker.last_text == "a chunk"
    assert speaker.last_language == "English"
    assert samples == (0.1, 0.2, 0.1)
    assert sample_rate == 16000
