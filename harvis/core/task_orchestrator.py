from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

MAX_TASK_STEPS = 24
MAX_WAIT_SECONDS = 5.0
MAX_TOTAL_WAIT_SECONDS = 15.0

TaskExecutor = Callable[[str, dict[str, Any]], dict[str, Any]]
StatusCallback = Callable[[str], None]

_ALLOWED_ACTIONS = frozenset(
    {
        "set_master_volume",
        "open_url",
        "open_application",
        "close_application",
        "browser_control",
        "media_control",
        "move_pointer",
        "scroll_view",
        "vision_click",
        "type_lines",
        "press_key",
        "type_text",
        "wait",
    }
)

_STOP_STATUSES = frozenset(
    {
        "not_found",
        "low_confidence",
        "vision_unavailable",
    }
)

_BROWSER_ACTIONS = frozenset(
    {
        "close_tab",
        "new_tab",
        "reopen_tab",
        "refresh",
        "back",
        "forward",
        "focus_address",
    }
)

_MEDIA_ACTIONS = frozenset(
    {
        "play_pause",
        "next_track",
        "previous_track",
    }
)

_POINTER_DESTINATIONS = frozenset(
    {
        "top_left",
        "top_center",
        "top_right",
        "center",
        "bottom_left",
        "bottom_center",
        "bottom_right",
        "left_center",
        "right_center",
    }
)


class TaskPlanError(ValueError):
    """Raised when a multi-step task plan is invalid before execution."""


class TaskOrchestrator:
    """Validate and execute bounded deterministic desktop action plans."""

    def __init__(
        self,
        *,
        executor: TaskExecutor,
        on_status: StatusCallback | None = None,
    ) -> None:
        self._executor = executor
        self._on_status = on_status

    def execute(self, steps: list[dict[str, Any]]) -> dict[str, Any]:
        """Execute a validated action plan in order and stop safely on uncertainty."""

        normalized_steps = self._normalize_plan(steps)
        total_steps = len(normalized_steps)
        results: list[dict[str, Any]] = []

        self._notify_status(f"Task plan started: {total_steps} steps")

        for index, step in enumerate(normalized_steps, start=1):
            action = step["action"]
            arguments = step["arguments"]
            self._notify_status(f"Task plan step {index}/{total_steps}")

            try:
                if action == "wait":
                    seconds = float(arguments["seconds"])
                    time.sleep(seconds)
                    result: dict[str, Any] = {
                        "status": "completed",
                        "seconds": seconds,
                    }
                else:
                    result = self._executor(action, arguments)
                    if result is None:
                        result = {"status": "completed"}
            except Exception as exc:
                self._notify_status(f"Task plan stopped at step {index}")
                return {
                    "status": "failed",
                    "steps_total": total_steps,
                    "steps_completed": index - 1,
                    "failed_step": index,
                    "failed_action": action,
                    "error": str(exc),
                    "results": results,
                }

            step_result = {
                "step": index,
                "action": action,
                "result": result,
            }
            results.append(step_result)

            result_status = str(result.get("status", "completed")).strip().lower()
            if result_status == "confirmation_required":
                self._notify_status(f"Task plan paused at step {index} for confirmation")
                return {
                    "status": "paused",
                    "reason": "confirmation_required",
                    "steps_total": total_steps,
                    "steps_completed": index - 1,
                    "pending_step": index,
                    "pending_action": action,
                    "results": results,
                }

            if result_status in _STOP_STATUSES:
                self._notify_status(f"Task plan stopped safely at step {index}")
                return {
                    "status": "stopped",
                    "reason": result_status,
                    "steps_total": total_steps,
                    "steps_completed": index - 1,
                    "stopped_step": index,
                    "stopped_action": action,
                    "results": results,
                }

        self._notify_status("Task plan completed")
        return {
            "status": "completed",
            "steps_total": total_steps,
            "steps_completed": total_steps,
            "results": results,
        }

    def _normalize_plan(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(steps, list):
            raise TaskPlanError("execute_action_plan requires steps as a list.")
        if not steps:
            raise TaskPlanError("execute_action_plan requires at least one step.")
        if len(steps) > MAX_TASK_STEPS:
            raise TaskPlanError(
                f"execute_action_plan supports at most {MAX_TASK_STEPS} steps."
            )

        normalized: list[dict[str, Any]] = []
        total_wait_seconds = 0.0

        for index, raw_step in enumerate(steps, start=1):
            if not isinstance(raw_step, dict):
                raise TaskPlanError(f"Task plan step {index} must be an object.")

            action = str(raw_step.get("action", "")).strip()
            if action not in _ALLOWED_ACTIONS:
                raise TaskPlanError(
                    f"Task plan step {index} uses unsupported action: {action or '<empty>'}."
                )

            arguments = self._arguments_for_step(index, action, raw_step)
            if action == "wait":
                total_wait_seconds += float(arguments["seconds"])
                if total_wait_seconds > MAX_TOTAL_WAIT_SECONDS:
                    raise TaskPlanError(
                        "Task plan wait time exceeds the allowed total wait budget."
                    )

            normalized.append(
                {
                    "action": action,
                    "arguments": arguments,
                }
            )

        return normalized

    def _arguments_for_step(
        self,
        index: int,
        action: str,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        if action == "set_master_volume":
            return {
                "percent": self._bounded_int(
                    step,
                    "percent",
                    index=index,
                    minimum=0,
                    maximum=100,
                )
            }

        if action == "open_url":
            return {"url": self._required_text(step, "url", index=index)}

        if action in {"open_application", "close_application"}:
            return {
                "app_name": self._required_text(step, "app_name", index=index)
            }

        if action == "browser_control":
            browser_action = self._required_text(step, "browser_action", index=index)
            if browser_action not in _BROWSER_ACTIONS:
                raise TaskPlanError(
                    f"Task plan step {index} has an unsupported browser_action."
                )
            return {"action": browser_action}

        if action == "media_control":
            media_action = self._required_text(step, "media_action", index=index)
            if media_action not in _MEDIA_ACTIONS:
                raise TaskPlanError(
                    f"Task plan step {index} has an unsupported media_action."
                )
            return {"action": media_action}

        if action == "move_pointer":
            destination = self._required_text(step, "destination", index=index)
            if destination not in _POINTER_DESTINATIONS:
                raise TaskPlanError(
                    f"Task plan step {index} has an unsupported pointer destination."
                )
            return {"destination": destination}

        if action == "scroll_view":
            direction = self._required_text(step, "direction", index=index)
            if direction not in {"up", "down"}:
                raise TaskPlanError(
                    f"Task plan step {index} direction must be up or down."
                )
            return {
                "direction": direction,
                "steps": self._bounded_int(
                    step,
                    "steps",
                    index=index,
                    minimum=1,
                    maximum=20,
                    default=3,
                ),
            }

        if action == "vision_click":
            button = str(step.get("button", "left")).strip().lower() or "left"
            if button not in {"left", "right", "double_left"}:
                raise TaskPlanError(
                    f"Task plan step {index} has an unsupported mouse button."
                )
            return {
                "target": self._required_text(step, "target", index=index),
                "button": button,
                "confirmed": bool(step.get("confirmed", False)),
            }

        if action == "type_lines":
            lines = step.get("lines")
            if not isinstance(lines, list) or not lines or len(lines) > 50:
                raise TaskPlanError(
                    f"Task plan step {index} requires 1 to 50 text lines."
                )
            return {"lines": [str(line) for line in lines]}

        if action == "press_key":
            key = str(step.get("key", "enter")).strip().lower() or "enter"
            if key != "enter":
                raise TaskPlanError(
                    f"Task plan step {index} only supports the Enter key."
                )
            return {
                "key": key,
                "count": self._bounded_int(
                    step,
                    "count",
                    index=index,
                    minimum=1,
                    maximum=5,
                    default=1,
                ),
            }

        if action == "type_text":
            if "text" not in step:
                raise TaskPlanError(
                    f"Task plan step {index} requires text."
                )
            return {"text": str(step["text"])}

        if action == "wait":
            if "seconds" not in step:
                raise TaskPlanError(
                    f"Task plan step {index} requires seconds."
                )
            try:
                seconds = float(step["seconds"])
            except (TypeError, ValueError) as exc:
                raise TaskPlanError(
                    f"Task plan step {index} seconds must be numeric."
                ) from exc
            if not 0.05 <= seconds <= MAX_WAIT_SECONDS:
                raise TaskPlanError(
                    f"Task plan step {index} wait must be between 0.05 and {MAX_WAIT_SECONDS:.1f} seconds."
                )
            return {"seconds": seconds}

        raise TaskPlanError(f"Task plan step {index} is unsupported.")

    @staticmethod
    def _required_text(
        step: dict[str, Any],
        field: str,
        *,
        index: int,
    ) -> str:
        value = str(step.get(field, "")).strip()
        if not value:
            raise TaskPlanError(
                f"Task plan step {index} requires {field}."
            )
        return value

    @staticmethod
    def _bounded_int(
        step: dict[str, Any],
        field: str,
        *,
        index: int,
        minimum: int,
        maximum: int,
        default: int | None = None,
    ) -> int:
        if field not in step:
            if default is None:
                raise TaskPlanError(
                    f"Task plan step {index} requires {field}."
                )
            return default

        try:
            value = int(step[field])
        except (TypeError, ValueError) as exc:
            raise TaskPlanError(
                f"Task plan step {index} {field} must be an integer."
            ) from exc

        if not minimum <= value <= maximum:
            raise TaskPlanError(
                f"Task plan step {index} {field} must be between {minimum} and {maximum}."
            )
        return value

    def _notify_status(self, status: str) -> None:
        callback = self._on_status
        if callback is not None:
            callback(status)


def task_plan_tool_declaration() -> dict[str, Any]:
    """Return the Gemini function declaration for bounded multi-step workflows."""

    return {
        "name": "execute_action_plan",
        "description": (
            "Execute an ordered multi-step desktop workflow from one user instruction. Use this for long, "
            "deterministic sequences that can be expressed with Harvis's approved local actions. The plan stops "
            "on errors, uncertain visual results, or confirmation-required visual actions. Do not use it for "
            "Harvis self-shutdown or when every next step depends on inspecting a new unknown screen state."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": MAX_TASK_STEPS,
                    "description": "Ordered actions to execute exactly in sequence.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": sorted(_ALLOWED_ACTIONS),
                                "description": "Approved action for this step.",
                            },
                            "app_name": {"type": "string"},
                            "url": {"type": "string"},
                            "percent": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "browser_action": {
                                "type": "string",
                                "enum": sorted(_BROWSER_ACTIONS),
                            },
                            "media_action": {
                                "type": "string",
                                "enum": sorted(_MEDIA_ACTIONS),
                            },
                            "destination": {
                                "type": "string",
                                "enum": sorted(_POINTER_DESTINATIONS),
                            },
                            "direction": {
                                "type": "string",
                                "enum": ["up", "down"],
                            },
                            "steps": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 20,
                            },
                            "target": {"type": "string"},
                            "button": {
                                "type": "string",
                                "enum": ["left", "right", "double_left"],
                            },
                            "confirmed": {"type": "boolean"},
                            "lines": {
                                "type": "array",
                                "minItems": 1,
                                "maxItems": 50,
                                "items": {"type": "string"},
                            },
                            "key": {
                                "type": "string",
                                "enum": ["enter"],
                            },
                            "count": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 5,
                            },
                            "text": {"type": "string"},
                            "seconds": {
                                "type": "number",
                                "minimum": 0.05,
                                "maximum": MAX_WAIT_SECONDS,
                            },
                        },
                        "required": ["action"],
                    },
                }
            },
            "required": ["steps"],
        },
    }


__all__ = [
    "MAX_TASK_STEPS",
    "MAX_TOTAL_WAIT_SECONDS",
    "MAX_WAIT_SECONDS",
    "TaskOrchestrator",
    "TaskPlanError",
    "task_plan_tool_declaration",
]
