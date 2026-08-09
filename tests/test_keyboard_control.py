from __future__ import annotations

import pytest

from harvis.actions import keyboard_control
from harvis.actions.keyboard_control import _normalize_text_payload, _validate_text_payload
from harvis.actions.system import SystemActionError


def test_typing_guard_accepts_normal_spanish_punctuation() -> None:
    _validate_text_payload("Hola, ¿cómo estás?")
    _validate_text_payload("Sí!!! Todo bien...")
    _validate_text_payload("Gemini.mm")


def test_typing_guard_rejects_corrupted_punctuation_runs() -> None:
    with pytest.raises(SystemActionError, match="abnormal punctuation run"):
        _validate_text_payload("hola,?????????????Hola, ¿cómo ??????")


def test_typing_guard_rejects_invalid_unicode_replacement_character() -> None:
    with pytest.raises(SystemActionError, match="invalid characters"):
        _validate_text_payload("Hola \ufffd")


def test_exact_escaped_newline_payload_becomes_enter() -> None:
    assert _normalize_text_payload(r"\n") == "\n"
    assert _normalize_text_payload(r"\r") == "\n"
    assert _normalize_text_payload(r"\r\n") == "\n"


def test_literal_newline_escape_inside_regular_text_is_preserved() -> None:
    code = 'print("first\\nsecond")'
    assert _normalize_text_payload(code) == code


def test_type_text_sends_normalized_enter_on_windows(monkeypatch) -> None:
    sent: list[str] = []

    monkeypatch.setattr(keyboard_control.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        keyboard_control,
        "_windows_type_unicode",
        lambda text: sent.append(text),
    )

    result = keyboard_control.type_text(r"\n")

    assert sent == ["\n"]
    assert result == {"status": "completed", "characters": 1}
