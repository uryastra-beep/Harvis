from __future__ import annotations

from harvis.assistant import HarvisAssistant
from harvis.config import HarvisSettings


def _silent_assistant(monkeypatch) -> HarvisAssistant:
    assistant = HarvisAssistant(HarvisSettings(assistant_mode="Silent"))
    monkeypatch.setattr(assistant._voice, "send_text", lambda text: True)
    return assistant


def test_model_cannot_self_confirm_sensitive_visual_click(monkeypatch) -> None:
    assistant = _silent_assistant(monkeypatch)
    calls: list[dict] = []

    def fake_vision_click(target: str, *, button: str, confirmed: bool) -> dict:
        calls.append(
            {
                "target": target,
                "button": button,
                "confirmed": confirmed,
            }
        )
        if confirmed:
            return {"status": "clicked"}
        return {"status": "confirmation_required"}

    monkeypatch.setattr("harvis.assistant.vision_click", fake_vision_click)

    first = assistant._execute_tool(
        "vision_click",
        {"target": "Delete account", "confirmed": True},
    )
    premature_retry = assistant._execute_tool(
        "vision_click",
        {"target": "Delete account", "confirmed": True},
    )

    assert first["status"] == "confirmation_required"
    assert premature_retry["status"] == "confirmation_required"
    assert calls == [
        {
            "target": "Delete account",
            "button": "left",
            "confirmed": False,
        }
    ]


def test_explicit_user_confirmation_allows_one_matching_retry(monkeypatch) -> None:
    assistant = _silent_assistant(monkeypatch)
    confirmed_values: list[bool] = []

    def fake_vision_click(target: str, *, button: str, confirmed: bool) -> dict:
        confirmed_values.append(confirmed)
        return {
            "status": "clicked" if confirmed else "confirmation_required"
        }

    monkeypatch.setattr("harvis.assistant.vision_click", fake_vision_click)

    assistant._execute_tool("vision_click", {"target": "Delete account"})
    assistant.send_text_command("yes")
    result = assistant._execute_tool("vision_click", {"target": "Delete account"})

    assert result["status"] == "clicked"
    assert confirmed_values == [False, True]


def test_user_rejection_cancels_pending_visual_confirmation(monkeypatch) -> None:
    assistant = _silent_assistant(monkeypatch)
    confirmed_values: list[bool] = []

    def fake_vision_click(target: str, *, button: str, confirmed: bool) -> dict:
        confirmed_values.append(confirmed)
        return {"status": "confirmation_required"}

    monkeypatch.setattr("harvis.assistant.vision_click", fake_vision_click)

    assistant._execute_tool("vision_click", {"target": "Delete account"})
    assistant.send_text_command("no, do not do it")
    assistant._execute_tool("vision_click", {"target": "Delete account"})

    assert confirmed_values == [False, False]


def test_partial_voice_yes_followed_by_no_never_confirms(monkeypatch) -> None:
    assistant = HarvisAssistant(HarvisSettings(assistant_mode="Speaking"))
    confirmed_values: list[bool] = []

    def fake_vision_click(target: str, *, button: str, confirmed: bool) -> dict:
        confirmed_values.append(confirmed)
        return {"status": "confirmation_required"}

    monkeypatch.setattr("harvis.assistant.vision_click", fake_vision_click)

    assistant._execute_tool("vision_click", {"target": "Delete account"})
    assistant._handle_input_transcript("sí")
    assistant._handle_input_transcript("pero no")
    assistant._execute_tool("vision_click", {"target": "Delete account"})

    assert confirmed_values == [False, False]


def test_multi_fragment_explicit_voice_confirmation_is_accepted(monkeypatch) -> None:
    assistant = HarvisAssistant(HarvisSettings(assistant_mode="Speaking"))
    confirmed_values: list[bool] = []

    def fake_vision_click(target: str, *, button: str, confirmed: bool) -> dict:
        confirmed_values.append(confirmed)
        return {
            "status": "clicked" if confirmed else "confirmation_required"
        }

    monkeypatch.setattr("harvis.assistant.vision_click", fake_vision_click)

    assistant._execute_tool("vision_click", {"target": "Delete account"})
    assistant._handle_input_transcript("sí")
    assistant._handle_input_transcript("hazlo")
    result = assistant._execute_tool("vision_click", {"target": "Delete account"})

    assert result["status"] == "clicked"
    assert confirmed_values == [False, True]
