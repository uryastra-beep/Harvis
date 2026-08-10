from __future__ import annotations

import pytest

from harvis.actions import keyboard_control
from harvis.actions.keyboard_control import _normalize_text_payload, _validate_text_payload
from harvis.actions.system import SystemActionError
from harvis.assistant import HarvisGeminiLiveVoice


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


def test_literal_newline_escape_is_preserved_as_text() -> None:
    assert _normalize_text_payload(r"\n") == r"\n"
    assert _normalize_text_payload(r"\r") == r"\r"
    assert _normalize_text_payload(r"\r\n") == r"\r\n"


def test_real_line_endings_are_normalized() -> None:
    assert _normalize_text_payload("first\r\nsecond\rthird") == "first\nsecond\nthird"


def test_literal_newline_escape_inside_regular_text_is_preserved() -> None:
    code = 'print("first\\nsecond")'
    assert _normalize_text_payload(code) == code


def test_type_text_keeps_escaped_newline_literal_on_windows(monkeypatch) -> None:
    sent: list[str] = []
    keyboard_control.set_ai_watermark_enabled(False)

    monkeypatch.setattr(keyboard_control.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        keyboard_control,
        "_windows_type_unicode",
        lambda text: sent.append(text),
    )

    result = keyboard_control.type_text(r"\n")

    assert sent == [r"\n"]
    assert result == {"status": "completed", "characters": 2}


def test_ai_watermark_prefixes_typed_text_once(monkeypatch) -> None:
    sent: list[str] = []
    keyboard_control.set_ai_watermark_enabled(True)

    monkeypatch.setattr(keyboard_control.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        keyboard_control,
        "_windows_type_unicode",
        lambda text: sent.append(text),
    )

    try:
        keyboard_control.type_text("Hello from Harvis")
        keyboard_control.type_text("#G6m2i9 Already marked")
    finally:
        keyboard_control.set_ai_watermark_enabled(False)

    assert sent == [
        "#G6m2i9 Hello from Harvis",
        "#G6m2i9 Already marked",
    ]


def test_press_key_sends_one_enter_on_windows(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(keyboard_control.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        keyboard_control,
        "_windows_press_key",
        lambda key, count: calls.append((key, count)),
    )

    result = keyboard_control.press_key("enter")

    assert calls == [("enter", 1)]
    assert result == {"status": "completed", "key": "enter", "count": 1}


def test_press_key_clamps_count(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(keyboard_control.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        keyboard_control,
        "_windows_press_key",
        lambda key, count: calls.append((key, count)),
    )

    keyboard_control.press_key("enter", 99)

    assert calls == [("enter", 5)]


def test_press_key_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unsupported keyboard key"):
        keyboard_control.press_key("space")


def test_type_lines_keeps_repeated_text_sequence_exact(monkeypatch) -> None:
    calls: list[tuple[str, str | int]] = []
    keyboard_control.set_ai_watermark_enabled(False)

    monkeypatch.setattr(
        keyboard_control,
        "type_text",
        lambda text, apply_watermark=True: calls.append(("text", text))
        or {"status": "completed"},
    )
    monkeypatch.setattr(
        keyboard_control,
        "press_key",
        lambda key, count=1: calls.append(("key", key)) or {"status": "completed"},
    )

    result = keyboard_control.type_lines(["hola", "hola", "hola", "hola"])

    assert calls == [
        ("text", "hola"),
        ("key", "enter"),
        ("text", "hola"),
        ("key", "enter"),
        ("text", "hola"),
        ("key", "enter"),
        ("text", "hola"),
    ]
    assert result == {
        "status": "completed",
        "lines": 4,
        "characters": 16,
        "enters": 3,
    }


def test_type_lines_applies_watermark_only_to_first_nonempty_line(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []
    keyboard_control.set_ai_watermark_enabled(True)

    monkeypatch.setattr(
        keyboard_control,
        "type_text",
        lambda text, apply_watermark=True: calls.append((text, apply_watermark))
        or {"status": "completed"},
    )
    monkeypatch.setattr(
        keyboard_control,
        "press_key",
        lambda key, count=1: {"status": "completed"},
    )

    try:
        keyboard_control.type_lines(["", "first", "second"])
    finally:
        keyboard_control.set_ai_watermark_enabled(False)

    assert calls == [
        ("first", True),
        ("second", False),
    ]


def test_type_lines_rejects_embedded_newline() -> None:
    with pytest.raises(ValueError, match="exactly one line"):
        keyboard_control.type_lines(["hola\nhola"])


def test_gemini_registers_keyboard_tools() -> None:
    declarations = HarvisGeminiLiveVoice._tool_declarations()
    functions = {
        function["name"]: function
        for function in declarations[0]["function_declarations"]
    }

    assert "press_key" in functions
    assert "type_lines" in functions
    assert functions["press_key"]["parameters"]["properties"]["key"]["enum"] == ["enter"]
