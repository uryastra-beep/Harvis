from __future__ import annotations

import asyncio

import pytest

from harvis.assistant import HarvisAssistant
from harvis.config import HarvisSettings
from harvis.actions.system import SystemActionError
from harvis.voice.gemini_live import GeminiLiveVoice


class _ImmediateLoop:
    def is_running(self) -> bool:
        return True

    def call_soon_threadsafe(self, callback, *args) -> None:
        callback(*args)


def _voice() -> GeminiLiveVoice:
    return GeminiLiveVoice(execute_tool=lambda name, arguments: None)


def test_microphone_mute_toggle_changes_state() -> None:
    voice = _voice()

    assert voice.microphone_muted is False
    assert voice.toggle_microphone_muted() is True
    assert voice.microphone_muted is True
    assert voice.toggle_microphone_muted() is False
    assert voice.microphone_muted is False


def test_muting_discards_queued_audio_and_blocks_new_chunks() -> None:
    voice = _voice()
    voice._loop = _ImmediateLoop()
    voice._input_queue = asyncio.Queue()

    voice._audio_input_callback(b"first", 0, None, None)
    assert voice._input_queue.qsize() == 1

    voice.set_microphone_muted(True)
    assert voice._input_queue.qsize() == 0

    voice._audio_input_callback(b"second", 0, None, None)
    assert voice._input_queue.qsize() == 0


def test_unmuting_allows_microphone_chunks_again() -> None:
    voice = _voice()
    voice._loop = _ImmediateLoop()
    voice._input_queue = asyncio.Queue()
    voice.set_microphone_muted(True)
    voice.set_microphone_muted(False)

    voice._audio_input_callback(b"audio", 0, None, None)

    assert voice._input_queue.qsize() == 1


def test_assistant_toggle_reports_state_in_speaking_mode() -> None:
    statuses: list[str] = []
    assistant = HarvisAssistant(
        HarvisSettings(assistant_mode="Speaking"),
        on_status=statuses.append,
    )

    assert assistant.toggle_microphone_muted() is True
    assert assistant.microphone_muted is True
    assert statuses[-1] == "Microphone muted"

    assert assistant.toggle_microphone_muted() is False
    assert assistant.microphone_muted is False
    assert statuses[-1] == "Microphone active"


def test_assistant_rejects_microphone_toggle_in_silent_mode() -> None:
    assistant = HarvisAssistant(HarvisSettings(assistant_mode="Silent"))

    with pytest.raises(SystemActionError):
        assistant.toggle_microphone_muted()
