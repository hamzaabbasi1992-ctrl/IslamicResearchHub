"""Local text-to-speech adapter using Meta's MMS-TTS models (VITS architecture).

Requires the optional "tts" dependency group (`pip install -e .[tts]`).
"""

import logging
import os

# Must run before `transformers`/`huggingface_hub` are imported below - same
# real bug class already fixed once for `SentenceTransformerEmbedder`: these
# libraries read HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE at *import time*, not
# per-call, so setting them after import is too late and a network request
# still goes out. Each checkpoint is small (~140MB) and cached after its
# first real load, so offline loading is correct regardless of whether a
# network is available at the time.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "3")

import torch  # noqa: E402
from transformers import AutoTokenizer, VitsModel  # noqa: E402

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
            self._models[language] = VitsModel.from_pretrained(checkpoint)
            self._tokenizers[language] = AutoTokenizer.from_pretrained(checkpoint)
        return self._models[language], self._tokenizers[language]
