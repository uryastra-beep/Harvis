from __future__ import annotations

import pytest

from harvis.actions.system import SystemActionError
from harvis.assistant import HarvisAssistant, HarvisGeminiLiveVoice
from harvis.config import HarvisSettings


def test_gemini_registers_shutdown_harvis_tool() -> None:
    declarations = HarvisGeminiLiveVoice._tool_declarations()
    functions = {
        function["name"]: function
        for function in declarations[0]["function_declarations"]
    }

    assert "shutdown_harvis" in functions
    assert functions["shutdown_harvis"]["parameters"] == {
        "type": "object",
        "properties": {},
    }


def test_shutdown_tool_requests_clean_app_exit() -> None:
    requests: list[str] = []
    statuses: list[str] = []
    assistant = HarvisAssistant(
        HarvisSettings(),
        on_shutdown_requested=lambda: requests.append("shutdown"),
        on_status=statuses.append,
    )

    result = assistant._execute_tool("shutdown_harvis", {})

    assert requests == ["shutdown"]
    assert statuses == ["Harvis shutdown requested"]
    assert result == {
        "status": "completed",
        "application": "Harvis",
    }


def test_shutdown_tool_fails_safely_without_app_callback() -> None:
    assistant = HarvisAssistant(HarvisSettings())

    with pytest.raises(SystemActionError, match="self-shutdown is not available"):
        assistant._execute_tool("shutdown_harvis", {})
