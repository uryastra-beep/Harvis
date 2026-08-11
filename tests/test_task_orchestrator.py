from __future__ import annotations

import pytest

from harvis.assistant import HarvisGeminiLiveVoice
from harvis.core.task_orchestrator import (
    MAX_TOTAL_WAIT_SECONDS,
    TaskOrchestrator,
    TaskPlanError,
)


def _orchestrator(executor, *, screen_checker=None, target_waiter=None) -> TaskOrchestrator:
    return TaskOrchestrator(
        executor=executor,
        screen_stability_checker=(
            screen_checker
            or (lambda **kwargs: {"status": "completed", "stable": True})
        ),
        visual_target_waiter=(
            target_waiter
            or (
                lambda target, **kwargs: {
                    "status": "found",
                    "target": target,
                    "found": True,
                    "confidence": 1.0,
                }
            )
        ),
    )


def test_plan_executes_actions_in_order_and_maps_arguments() -> None:
    calls: list[tuple[str, dict]] = []

    def executor(name: str, arguments: dict) -> dict:
        calls.append((name, arguments))
        return {"status": "completed"}

    orchestrator = _orchestrator(executor)
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


def test_long_plan_checks_screen_stability_between_ui_steps() -> None:
    actions: list[str] = []
    stability_checks: list[float] = []

    def executor(name: str, arguments: dict) -> dict:
        actions.append(name)
        return {"status": "completed"}

    def screen_checker(**kwargs) -> dict:
        stability_checks.append(float(kwargs["timeout_seconds"]))
        return {"status": "completed", "stable": True}

    orchestrator = _orchestrator(executor, screen_checker=screen_checker)
    result = orchestrator.execute(
        [
            {"action": "open_application", "app_name": "Notepad"},
            {"action": "type_text", "text": "hello"},
            {"action": "press_key", "key": "enter"},
        ]
    )

    assert result["status"] == "completed"
    assert actions == ["open_application", "type_text", "press_key"]
    assert len(stability_checks) == 2
    assert [item["type"] for item in result["checkpoints"]] == [
        "screen_stability",
        "screen_stability",
    ]


def test_long_plan_waits_for_visual_target_before_clicking() -> None:
    actions: list[str] = []
    waited_targets: list[str] = []

    def executor(name: str, arguments: dict) -> dict:
        actions.append(name)
        if name == "vision_click":
            return {"status": "clicked"}
        return {"status": "completed"}

    def target_waiter(target: str, **kwargs) -> dict:
        waited_targets.append(target)
        return {
            "status": "found",
            "target": target,
            "found": True,
            "confidence": 0.99,
        }

    orchestrator = _orchestrator(executor, target_waiter=target_waiter)
    result = orchestrator.execute(
        [
            {"action": "open_application", "app_name": "Settings"},
            {"action": "vision_click", "target": "Bluetooth button"},
            {"action": "type_text", "text": "done"},
        ]
    )

    assert result["status"] == "completed"
    assert waited_targets == ["Bluetooth button"]
    assert actions == ["open_application", "vision_click", "type_text"]


def test_long_plan_stops_before_missing_visual_target() -> None:
    actions: list[str] = []

    def executor(name: str, arguments: dict) -> dict:
        actions.append(name)
        return {"status": "completed"}

    def target_waiter(target: str, **kwargs) -> dict:
        return {
            "status": "not_found",
            "target": target,
            "found": False,
            "confidence": 0.0,
        }

    orchestrator = _orchestrator(executor, target_waiter=target_waiter)
    result = orchestrator.execute(
        [
            {"action": "open_application", "app_name": "Settings"},
            {"action": "vision_click", "target": "Missing button"},
            {"action": "type_text", "text": "must not run"},
        ]
    )

    assert result["status"] == "stopped"
    assert result["reason"] == "not_found"
    assert result["steps_completed"] == 1
    assert result["stopped_step"] == 2
    assert result["missing_target"] == "Missing button"
    assert actions == ["open_application"]


def test_ready_target_can_guard_non_visual_step() -> None:
    actions: list[str] = []
    waited_targets: list[tuple[str, float]] = []

    def executor(name: str, arguments: dict) -> dict:
        actions.append(name)
        return {"status": "completed"}

    def target_waiter(target: str, **kwargs) -> dict:
        waited_targets.append((target, float(kwargs["timeout_seconds"])))
        return {"status": "found", "target": target, "found": True}

    orchestrator = _orchestrator(executor, target_waiter=target_waiter)
    result = orchestrator.execute(
        [
            {"action": "open_application", "app_name": "Notepad"},
            {
                "action": "type_text",
                "text": "hello",
                "ready_target": "Notepad editor area",
                "ready_timeout": 7.5,
            },
            {"action": "press_key", "key": "enter"},
        ]
    )

    assert result["status"] == "completed"
    assert waited_targets == [("Notepad editor area", 7.5)]
    assert actions == ["open_application", "type_text", "press_key"]


def test_two_step_plan_does_not_add_screen_guards() -> None:
    actions: list[str] = []
    screen_checks = 0
    target_checks = 0

    def executor(name: str, arguments: dict) -> dict:
        actions.append(name)
        return {"status": "completed"}

    def screen_checker(**kwargs) -> dict:
        nonlocal screen_checks
        screen_checks += 1
        return {"status": "completed"}

    def target_waiter(target: str, **kwargs) -> dict:
        nonlocal target_checks
        target_checks += 1
        return {"status": "found"}

    orchestrator = _orchestrator(
        executor,
        screen_checker=screen_checker,
        target_waiter=target_waiter,
    )
    result = orchestrator.execute(
        [
            {"action": "open_application", "app_name": "Notepad"},
            {"action": "type_text", "text": "hello"},
        ]
    )

    assert result["status"] == "completed"
    assert actions == ["open_application", "type_text"]
    assert screen_checks == 0
    assert target_checks == 0


def test_plan_pauses_when_visual_confirmation_is_required() -> None:
    calls: list[str] = []

    def executor(name: str, arguments: dict) -> dict:
        calls.append(name)
        if name == "vision_click":
            return {"status": "confirmation_required"}
        return {"status": "completed"}

    orchestrator = _orchestrator(executor)
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

    orchestrator = _orchestrator(executor)
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

    orchestrator = _orchestrator(executor)
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

    orchestrator = _orchestrator(executor)

    with pytest.raises(TaskPlanError):
        orchestrator.execute(
            [
                {"action": "open_application", "app_name": "Notepad"},
                {"action": "shutdown_harvis"},
            ]
        )

    assert calls == []


def test_plan_rejects_excessive_total_wait_time() -> None:
    orchestrator = _orchestrator(
        lambda name, arguments: {"status": "completed"}
    )
    waits = [
        {"action": "wait", "seconds": 5.0}
        for _ in range(int(MAX_TOTAL_WAIT_SECONDS // 5.0) + 1)
    ]

    with pytest.raises(TaskPlanError):
        orchestrator.execute(waits)


def test_gemini_declarations_include_action_plan_tool() -> None:
    declarations = HarvisGeminiLiveVoice._tool_declarations()
    tools = {
        item["name"]: item
        for item in declarations[0]["function_declarations"]
    }

    assert "execute_action_plan" in tools
    step_properties = tools["execute_action_plan"]["parameters"]["properties"][
        "steps"
    ]["items"]["properties"]
    assert "ready_target" in step_properties
    assert "ready_timeout" in step_properties
