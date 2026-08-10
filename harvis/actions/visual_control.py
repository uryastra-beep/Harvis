from __future__ import annotations

import ctypes
import io
import platform
from ctypes import wintypes
from typing import Any

from harvis.actions.local_vision import (
    LOCAL_CONFIDENCE_THRESHOLD,
    LocalVisionTarget,
    locate_local_target,
)
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
    """Locate a visible UI target locally first, then use Gemini vision as fallback."""

    target_text = str(target).strip()
    if not target_text:
        raise ValueError("vision_click requires a target description.")

    normalized_button = str(button).strip().lower()
    if normalized_button not in {"left", "right", "double_left"}:
        raise ValueError("button must be left, right, or double_left.")

    preferred_capture = capture_preferred_screen()
    full_capture: ScreenCapture | None = None

    local_attempts = 1
    preferred_local = locate_local_target(preferred_capture, target_text)
    best_local_capture = preferred_capture
    best_local_target = preferred_local

    if not _is_confident_local_target(preferred_local):
        candidate_full_capture = capture_full_screen()
        if _capture_geometry(candidate_full_capture) != _capture_geometry(
            preferred_capture
        ):
            full_capture = candidate_full_capture
            local_attempts += 1
            full_local = locate_local_target(full_capture, target_text)
            if _local_target_score(full_local) > _local_target_score(
                best_local_target
            ):
                best_local_capture = full_capture
                best_local_target = full_local

    if _is_confident_local_target(best_local_target):
        return _complete_local_click(
            target_text,
            normalized_button,
            confirmed,
            best_local_capture,
            best_local_target,
            attempts=local_attempts,
        )

    cloud_attempts = 0
    cloud_error: Exception | None = None
    cloud_capture = preferred_capture
    cloud_target: VisionTarget | None = None

    try:
        cloud_target = locate_visual_target(preferred_capture, target_text)
        cloud_attempts += 1

        if not _is_confident_target(cloud_target):
            if full_capture is None:
                candidate_full_capture = capture_full_screen()
                if _capture_geometry(candidate_full_capture) != _capture_geometry(
                    preferred_capture
                ):
                    full_capture = candidate_full_capture

            if full_capture is not None:
                full_target = locate_visual_target(full_capture, target_text)
                cloud_attempts += 1
                if _target_score(full_target) > _target_score(cloud_target):
                    cloud_capture = full_capture
                    cloud_target = full_target
    except Exception as exc:
        cloud_error = exc

    if cloud_target is not None and _is_confident_target(cloud_target):
        return _complete_cloud_click(
            target_text,
            normalized_button,
            confirmed,
            cloud_capture,
            cloud_target,
            local_attempts=local_attempts,
            cloud_attempts=cloud_attempts,
        )

    return _failed_vision_result(
        target_text,
        best_local_target,
        local_attempts=local_attempts,
        cloud_target=cloud_target,
        cloud_attempts=cloud_attempts,
        cloud_error=cloud_error,
    )


def _complete_local_click(
    target_text: str,
    button: str,
    confirmed: bool,
    capture: ScreenCapture,
    target: LocalVisionTarget,
    *,
    attempts: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "local_match",
        "target": target_text,
        "found": target.found,
        "confidence": round(target.confidence, 3),
        "description": target.description,
        "sensitive": target.sensitive,
        "locator": "local",
        "methods": list(target.methods),
        "box": list(target.box),
        "x": target.x,
        "y": target.y,
        "capture_origin": [capture.origin_x, capture.origin_y],
        "capture_size": [capture.width, capture.height],
        "attempts": attempts,
        "cloud_fallback_used": False,
    }
    if target.diagnostics:
        result["diagnostics"] = list(target.diagnostics)

    if target.sensitive and not confirmed:
        result["status"] = "confirmation_required"
        result["requires_confirmation"] = True
        return result

    _move_cursor(target.x, target.y, duration=0.20)
    _click_mouse(button)
    result["status"] = "clicked"
    return result


def _complete_cloud_click(
    target_text: str,
    button: str,
    confirmed: bool,
    capture: ScreenCapture,
    target: VisionTarget,
    *,
    local_attempts: int,
    cloud_attempts: int,
) -> dict[str, Any]:
    screen_x, screen_y = _normalized_to_screen(
        target.x_1000,
        target.y_1000,
        capture,
    )

    result: dict[str, Any] = {
        "status": "cloud_match",
        "target": target_text,
        "found": target.found,
        "confidence": round(target.confidence, 3),
        "description": target.description,
        "sensitive": target.sensitive,
        "box_2d": list(target.box_2d),
        "model": target.model,
        "locator": "gemini",
        "x": screen_x,
        "y": screen_y,
        "capture_origin": [capture.origin_x, capture.origin_y],
        "capture_size": [capture.width, capture.height],
        "attempts": local_attempts + cloud_attempts,
        "local_attempts": local_attempts,
        "cloud_attempts": cloud_attempts,
        "cloud_fallback_used": True,
    }

    if target.sensitive and not confirmed:
        result["status"] = "confirmation_required"
        result["requires_confirmation"] = True
        return result

    _move_cursor(screen_x, screen_y, duration=0.20)
    _click_mouse(button)
    result["status"] = "clicked"
    return result


def _failed_vision_result(
    target_text: str,
    local_target: LocalVisionTarget,
    *,
    local_attempts: int,
    cloud_target: VisionTarget | None,
    cloud_attempts: int,
    cloud_error: Exception | None,
) -> dict[str, Any]:
    best_found = local_target.found
    best_confidence = local_target.confidence
    description = local_target.description
    sensitive = local_target.sensitive

    if cloud_target is not None and _target_score(cloud_target) > best_confidence:
        best_found = cloud_target.found
        best_confidence = cloud_target.confidence
        description = cloud_target.description
        sensitive = cloud_target.sensitive

    if cloud_error is not None:
        status = "local_low_confidence" if local_target.found else "vision_unavailable"
    elif best_found:
        status = "low_confidence"
    else:
        status = "not_found"

    result: dict[str, Any] = {
        "status": status,
        "target": target_text,
        "found": best_found,
        "confidence": round(best_confidence, 3),
        "description": description,
        "sensitive": sensitive,
        "locator": "local+gemini",
        "methods": list(local_target.methods),
        "attempts": local_attempts + cloud_attempts,
        "local_attempts": local_attempts,
        "cloud_attempts": cloud_attempts,
        "cloud_fallback_used": True,
    }

    if local_target.found:
        result["local_box"] = list(local_target.box)
        result["local_x"] = local_target.x
        result["local_y"] = local_target.y
    if local_target.diagnostics:
        result["diagnostics"] = list(local_target.diagnostics)
    if cloud_target is not None:
        result["model"] = cloud_target.model
        result["cloud_confidence"] = round(cloud_target.confidence, 3)
    if cloud_error is not None:
        result["cloud_error"] = str(cloud_error)

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


def _local_target_score(target: LocalVisionTarget) -> float:
    if not target.found:
        return 0.0
    return target.confidence


def _is_confident_local_target(target: LocalVisionTarget) -> bool:
    return target.found and target.confidence >= LOCAL_CONFIDENCE_THRESHOLD


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
