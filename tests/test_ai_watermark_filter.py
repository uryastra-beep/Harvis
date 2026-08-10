from __future__ import annotations

import pytest

from harvis import assistant as assistant_module
from harvis.actions import keyboard_control
from harvis.ai_watermark import should_watermark_ai_authored_text
from harvis.assistant import HarvisAssistant
from harvis.config import HarvisSettings


@pytest.mark.parametrize(
    "request",
    [
        "Escribe hola mundo",
        "Redáctame un mensaje para mañana",
        "Haz un texto corto sobre Linux",
        "Crea un correo para el profesor",
        "Compón un poema de cuatro líneas",
        "Resúmeme esto en un párrafo",
        "Write a paragraph about Python",
        "Draft an email for my teacher",
        "Compose a short message",
    ],
)
def test_authored_writing_requests_enable_watermark(request: str) -> None:
    assert should_watermark_ai_authored_text(request) is True


@pytest.mark.parametrize(
    "request",
    [
        "Busca gatos en Google",
        "Escribe gatos en la barra de búsqueda",
        "Busca información y escribe un texto sobre Linux",
        "Dame la URL de GitHub",
        "Abre https://github.com",
        "Ve a google.com",
        "Crea una carpeta llamada Test",
        "Open the browser and search for Harvis",
    ],
)
def test_search_navigation_and_url_requests_disable_watermark(request: str) -> None:
    assert should_watermark_ai_authored_text(request) is False


def test_assistant_applies_watermark_only_for_writing_context(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []
    assistant = HarvisAssistant(HarvisSettings(ai_watermark_enabled=True))

    monkeypatch.setattr(
        assistant_module,
        "type_text",
        lambda text, *, apply_watermark=True: calls.append(
            (text, apply_watermark)
        )
        or {"status": "completed"},
    )

    assistant._set_watermark_context("Redacta un mensaje para GitHub")
    assistant._execute_tool("type_text", {"text": "Hello from Harvis"})

    assistant._set_watermark_context("Busca Harvis en Google")
    assistant._execute_tool("type_text", {"text": "Harvis"})

    assert calls == [
        ("Hello from Harvis", True),
        ("Harvis", False),
    ]


def test_assistant_watermark_setting_still_overrides_filter(monkeypatch) -> None:
    calls: list[bool] = []
    assistant = HarvisAssistant(HarvisSettings(ai_watermark_enabled=False))

    monkeypatch.setattr(
        assistant_module,
        "type_text",
        lambda text, *, apply_watermark=True: calls.append(apply_watermark)
        or {"status": "completed"},
    )

    assistant._set_watermark_context("Escribe un mensaje de prueba")
    assistant._execute_tool("type_text", {"text": "Test"})

    assert calls == [False]


def test_multiline_typing_can_explicitly_skip_watermark(monkeypatch) -> None:
    calls: list[tuple[str, bool]] = []
    keyboard_control.set_ai_watermark_enabled(True)

    monkeypatch.setattr(
        keyboard_control,
        "type_text",
        lambda text, *, apply_watermark=True: calls.append(
            (text, apply_watermark)
        )
        or {"status": "completed"},
    )
    monkeypatch.setattr(
        keyboard_control,
        "press_key",
        lambda key, count=1: {"status": "completed"},
    )

    keyboard_control.type_lines(
        ["search query", "second line"],
        apply_watermark=False,
    )

    keyboard_control.set_ai_watermark_enabled(False)
    assert calls == [
        ("search query", False),
        ("second line", False),
    ]
