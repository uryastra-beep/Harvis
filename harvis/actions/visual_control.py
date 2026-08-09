from __future__ import annotations

import ctypes
import io
import platform
from ctypes import wintypes
from typing import Any

from harvis.actions.screen_control import (
    ScreenCapture,
    _click_mouse,
    _move_cursor,
    _normalized_to_screen,
    capture_full_screen as capture_full_screen_fallback,
    move_pointer,
)
from harvis.actions.system import SystemActionError
from harvis.actions.vision_locator import (
    VISION_CONFIDENCE_THRESHOLD,
    VisionTarget,
    locate_visual_target,
)

VISION_SCREENSHOT_MAX_DIMENSION = 3200


def capture_full_screen() -> ScreenCapture:
    """Capture the complete virtual desktop, preferring MSS and lossless PNG."""

    return _capture_with_mss(preferred_monitor=False)


def capture_preferred_screen() -> ScreenCapture:
    """Capture the display under the pointer for higher UI-detail accuracy."""

    return _capture_with_mss(preferred_monitor=True)


def vision_click(
    target: str,
    *,
    button: str = "left",
    confirmed: bool = False,
) -> dict[str, Any]:
    """Find a visible screen element with Gemini vision and click its center."""

    target_text = str(target).strip()
    if not target_text:
        raise ValueError("vision_click requires a target description.")

    normalized_button = str(button).strip().lower()
    if normalized_button not in {"left", "right", "double_left"}:
        raise ValueError("button must be left, right, or double_left.")

    preferred_capture = capture_preferred_screen()
    preferred_target = locate_visual_target(preferred_capture, target_text)
    best_capture = preferred_capture
    best_target = preferred_target
    attempts = 1

    if not _is_confident_target(preferred_target):
        full_capture = capture_full_screen()
        if _capture_geometry(full_capture) != _capture_geometry(preferred_capture):
            full_target = locate_visual_target(full_capture, target_text)
            attempts += 1
            if _target_score(full_target) > _target_score(best_target):
                best_capture = full_capture
                best_target = full_target

    result: dict[str, Any] = {
        "status": "not_found",
        "target": target_text,
        "found": best_target.found,
        "confidence": round(best_target.confidence, 3),
        "description": best_target.description,
        "sensitive": best_target.sensitive,
        "box_2d": list(best_target.box_2d),
        "model": best_target.model,
        "attempts": attempts,
    }

    if not _is_confident_target(best_target):
        if best_target.found:
            result["status"] = "low_confidence"
        return result

    screen_x, screen_y = _normalized_to_screen(
        best_target.x_1000,
        best_target.y_1000,
        best_capture,
    )
    result["x"] = screen_x
    result["y"] = screen_y
    result["capture_origin"] = [best_capture.origin_x, best_capture.origin_y]
    result["capture_size"] = [best_capture.width, best_capture.height]

    if best_target.sensitive and not confirmed:
        result["status"] = "confirmation_required"
        result["requires_confirmation"] = True
        return result

    _move_cursor(screen_x, screen_y, duration=0.20)
    _click_mouse(normalized_button)
    result["status"] = "clicked"
    return result


def _capture_with_mss(*, preferred_monitor: bool) -> ScreenCapture:
    try:
        import mss
        from PIL import Image
    except ImportError:
        return capture_full_screen_fallback()

    try:
        with mss.mss() as capture:
            monitors = capture.monitors
            if not monitors:
                raise SystemActionError("Harvis could not find a display to capture.")

            monitor = monitors[0]
            if preferred_monitor and len(monitors) > 1:
                point = _pointer_position()
                if point is not None:
                    selected = _monitor_containing_point(monitors[1:], *point)
                    if selected is not None:
                        monitor = selected
                if monitor is monitors[0]:
                    monitor = monitors[1]

            raw = capture.grab(monitor)
            image = Image.frombytes("RGB", raw.size, raw.rgb)
            origin_x = int(monitor["left"])
            origin_y = int(monitor["top"])
            width = int(monitor["width"])
            height = int(monitor["height"])
    except Exception:
        return capture_full_screen_fallback()

    if width <= 0 or height <= 0:
        raise SystemActionError("Harvis received an empty screen capture.")

    largest_dimension = max(image.size)
    if largest_dimension > VISION_SCREENSHOT_MAX_DIMENSION:
        ratio = VISION_SCREENSHOT_MAX_DIMENSION / float(largest_dimension)
        image = image.resize(
            (
                max(1, int(round(image.width * ratio))),
                max(1, int(round(image.height * ratio))),
            )
        )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return ScreenCapture(
        image_bytes=buffer.getvalue(),
        origin_x=origin_x,
        origin_y=origin_y,
        width=width,
        height=height,
    )


def _pointer_position() -> tuple[int, int] | None:
    if platform.system() == "Windows":
        point = wintypes.POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return int(point.x), int(point.y)
        return None

    try:
        import shutil
        import subprocess

        xdotool = shutil.which("xdotool")
        if xdotool is None:
            return None
        output = subprocess.check_output(
            [xdotool, "getmouselocation", "--shell"],
            text=True,
            timeout=1.0,
        )
        values: dict[str, int] = {}
        for line in output.splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {"X", "Y"}:
                values[key] = int(value)
        if "X" in values and "Y" in values:
            return values["X"], values["Y"]
    except Exception:
        return None
    return None


def _monitor_containing_point(monitors, x: int, y: int):
    for monitor in monitors:
        left = int(monitor["left"])
        top = int(monitor["top"])
        right = left + int(monitor["width"])
        bottom = top + int(monitor["height"])
        if left <= x < right and top <= y < bottom:
            return monitor
    return None


def _capture_geometry(capture: ScreenCapture) -> tuple[int, int, int, int]:
    return capture.origin_x, capture.origin_y, capture.width, capture.height


def _target_score(target: VisionTarget) -> float:
    if not target.found:
        return 0.0
    return target.confidence


def _is_confident_target(target: VisionTarget) -> bool:
    return target.found and target.confidence >= VISION_CONFIDENCE_THRESHOLD


__all__ = [
    "capture_full_screen",
    "capture_preferred_screen",
    "move_pointer",
    "vision_click",
]
