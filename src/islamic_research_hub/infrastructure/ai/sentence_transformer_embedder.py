"""Local multilingual text embedding adapter using sentence-transformers.

Requires the optional "ai" dependency group (`pip install -e .[ai]`).
"""

import logging
import os

# Must run before `sentence_transformers`/`transformers`/`huggingface_hub`
# are imported below - confirmed for real (a ~30 second hang on a bad
# connection) that these libraries read HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE
# at *import time*, not per-call, so setting them later (e.g. inside
# __init__, after the `from sentence_transformers import ...` below has
# already run) is too late and a network HEAD request still goes out. The
# model is already downloaded/cached after the first real run, so offline
# loading is correct here regardless of whether a network is available.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "3")

from sentence_transformers import SentenceTransformer  # noqa: E402

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class SentenceTransformerEmbedder:
    """Embed text locally using a multilingual sentence-transformers model."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        LOGGER.info("Loading embedding model: %s", model_name)
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return one normalized embedding vector per input text, in order."""
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return tuple(tuple(float(value) for value in vector) for vector in vectors)
