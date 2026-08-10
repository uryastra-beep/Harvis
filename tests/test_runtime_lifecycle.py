from __future__ import annotations

from harvis.voice.gemini_live import (
    INPUT_BLOCK_FRAMES,
    INPUT_QUEUE_LIMIT,
    GeminiLiveVoice,
)


class _FakeAudioStream:
    def __init__(self) -> None:
        self.abort_calls = 0

    def abort(self) -> None:
        self.abort_calls += 1


class _StillRunningThread:
    def __init__(self) -> None:
        self.join_timeout: float | None = None

    def is_alive(self) -> bool:
        return True

    def join(self, timeout: float | None = None) -> None:
        self.join_timeout = timeout


def _voice() -> GeminiLiveVoice:
    return GeminiLiveVoice(execute_tool=lambda name, arguments: {})


def test_microphone_buffer_is_tuned_for_low_latency() -> None:
    assert INPUT_BLOCK_FRAMES <= 800
    assert INPUT_QUEUE_LIMIT <= 8


def test_audio_streams_are_aborted_during_shutdown() -> None:
    voice = _voice()
    input_stream = _FakeAudioStream()
    output_stream = _FakeAudioStream()
    voice._input_stream = input_stream
    voice._output_stream = output_stream

    voice._abort_audio_streams()

    assert input_stream.abort_calls == 1
    assert output_stream.abort_calls == 1


def test_stop_keeps_reference_to_a_thread_that_has_not_exited() -> None:
    voice = _voice()
    thread = _StillRunningThread()
    voice._thread = thread

    voice.stop()

    assert voice._thread is thread
    assert thread.join_timeout == 3.0
