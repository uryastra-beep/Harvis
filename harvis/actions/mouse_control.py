from __future__ import annotations

import ctypes
import platform
import shutil
import subprocess
from typing import Any

from harvis.actions.system import SystemActionError

WINDOWS_WHEEL_DELTA = 120
WINDOWS_MOUSEEVENTF_WHEEL = 0x0800
MIN_SCROLL_STEPS = 1
MAX_SCROLL_STEPS = 20


def scroll_view(direction: str, steps: int = 3) -> dict[str, Any]:
    """Scroll the control under the pointer in the requested direction."""

    normalized_direction = str(direction).strip().lower()
    if normalized_direction not in {"up", "down"}:
        raise ValueError("direction must be up or down.")

    normalized_steps = max(MIN_SCROLL_STEPS, min(MAX_SCROLL_STEPS, int(steps)))
    system_name = platform.system()

    if system_name == "Windows":
        _scroll_windows(normalized_direction, normalized_steps)
    elif system_name == "Linux":
        _scroll_linux(normalized_direction, normalized_steps)
    else:
        raise SystemActionError(
            f"Scrolling is not supported on {system_name or 'this platform'} yet."
        )

    return {
        "status": "completed",
        "direction": normalized_direction,
        "steps": normalized_steps,
    }


def _scroll_windows(direction: str, steps: int) -> None:
    wheel_delta = WINDOWS_WHEEL_DELTA if direction == "up" else -WINDOWS_WHEEL_DELTA
    user32 = ctypes.windll.user32

    for _ in range(steps):
        user32.mouse_event(
            WINDOWS_MOUSEEVENTF_WHEEL,
            0,
            0,
            wheel_delta,
            0,
        )


def _scroll_linux(direction: str, steps: int) -> None:
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        raise SystemActionError(
            "Scrolling on Linux requires xdotool to be installed."
        )

    button = "4" if direction == "up" else "5"
    try:
        subprocess.run(
            [xdotool, "click", "--repeat", str(steps), "--delay", "45", button],
            check=True,
            timeout=3.0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemActionError("Harvis could not scroll the active view.") from exc


__all__ = ["scroll_view"]
