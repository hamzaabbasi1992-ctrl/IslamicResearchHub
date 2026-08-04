"""Tests for TtsWorker's chunk-by-chunk synthesis, off the GUI thread."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from islamic_research_hub.application.page_narration import (  # noqa: E402
    ChunkedNarrationPlan,
    PageNarrationService,
)
from islamic_research_hub.interfaces.desktop_app.tts_worker import TtsWorker  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class _FakeSpeaker:
    """Records each synthesize() call; can fail on a specific chunk index
    or trigger cancellation from inside a call, to test both paths
    deterministically instead of relying on real thread timing."""

    def __init__(
        self,
        chunk_count: int = 3,
        fail_at: int | None = None,
        cancel_worker_at: int | None = None,
        worker: TtsWorker | None = None,
    ) -> None:
        self.chunk_count = chunk_count
        self.fail_at = fail_at
        self.cancel_worker_at = cancel_worker_at
        self.worker = worker
        self.calls: list[str] = []

    def synthesize(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
        index = len(self.calls)
        self.calls.append(text)
        if self.cancel_worker_at is not None and index == self.cancel_worker_at:
            assert self.worker is not None
            self.worker.request_cancellation()
        if self.fail_at is not None and index == self.fail_at:
            raise RuntimeError("synthesis failed")
        return (0.0, 0.1), 8000


class _FakePlanService:
    """A PageNarrationService stand-in whose prepare step returns a fixed
    plan, so tests control chunk count directly rather than depending on
    chunk_narration_text's real splitting behavior."""

    def __init__(self, speaker: _FakeSpeaker, chunk_count: int) -> None:
        self._speaker = speaker
        self._chunk_count = chunk_count

    def prepare_chunked_narration(self, text: str, language: str | None) -> ChunkedNarrationPlan:
        chunk_texts = tuple(f"chunk {i}" for i in range(self._chunk_count))
        return ChunkedNarrationPlan(language="English", chunk_texts=chunk_texts)

    def synthesize_chunk(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
        return self._speaker.synthesize(text, language)


def test_multi_chunk_text_emits_chunk_ready_in_order_then_finishes(qtbot) -> None:
    speaker = _FakeSpeaker()
    service = _FakePlanService(speaker, chunk_count=3)
    worker = TtsWorker(lambda: service, "text", "English", "key")
    received: list[tuple[str, int, bool, object]] = []
    worker.chunk_ready.connect(lambda *args: received.append(args))
    finished_args = []
    worker.narration_finished.connect(lambda *args: finished_args.append(args))

    with qtbot.waitSignal(worker.narration_finished, timeout=5000):
        worker.start()

    assert [chunk_index for _, chunk_index, _, _ in received] == [0, 1, 2]
    assert [is_last for _, _, is_last, _ in received] == [False, False, True]
    assert all(request_key == "key" for _, _, _, request_key in received)
    parent_dirs = {Path(wav_path).parent for wav_path, _, _, _ in received}
    assert len(parent_dirs) == 1
    for wav_path, _, _, _ in received:
        assert Path(wav_path).is_file()
    assert finished_args == [("key", 3)]


def test_speaker_failing_on_first_chunk_emits_only_narration_failed(qtbot) -> None:
    speaker = _FakeSpeaker(fail_at=0)
    service = _FakePlanService(speaker, chunk_count=3)
    worker = TtsWorker(lambda: service, "text", "English", "key")
    chunk_ready_calls = []
    failed_calls = []
    worker.chunk_ready.connect(lambda *args: chunk_ready_calls.append(args))
    worker.narration_failed.connect(lambda key: failed_calls.append(key))

    with qtbot.waitSignal(worker.narration_finished, timeout=5000):
        worker.start()

    assert chunk_ready_calls == []
    assert failed_calls == ["key"]


def test_speaker_failing_on_a_later_chunk_keeps_earlier_chunks(qtbot) -> None:
    """Real CPU already spent on earlier chunks isn't thrown away - the
    page plays partially rather than failing outright."""
    speaker = _FakeSpeaker(chunk_count=5, fail_at=2)
    service = _FakePlanService(speaker, chunk_count=5)
    worker = TtsWorker(lambda: service, "text", "English", "key")
    chunk_ready_calls = []
    failed_calls = []
    finished_calls = []
    worker.chunk_ready.connect(lambda *args: chunk_ready_calls.append(args))
    worker.narration_failed.connect(lambda key: failed_calls.append(key))
    worker.narration_finished.connect(lambda *args: finished_calls.append(args))

    with qtbot.waitSignal(worker.narration_finished, timeout=5000):
        worker.start()

    assert len(chunk_ready_calls) == 2
    assert failed_calls == []
    assert finished_calls == [("key", 2)]


def test_cancellation_requested_mid_run_stops_further_synthesis(qtbot) -> None:
    """A fake speaker cancels the worker from inside its own synthesize()
    call - deterministic, no reliance on real thread-timing races."""
    worker = TtsWorker(lambda: None, "text", "English", "key")  # placeholder, replaced below
    speaker = _FakeSpeaker(chunk_count=5, cancel_worker_at=1, worker=worker)
    service = _FakePlanService(speaker, chunk_count=5)
    worker._get_service = lambda: service
    chunk_ready_calls = []
    finished_calls = []
    worker.chunk_ready.connect(lambda *args: chunk_ready_calls.append(args))
    worker.narration_finished.connect(lambda *args: finished_calls.append(args))

    with qtbot.waitSignal(worker.narration_finished, timeout=5000):
        worker.start()

    # Chunk 0 (synthesized before cancellation was requested) is kept;
    # cancellation is checked before chunk 1's synthesis even completes -
    # but the fake speaker requests it *during* chunk 1's own call, so
    # chunk 1 still finishes and is emitted; chunk 2 never starts.
    assert [chunk_index for _, chunk_index, _, _ in chunk_ready_calls] == [0, 1]
    assert finished_calls == [("key", 2)]


def test_no_service_available_emits_failed_and_finished_with_zero_chunks(qtbot) -> None:
    worker = TtsWorker(lambda: None, "text", "English", "key")
    chunk_ready_calls = []
    failed_calls = []
    finished_calls = []
    worker.chunk_ready.connect(lambda *args: chunk_ready_calls.append(args))
    worker.narration_failed.connect(lambda key: failed_calls.append(key))
    worker.narration_finished.connect(lambda *args: finished_calls.append(args))

    with qtbot.waitSignal(worker.narration_finished, timeout=5000):
        worker.start()

    assert chunk_ready_calls == []
    assert failed_calls == ["key"]
    assert finished_calls == [("key", 0)]


def test_real_page_narration_service_end_to_end(qtbot) -> None:
    """One real (non-fake) PageNarrationService, to confirm the worker's
    integration with the real prepare_chunked_narration/synthesize_chunk
    contract, not just the test doubles above."""

    class _RealFakeSpeaker:
        def synthesize(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
            return (0.0, 0.1, 0.0), 8000

    service = PageNarrationService(_RealFakeSpeaker())
    worker = TtsWorker(lambda: service, "Hello world. This is a second sentence.", "English", "key")
    chunk_ready_calls = []
    worker.chunk_ready.connect(lambda *args: chunk_ready_calls.append(args))

    with qtbot.waitSignal(worker.narration_finished, timeout=5000):
        worker.start()

    assert len(chunk_ready_calls) >= 1
    assert chunk_ready_calls[-1][2] is True  # last chunk marked is_last
