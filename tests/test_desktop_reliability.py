from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from harvis.actions.app_discovery import _score_name
from harvis.actions.screen_control import (
    ScreenCapture,
    _normalized_to_screen,
    _parse_vision_response,
)
from harvis.assistant import HarvisGeminiLiveVoice


@dataclass
class _FakeFunctionCall:
    id: str
    name: str
    args: dict[str, object]


@dataclass
class _FakeToolCall:
    function_calls: list[_FakeFunctionCall]


class _FakeFunctionResponse:
    def __init__(self, *, id: str, name: str, response: dict[str, object]) -> None:
        self.id = id
        self.name = name
        self.response = response


class _FakeTypes:
    FunctionResponse = _FakeFunctionResponse


class _FakeSession:
    def __init__(self) -> None:
        self.responses = []

    async def send_tool_response(self, *, function_responses) -> None:
        self.responses.extend(function_responses)


def test_dynamic_app_name_scoring_prefers_exact_matches() -> None:
    assert _score_name("WhatsApp.exe", "whatsapp") == 1000
    assert _score_name("WhatsAppLauncher.exe", "whatsapp") < 1000
    assert _score_name("unrelated.exe", "whatsapp") == 0


def test_screen_coordinates_preserve_virtual_desktop_origin() -> None:
    capture = ScreenCapture(
        image_bytes=b"image",
        origin_x=-1920,
        origin_y=0,
        width=3840,
        height=1080,
    )

    x, y = _normalized_to_screen(500, 500, capture)

    assert -2 <= x <= 1
    assert 538 <= y <= 541


def test_vision_json_parsing_clamps_coordinates() -> None:
    result = _parse_vision_response(
        '{"found":true,"x":1200,"y":-50,"confidence":1.4,'
        '"description":"Send button","sensitive":false}'
    )

    assert result.found is True
    assert result.x_1000 == 1000
    assert result.y_1000 == 0
    assert result.confidence == 1.0


def test_blocking_desktop_tool_runs_off_live_event_loop() -> None:
    def blocking_executor(name: str, arguments: dict[str, object]):
        time.sleep(0.06)
        return {"name": name, "arguments": arguments}

    voice = HarvisGeminiLiveVoice(execute_tool=blocking_executor)
    session = _FakeSession()
    tool_call = _FakeToolCall(
        function_calls=[
            _FakeFunctionCall(
                id="call-1",
                name="test_tool",
                args={"value": 1},
            )
        ]
    )

    async def scenario() -> None:
        task = asyncio.create_task(
            voice._handle_tool_calls(session, _FakeTypes, tool_call)
        )
        await asyncio.sleep(0.01)
        assert task.done() is False
        await task

    asyncio.run(scenario())
    assert len(session.responses) == 1
    assert session.responses[0].response["ok"] is True
