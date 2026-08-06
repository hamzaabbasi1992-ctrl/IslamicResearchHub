"""Local text-to-English translation adapter using Helsinki-NLP's
MarianMT models.

Requires the optional "translation" dependency group
(`pip install -e .[translation]`). Mirrors `mms_tts_speaker.py`'s exact
shape (one small model per source language, loaded lazily on first real
use, `load_offline_or_download()` for the cache-first load).
"""

import logging

import torch
from transformers import MarianMTModel, MarianTokenizer

from islamic_research_hub.infrastructure.ai.huggingface_loading import load_offline_or_download

LOGGER = logging.getLogger(__name__)

CHECKPOINTS_BY_SOURCE_LANGUAGE = {
    "Arabic": "Helsinki-NLP/opus-mt-ar-en",
    "Urdu": "Helsinki-NLP/opus-mt-ur-en",
}
"""English is deliberately the only real target for Milestone 1 - it's
the one language pair with small, well-established, directly-trained
models for both real source languages this corpus has. Helsinki-NLP has
no direct Arabic<->Urdu pair; forcing one through a two-hop pivot (e.g.
ar->en->ur) would compound translation error and isn't a real capability
yet, just a guess - out of scope until it's been properly evaluated."""

MAX_INPUT_TOKENS = 512
"""A generous real paragraph's worth of text - MarianMT's own trained
sequence length ceiling for these checkpoints; longer input is truncated
rather than silently failing."""


class MarianTranslator:
    """Translate real Arabic/Urdu text to English locally, one small
    MarianMT model loaded per source language on first real use."""

    def __init__(self) -> None:
        self._models: dict[str, MarianMTModel] = {}
        self._tokenizers: dict[str, MarianTokenizer] = {}

    def translate_to_english(self, text: str, source_language: str) -> str:
        """Return a real English translation of `text`.

        Raises `KeyError` for a source language with no checkpoint in
        `CHECKPOINTS_BY_SOURCE_LANGUAGE` - callers are expected to have
        already resolved a supported language (see `PageTranslationService`).
        """
        model, tokenizer = self._get_or_load(source_language)
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_INPUT_TOKENS)
        with torch.no_grad():
            translated_tokens = model.generate(**inputs, max_new_tokens=MAX_INPUT_TOKENS)
        return tokenizer.decode(translated_tokens[0], skip_special_tokens=True)

    def _get_or_load(self, source_language: str) -> tuple[MarianMTModel, MarianTokenizer]:
        if source_language not in self._models:
            checkpoint = CHECKPOINTS_BY_SOURCE_LANGUAGE[source_language]
            LOGGER.info("Loading translation model for %s: %s", source_language, checkpoint)
            model, tokenizer = _load_offline_or_download(checkpoint)
            self._models[source_language] = model
            self._tokenizers[source_language] = tokenizer
        return self._models[source_language], self._tokenizers[source_language]


def _load_offline_or_download(checkpoint: str) -> tuple[MarianMTModel, MarianTokenizer]:
    def _load(name: str, local_only: bool) -> tuple[MarianMTModel, MarianTokenizer]:
        model = MarianMTModel.from_pretrained(name, local_files_only=local_only)
        tokenizer = MarianTokenizer.from_pretrained(name, local_files_only=local_only)
        return model, tokenizer

    return load_offline_or_download(checkpoint, _load)
