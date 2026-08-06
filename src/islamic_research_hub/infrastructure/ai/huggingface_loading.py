"""Shared "try the local cache first, only download on a genuine cache
miss" loading helper for local HuggingFace models.

Extracted from `mms_tts_speaker.py` (the first local model this project
shipped) so `marian_translator.py` doesn't duplicate the same two-branch
try/except - both need the exact same real behavior: no hang on an
unnecessary network check once a checkpoint is already cached, but still
able to download on a brand-new install.
"""

from __future__ import annotations

import logging
from typing import Callable, TypeVar

LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")


def load_offline_or_download(checkpoint: str, loader: Callable[[str, bool], _T]) -> _T:
    """Call `loader(checkpoint, local_files_only=True)` first; only retry
    with `local_files_only=False` (a real network download) if that raises.

    `loader` is a thin closure around a real `from_pretrained` call, e.g.
    `lambda name, local_only: AutoTokenizer.from_pretrained(name, local_files_only=local_only)`.
    """
    try:
        return loader(checkpoint, True)
    except Exception:
        LOGGER.info("Checkpoint %s not cached yet - downloading (first use only).", checkpoint)
        return loader(checkpoint, False)
