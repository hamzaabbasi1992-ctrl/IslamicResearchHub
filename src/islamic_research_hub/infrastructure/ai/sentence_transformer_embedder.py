"""Local multilingual text embedding adapter using sentence-transformers.

Requires the optional "ai" dependency group (`pip install -e .[ai]`).
"""

import logging

from sentence_transformers import SentenceTransformer

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
