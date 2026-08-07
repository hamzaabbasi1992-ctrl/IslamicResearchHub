"""Local direct Arabic<->Urdu translation using Facebook's M2M100 model.

Phase 12 Milestone 2: Helsinki-NLP (used by `marian_translator.py` for
translation to English) has no direct Arabic<->Urdu pair - chaining
ar->en->ur through two separate models would compound their combined
translation error, not a real capability, just a guess. M2M100 is one
real model genuinely trained many-to-many across 100 languages,
including a direct Arabic<->Urdu path with no pivot - `facebook/
m2m100_418M` is the smallest real published checkpoint that still
covers both languages, matching this project's preference for small,
well-established, directly-trained models over the larger 1.2B variant
that wasn't justified for this corpus's real accuracy needs. Mirrors
`marian_translator.py`'s exact shape: one small model loaded lazily on
first real use, `load_offline_or_download()` for the cache-first load.
"""

import logging

import torch
from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer

from islamic_research_hub.infrastructure.ai.huggingface_loading import load_offline_or_download

LOGGER = logging.getLogger(__name__)

CHECKPOINT = "facebook/m2m100_418M"

LANGUAGE_CODES = {"Arabic": "ar", "Urdu": "ur"}
"""M2M100's own ISO language codes for the two real languages this
corpus has - the same set `DIRECT_TRANSLATION_TARGETS` in
`text_translation.py` already restricts real requests to."""

MAX_INPUT_TOKENS = 512
"""Same generous real-paragraph ceiling as `marian_translator.py` -
longer input is truncated rather than silently failing."""


class M2M100Translator:
    """Translate real Arabic/Urdu text directly into the other language,
    one shared M2M100 model loaded lazily on first real use."""

    def __init__(self) -> None:
        self._model: M2M100ForConditionalGeneration | None = None
        self._tokenizer: M2M100Tokenizer | None = None

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        """Return a real direct translation of `text` from
        `source_language` into `target_language`.

        Raises `KeyError` for a language with no entry in
        `LANGUAGE_CODES` - callers are expected to have already
        resolved a supported pair (see `PageTranslationService`).
        """
        model, tokenizer = self._get_or_load()
        tokenizer.src_lang = LANGUAGE_CODES[source_language]
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_INPUT_TOKENS)
        target_code = LANGUAGE_CODES[target_language]
        with torch.no_grad():
            generated_tokens = model.generate(
                **inputs,
                forced_bos_token_id=tokenizer.get_lang_id(target_code),
                max_new_tokens=MAX_INPUT_TOKENS,
            )
        return tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)[0]

    def _get_or_load(self) -> tuple[M2M100ForConditionalGeneration, M2M100Tokenizer]:
        if self._model is None:
            LOGGER.info("Loading direct translation model: %s", CHECKPOINT)
            self._model, self._tokenizer = _load_offline_or_download(CHECKPOINT)
        return self._model, self._tokenizer


def _load_offline_or_download(
    checkpoint: str,
) -> tuple[M2M100ForConditionalGeneration, M2M100Tokenizer]:
    def _load(name: str, local_only: bool) -> tuple[M2M100ForConditionalGeneration, M2M100Tokenizer]:
        model = M2M100ForConditionalGeneration.from_pretrained(name, local_files_only=local_only)
        tokenizer = M2M100Tokenizer.from_pretrained(name, local_files_only=local_only)
        return model, tokenizer

    return load_offline_or_download(checkpoint, _load)
