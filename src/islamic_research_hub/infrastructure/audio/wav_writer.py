"""Write a synthesized speech waveform to a real WAV file on disk.

Kept as its own small module, separate from the TTS adapter and the Qt
worker, so it's testable without either a model or a running Qt event loop.
"""

from pathlib import Path

from scipy.io import wavfile


def write_wav(path: Path, samples: tuple[float, ...], sample_rate: int) -> None:
    """Write `samples` (floats in [-1, 1], as returned by `TtsSpeaker.synthesize`)
    to `path` as a real, playable WAV file."""
    wavfile.write(path, sample_rate, _to_float32_array(samples))


def _to_float32_array(samples: tuple[float, ...]):
    import numpy as np

    return np.asarray(samples, dtype=np.float32)
