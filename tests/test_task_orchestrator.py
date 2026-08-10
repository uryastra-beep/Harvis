from __future__ import annotations

import pytest

from harvis.assistant import HarvisGeminiLiveVoice
from harvis.core.task_orchestrator import (
    MAX_TOTAL_WAIT_SECONDS,
    TaskOrchestrator,
    TaskPlanError,
)


def test_plan_executes_actions_in_order_and_maps_arguments() -> None:
    calls: list[tuple[str, dict]] = []

    def executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {"status": "completed"}

    orchestrator = TaskOrchestrator(executor=executor)
    result = orchestrator.execute(
        [
            {"action": "open_application", "app_name": "Notepad"},
            {"action": "type_text", "text": "hello"},
            {"action": "press_key", "key": "enter", "count": 2},
        ]
    )

    assert result["status"] == "completed"
    assert result["steps_completed"] == 3
    assert calls == [
        ("open_application", {"app_name": "Notepad"}),
        ("type_text", {"text": "hello"}),
        ("press_key", {"key": "enter", "count": 2}),
    ]


def test_plan_pauses_when_visual_confirmation_is_required() -> None:
    calls: list[str] = []

    def executor(name: str, arguments: dict) -> dict:
        calls.append(name)
        if name == "vision_click":
            return {"status": "confirmation_required"}
        return {"status": "completed"}

    orchestrator = TaskOrchestrator(executor=executor)
    result = orchestrator.execute(
        [
            {"action": "open_application", "app_name": "Settings"},
            {"action": "vision_click", "target": "Delete account"},
            {"action": "type_text", "text": "must not run"},
        ]
    )

    assert result["status"] == "paused"
    assert result["reason"] == "confirmation_required"
    assert result["pending_step"] == 2
    assert calls == ["open_application", "vision_click"]


def test_plan_stops_after_uncertain_visual_result() -> None:
    calls: list[str] = []

    def executor(name: str, arguments: dict) -> dict:
        calls.append(name)
        if name == "vision_click":
            return {"status": "not_found"}
        return {"status": "completed"}

    orchestrator = TaskOrchestrator(executor=executor)
    result = orchestrator.execute(
        [
            {"action": "vision_click", "target": "Missing button"},
            {"action": "type_text", "text": "must not run"},
        ]
    )

    assert result["status"] == "stopped"
    assert result["reason"] == "not_found"
    assert calls == ["vision_click"]


def test_plan_returns_partial_results_when_an_action_raises() -> None:
    def executor(name: str, arguments: dict) -> dict:
        if name == "browser_control":
            raise RuntimeError("browser unavailable")
        return {"status": "completed"}

    orchestrator = TaskOrchestrator(executor=executor)
    result = orchestrator.execute(
        [
            {"action": "open_application", "app_name": "Chrome"},
            {"action": "browser_control", "browser_action": "new_tab"},
            {"action": "type_text", "text": "must not run"},
        ]
    )

    assert result["status"] == "failed"
    assert result["steps_completed"] == 1
    assert result["failed_step"] == 2
    assert result["failed_action"] == "browser_control"
    assert result["error"] == "browser unavailable"


def test_invalid_plan_is_rejected_before_any_action_runs() -> None:
    calls: list[str] = []

    def executor(name: str, arguments: dict) -> dict:
        calls.append(name)
        return {"status": "completed"}

    orchestrator = TaskOrchestrator(executor=executor)

    with pytest.raises(TaskPlanError):
        orchestrator.execute(
            [
                {"action": "open_application", "app_name": "Notepad"},
                {"action": "shutdown_harvis"},
            ]
        )

    assert calls == []


def test_plan_rejects_excessive_total_wait_time() -> None:
    orchestrator = TaskOrchestrator(
        executor=lambda name, arguments: {"status": "completed"}
    )
    waits = [
        {"action": "wait", "seconds": 5.0}
        for _ in range(int(MAX_TOTAL_WAIT_SECONDS // 5.0) + 1)
    ]

    with pytest.raises(TaskPlanError):
        orchestrator.execute(waits)


def test_gemini_declarations_include_action_plan_tool() -> None:
    declarations = HarvisGeminiLiveVoice._tool_declarations()
    names = {
        item["name"]
        for item in declarations[0]["function_declarations"]
    }

    assert "execute_action_plan" in names
