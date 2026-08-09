import pytest

from harvis.actions import mouse_control
from harvis.actions.system import SystemActionError
from harvis.assistant import HarvisGeminiLiveVoice


def test_scroll_view_uses_windows_wheel(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(mouse_control.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        mouse_control,
        "_scroll_windows",
        lambda direction, steps: calls.append((direction, steps)),
    )

    result = mouse_control.scroll_view("down", 5)

    assert calls == [("down", 5)]
    assert result == {
        "status": "completed",
        "direction": "down",
        "steps": 5,
    }


def test_scroll_view_clamps_step_count(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    monkeypatch.setattr(mouse_control.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        mouse_control,
        "_scroll_windows",
        lambda direction, steps: calls.append((direction, steps)),
    )

    mouse_control.scroll_view("up", 999)

    assert calls == [("up", mouse_control.MAX_SCROLL_STEPS)]


def test_scroll_view_rejects_invalid_direction() -> None:
    with pytest.raises(ValueError):
        mouse_control.scroll_view("sideways", 3)


def test_scroll_view_rejects_unsupported_platform(monkeypatch) -> None:
    monkeypatch.setattr(mouse_control.platform, "system", lambda: "Darwin")

    with pytest.raises(SystemActionError):
        mouse_control.scroll_view("down", 3)


def test_gemini_registers_scroll_tool() -> None:
    declarations = HarvisGeminiLiveVoice._tool_declarations()
    function_names = {
        function["name"]
        for function in declarations[0]["function_declarations"]
    }

    assert "scroll_view" in function_names
