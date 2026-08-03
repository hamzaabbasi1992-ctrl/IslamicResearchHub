"""Tests for the WAV-writing helper - real scipy round-trip, no model, no Qt."""

from pathlib import Path

from scipy.io import wavfile

from islamic_research_hub.infrastructure.audio.wav_writer import write_wav


def test_write_wav_round_trips_samples_and_sample_rate(tmp_path: Path) -> None:
    """A real waveform written out reads back with the same rate and sample count."""
    samples = tuple(0.01 * i for i in range(-50, 50))
    path = tmp_path / "narration.wav"

    write_wav(path, samples, sample_rate=16000)

    rate, data = wavfile.read(path)
    assert rate == 16000
    assert len(data) == len(samples)


def test_write_wav_creates_a_real_playable_file(tmp_path: Path) -> None:
    """The written file is a real, non-empty file on disk."""
    path = tmp_path / "narration.wav"

    write_wav(path, (0.0, 0.5, -0.5, 0.0), sample_rate=8000)

    assert path.is_file()
    assert path.stat().st_size > 0
