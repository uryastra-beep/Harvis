from __future__ import annotations

import pytest

from harvis.actions.system import SystemActionError
from harvis.assistant import HarvisAssistant, HarvisGeminiLiveVoice
from harvis.config import HarvisSettings


def test_invalid_assistant_mode_falls_back_to_speaking() -> None:
    settings = HarvisSettings(assistant_mode="Unknown").normalized()

    assert settings.assistant_mode == "Speaking"


def test_silent_mode_configures_gemini_without_voice_input() -> None:
    voice = HarvisGeminiLiveVoice(
        user_name="User",
        language_tag="es-419",
        silent_mode=True,
        execute_tool=lambda name, arguments: {},
    )

    assert voice.silent_mode is True
    assert "Silent mode is active" in voice._system_instruction()


def test_silent_text_command_is_queued_without_wake_word(monkeypatch) -> None:
    assistant = HarvisAssistant(HarvisSettings(assistant_mode="Silent"))
    queued: list[str] = []

    monkeypatch.setattr(
        assistant._voice,
        "send_text",
        lambda text: queued.append(text) or True,
    )

    assistant.send_text_command("open Chrome")

    assert queued == ["open Chrome"]


def test_text_command_is_rejected_in_speaking_mode() -> None:
    assistant = HarvisAssistant(HarvisSettings(assistant_mode="Speaking"))

    with pytest.raises(SystemActionError, match="only in Silent mode"):
        assistant.send_text_command("open Chrome")


def test_basic_text_command_falls_back_locally_when_gemini_is_unavailable(
    monkeypatch,
) -> None:
    responses: list[str] = []
    assistant = HarvisAssistant(
        HarvisSettings(assistant_mode="Silent"),
        on_response=responses.append,
    )
    dispatched = []
    monkeypatch.setattr(assistant, "ensure_active_session", lambda: None)
    monkeypatch.setattr(assistant._voice, "send_text", lambda text: False)
    monkeypatch.setattr(assistant._router, "dispatch", dispatched.append)

    assistant.send_text_command("set volume to 35")

    assert dispatched[0].parameters == {"percent": 35}
    assert "Offline command" in responses[-1]


def test_disabling_idle_local_wake_starts_gemini(monkeypatch) -> None:
    assistant = HarvisAssistant(
        HarvisSettings(
            assistant_mode="Speaking",
            local_wake_word_enabled=True,
        )
    )
    starts: list[bool] = []
    monkeypatch.setattr(assistant._voice, "start", lambda: starts.append(True))

    assistant.apply_settings(
        HarvisSettings(
            assistant_mode="Speaking",
            local_wake_word_enabled=False,
        )
    )

    assert starts == [True]


def test_local_wake_runtime_error_falls_back_to_gemini(monkeypatch) -> None:
    assistant = HarvisAssistant(
        HarvisSettings(
            assistant_mode="Speaking",
            local_wake_word_enabled=True,
        )
    )
    starts: list[bool] = []
    monkeypatch.setattr(assistant._voice, "start", lambda: starts.append(True))

    assistant._handle_local_wake_error(RuntimeError("recognizer stopped"))

    assert starts == [True]
