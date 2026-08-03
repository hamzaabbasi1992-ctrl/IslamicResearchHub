"""Local text-to-speech adapter using Meta's MMS-TTS models (VITS architecture).

Requires the optional "tts" dependency group (`pip install -e .[tts]`).
"""

import logging

import torch
from transformers import AutoTokenizer, VitsModel

LOGGER = logging.getLogger(__name__)

CHECKPOINTS_BY_LANGUAGE = {
    "Arabic": "facebook/mms-tts-ara",
    "Urdu": "facebook/mms-tts-urd-script_arabic",
    "English": "facebook/mms-tts-eng",
}
"""One MMS-TTS checkpoint per language this corpus actually has - confirmed
directly (not assumed) to all load, both online and offline-from-cache, and
to produce real, non-silent audio for genuine Arabic and Urdu page content.
Urdu uses the Arabic-script checkpoint, matching this corpus's real script
usage - `facebook/mms-tts-urd-script_devanagari` is a different, unused
checkpoint for Devanagari-script Urdu, which doesn't occur in this corpus."""


class MmsTtsSpeaker:
    """Synthesize speech locally via MMS-TTS, one model loaded per language.

    Each language's checkpoint (~140MB, ~36M parameters) is loaded lazily on
    first use of that language, not all three eagerly at construction - a
    session that only ever reads Arabic books shouldn't pay the Urdu/English
    load cost.
    """

    def __init__(self) -> None:
        self._models: dict[str, VitsModel] = {}
        self._tokenizers: dict[str, object] = {}

    def synthesize(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
        """Return (samples, sample_rate) for `text`, spoken in `language`.

        Raises `KeyError` for a language with no checkpoint in
        `CHECKPOINTS_BY_LANGUAGE` - callers are expected to have already
        resolved a supported language (see `PageNarrationService`).
        """
        model, tokenizer = self._get_or_load(language)
        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            waveform = model(**inputs).waveform
        samples = waveform.squeeze().tolist()
        return tuple(samples), model.config.sampling_rate

    def _get_or_load(self, language: str) -> tuple[VitsModel, object]:
        if language not in self._models:
            checkpoint = CHECKPOINTS_BY_LANGUAGE[language]
            LOGGER.info("Loading TTS model for %s: %s", language, checkpoint)
            model, tokenizer = _load_offline_or_download(checkpoint)
            self._models[language] = model
            self._tokenizers[language] = tokenizer
        return self._models[language], self._tokenizers[language]


def _load_offline_or_download(checkpoint: str) -> tuple[VitsModel, object]:
    """Try a real, already-cached checkpoint first (fast, no network call
    at all); only reach for a real download on a genuine cache miss (a
    first-ever use on this machine).

    Real bug found and fixed: this used to force offline mode
    *unconditionally* via `os.environ.setdefault("HF_HUB_OFFLINE", "1")`
    before any import - confirmed directly (not assumed) that this made a
    brand-new install unable to ever download a checkpoint in the first
    place, since offline mode was already forced before the very first
    real load could happen. `local_files_only=True` as an explicit, scoped
    argument here achieves the original goal (don't hang on an
    unnecessary network check once already cached) without that failure
    mode, and without leaking into other HuggingFace-based code sharing
    this process (`FasterWhisperTranscriber` also lives in this package -
    a global env var would have silently affected it too).
    """
    try:
        model = VitsModel.from_pretrained(checkpoint, local_files_only=True)
        tokenizer = AutoTokenizer.from_pretrained(checkpoint, local_files_only=True)
        return model, tokenizer
    except Exception:
        LOGGER.info("TTS checkpoint %s not cached yet - downloading (first use only).", checkpoint)
        model = VitsModel.from_pretrained(checkpoint)
        tokenizer = AutoTokenizer.from_pretrained(checkpoint)
        return model, tokenizer
