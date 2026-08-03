"""Tests for the PCM16-bytes-to-samples helper - real numpy round-trip, no Qt, no model."""

import struct

import pytest

from islamic_research_hub.infrastructure.audio.pcm_conversion import pcm16_bytes_to_samples


def test_pcm16_bytes_to_samples_converts_known_values() -> None:
    """A real signed-16-bit PCM buffer (silence, half-scale, negative
    half-scale, near-full-scale) converts to the expected normalized floats."""
    data = struct.pack("<4h", 0, 16384, -16384, 32767)

    samples = pcm16_bytes_to_samples(data)

    assert samples[0] == 0.0
    assert samples[1] == pytest.approx(0.5)
    assert samples[2] == pytest.approx(-0.5)
    assert samples[3] == pytest.approx(1.0, abs=0.001)


def test_pcm16_bytes_to_samples_handles_empty_input() -> None:
    assert pcm16_bytes_to_samples(b"") == ()


def test_pcm16_bytes_to_samples_returns_a_plain_tuple() -> None:
    data = struct.pack("<2h", 0, 100)

    samples = pcm16_bytes_to_samples(data)

    assert isinstance(samples, tuple)
    assert len(samples) == 2
