"""Convert raw microphone PCM audio into normalized float samples.

Kept as its own small module, separate from the STT adapter and the Qt
capture plumbing, so it's testable without either a model or a running Qt
event loop - mirrors `wav_writer.py`'s reasoning (bytes<->samples
conversion kept out of both the model adapter and Qt-specific code). This
is the mirror-image direction of `wav_writer.py`: bytes -> samples here,
samples -> bytes there.
"""

import numpy as np


def pcm16_bytes_to_samples(data: bytes) -> tuple[float, ...]:
    """Convert raw signed 16-bit little-endian PCM bytes (`QAudioSource`'s
    real capture format) to normalized float samples in [-1, 1] - the same
    representation `TtsSpeaker.synthesize()` produces, so both audio paths
    speak the same plain-tuple-of-floats convention."""
    integers = np.frombuffer(data, dtype="<i2")
    return tuple((integers.astype(np.float32) / 32768.0).tolist())
