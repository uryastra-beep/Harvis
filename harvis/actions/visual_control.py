from __future__ import annotations

import ctypes
import io
import platform
import time
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
    move_pointer,
)
from harvis.actions.screen_control import (
    capture_full_screen as capture_full_screen_fallback,
)
from harvis.actions.system import SystemActionError
from harvis.actions.vision_locator import (
    VISION_CONFIDENCE_THRESHOLD,
    VisionTarget,
    locate_visual_target,
)

VISION_SCREENSHOT_MAX_DIMENSION = 3200
SCREEN_STABILITY_TIMEOUT_SECONDS = 6.0
VISUAL_TARGET_TIMEOUT_SECONDS = 10.0


def capture_full_screen() -> ScreenCapture:
    """Capture the complete virtual desktop, preferring MSS and lossless PNG."""

    return _capture_with_mss(preferred_monitor=False)


def capture_preferred_screen() -> ScreenCapture:
    """Capture the display under the pointer for higher UI-detail accuracy."""

    return _capture_with_mss(preferred_monitor=True)


def wait_for_screen_stable(
    *,
    timeout_seconds: float = SCREEN_STABILITY_TIMEOUT_SECONDS,
    sample_interval: float = 0.35,
    required_stable_samples: int = 2,
    difference_threshold: float = 3.0,
) -> dict[str, Any]:
    """Wait until consecutive desktop captures indicate that the visible UI settled."""

    timeout = max(0.5, min(15.0, float(timeout_seconds)))
    interval = max(0.15, min(1.0, float(sample_interval)))
    required = max(1, min(5, int(required_stable_samples)))
    threshold = max(0.0, min(32.0, float(difference_threshold)))
    deadline = time.monotonic() + timeout
    previous_signature: tuple[int, ...] | None = None
    stable_samples = 0
    samples = 0
    last_difference: float | None = None

    while True:
        try:
            capture = capture_full_screen()
            signature = _screen_signature(capture)
        except Exception as exc:
            return {
                "status": "screen_unavailable",
                "error": str(exc),
                "samples": samples,
            }

        samples += 1
        if previous_signature is not None:
            last_difference = _signature_difference(previous_signature, signature)
            if last_difference <= threshold:
                stable_samples += 1
            else:
                stable_samples = 0

            if stable_samples >= required:
                return {
                    "status": "completed",
                    "stable": True,
                    "samples": samples,
                    "difference": round(last_difference, 3),
                }

        previous_signature = signature
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {
                "status": "screen_unstable",
                "stable": False,
                "samples": samples,
                "difference": (
                    None if last_difference is None else round(last_difference, 3)
                ),
            }

        time.sleep(min(interval, remaining))


def wait_for_visual_target(
    target: str,
    *,
    timeout_seconds: float = VISUAL_TARGET_TIMEOUT_SECONDS,
    poll_seconds: float = 1.25,
) -> dict[str, Any]:
    """Wait for a visible target without clicking it, stopping after a bounded timeout."""

    target_text = str(target).strip()
    if not target_text:
        raise ValueError("wait_for_visual_target requires a target description.")

    timeout = max(1.0, min(15.0, float(timeout_seconds)))
    poll = max(0.5, min(3.0, float(poll_seconds)))
    deadline = time.monotonic() + timeout
    attempts = 0
    cloud_failures = 0
    best_found = False
    best_confidence = 0.0
    best_description = "Could not find it."
    best_locator = "gemini+local"

    while True:
        attempts += 1
        capture = capture_full_screen()

        try:
            cloud_target = locate_visual_target(capture, target_text)
            if cloud_target.found and cloud_target.confidence > best_confidence:
                best_found = True
                best_confidence = cloud_target.confidence
                best_description = cloud_target.description
                best_locator = "gemini"
            if _is_confident_target(cloud_target):
                screen_x, screen_y = _normalized_to_screen(
                    cloud_target.x_1000,
                    cloud_target.y_1000,
                    capture,
                )
                return {
                    "status": "found",
                    "target": target_text,
                    "found": True,
                    "confidence": round(cloud_target.confidence, 3),
                    "description": cloud_target.description,
                    "locator": "gemini",
                    "x": screen_x,
                    "y": screen_y,
                    "attempts": attempts,
                    "waited_seconds": round(timeout - max(0.0, deadline - time.monotonic()), 2),
                }
        except Exception:
            cloud_failures += 1

        local_target = locate_local_target(capture, target_text)
        if local_target.found and local_target.confidence > best_confidence:
            best_found = True
            best_confidence = local_target.confidence
            best_description = local_target.description
            best_locator = "local"
        if _is_confident_local_target(local_target):
            return {
                "status": "found",
                "target": target_text,
                "found": True,
                "confidence": round(local_target.confidence, 3),
                "description": local_target.description,
                "locator": "local",
                "methods": list(local_target.methods),
                "x": local_target.x,
                "y": local_target.y,
                "attempts": attempts,
                "waited_seconds": round(timeout - max(0.0, deadline - time.monotonic()), 2),
            }

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if best_found:
                status = "low_confidence"
            elif cloud_failures == attempts:
                status = "vision_unavailable"
            else:
                status = "not_found"
            return {
                "status": status,
                "target": target_text,
                "found": best_found,
                "confidence": round(best_confidence, 3),
                "description": best_description,
                "locator": best_locator,
                "attempts": attempts,
                "waited_seconds": round(timeout, 2),
            }

        time.sleep(min(poll, remaining))


def vision_click(
    target: str,
    *,
    button: str = "left",
    confirmed: bool = False,
) -> dict[str, Any]:
    """Prefer Gemini Vision, fall back locally, then retry Gemini once."""

    target_text = str(target).strip()
    if not target_text:
        raise ValueError("vision_click requires a target description.")

    normalized_button = str(button).strip().lower()
    if normalized_button not in {"left", "right", "double_left"}:
        raise ValueError("button must be left, right, or double_left.")

    preferred_capture = capture_preferred_screen()
    full_capture: ScreenCapture | None = None

    cloud_attempts = 0
    cloud_errors: list[Exception] = []
    best_cloud_capture = preferred_capture
    best_cloud_target: VisionTarget | None = None

    # Gemini Vision is the primary locator whenever it is available and confident.
    cloud_attempts += 1
    try:
        primary_cloud_target = locate_visual_target(preferred_capture, target_text)
        best_cloud_target = primary_cloud_target
        if _is_confident_target(primary_cloud_target):
            return _complete_cloud_click(
                target_text,
                normalized_button,
                confirmed,
                preferred_capture,
                primary_cloud_target,
                local_attempts=0,
                cloud_attempts=cloud_attempts,
            )
    except Exception as exc:
        cloud_errors.append(exc)

    # If Gemini Vision cannot confidently locate the target, use the local stack.
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
            cloud_attempts=cloud_attempts,
        )

    # Local vision also failed. Give Gemini Vision one final chance, preferably
    # with the full desktop capture when it differs from the preferred display.
    if full_capture is None:
        candidate_full_capture = capture_full_screen()
        if _capture_geometry(candidate_full_capture) != _capture_geometry(
            preferred_capture
        ):
            full_capture = candidate_full_capture

    final_cloud_capture = full_capture or preferred_capture
    cloud_attempts += 1
    try:
        final_cloud_target = locate_visual_target(final_cloud_capture, target_text)
        if (
            best_cloud_target is None
            or _target_score(final_cloud_target) > _target_score(best_cloud_target)
        ):
            best_cloud_capture = final_cloud_capture
            best_cloud_target = final_cloud_target

        if _is_confident_target(final_cloud_target):
            return _complete_cloud_click(
                target_text,
                normalized_button,
                confirmed,
                final_cloud_capture,
                final_cloud_target,
                local_attempts=local_attempts,
                cloud_attempts=cloud_attempts,
            )
    except Exception as exc:
        cloud_errors.append(exc)

    return _failed_vision_result(
        target_text,
        best_local_target,
        local_attempts=local_attempts,
        cloud_target=best_cloud_target,
        cloud_capture=best_cloud_capture,
        cloud_attempts=cloud_attempts,
        cloud_error=cloud_errors[-1] if cloud_errors else None,
    )


def local_vision_click(
    target: str,
    *,
    button: str = "left",
) -> dict[str, Any]:
    """Locate and click a target without making any Gemini request."""

    target_text = str(target).strip()
    if not target_text:
        raise ValueError("local_vision_click requires a target description.")

    normalized_button = str(button).strip().lower()
    if normalized_button not in {"left", "right", "double_left"}:
        raise ValueError("button must be left, right, or double_left.")

    preferred_capture = capture_preferred_screen()
    best_capture = preferred_capture
    best_target = locate_local_target(preferred_capture, target_text)
    attempts = 1

    if not _is_confident_local_target(best_target):
        full_capture = capture_full_screen()
        if _capture_geometry(full_capture) != _capture_geometry(preferred_capture):
            attempts += 1
            full_target = locate_local_target(full_capture, target_text)
            if _local_target_score(full_target) > _local_target_score(best_target):
                best_capture = full_capture
                best_target = full_target

    if _is_confident_local_target(best_target):
        return _complete_local_click(
            target_text,
            normalized_button,
            False,
            best_capture,
            best_target,
            attempts=attempts,
        )

    return {
        "status": "low_confidence" if best_target.found else "not_found",
        "target": target_text,
        "found": best_target.found,
        "confidence": round(best_target.confidence, 3),
        "description": "Could not find it.",
        "sensitive": best_target.sensitive,
        "locator": "local",
        "methods": list(best_target.methods),
        "attempts": attempts,
        "local_attempts": attempts,
        "cloud_attempts": 0,
        "local_fallback_used": False,
        "cloud_fallback_used": False,
    }


def click_screen_coordinates(
    x: int,
    y: int,
    *,
    expected_origin: tuple[int, int],
    expected_size: tuple[int, int],
) -> dict[str, Any]:
    """Click an inspected questionnaire point only if desktop geometry is unchanged."""

    screen_x = int(x)
    screen_y = int(y)
    origin_x, origin_y = (int(value) for value in expected_origin)
    width, height = (int(value) for value in expected_size)
    if width <= 0 or height <= 0:
        return {"status": "invalid_coordinates"}

    capture = capture_full_screen()
    expected_geometry = (origin_x, origin_y, width, height)
    if _capture_geometry(capture) != expected_geometry:
        return {
            "status": "screen_geometry_changed",
            "expected_geometry": list(expected_geometry),
            "current_geometry": list(_capture_geometry(capture)),
        }

    if not (
        origin_x <= screen_x < origin_x + width
        and origin_y <= screen_y < origin_y + height
    ):
        return {"status": "invalid_coordinates", "x": screen_x, "y": screen_y}

    _move_cursor(screen_x, screen_y, duration=0.20)
    _click_mouse("left")
    return {"status": "clicked", "x": screen_x, "y": screen_y}


def _complete_local_click(
    target_text: str,
    button: str,
    confirmed: bool,
    capture: ScreenCapture,
    target: LocalVisionTarget,
    *,
    attempts: int,
    cloud_attempts: int = 0,
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
        "attempts": attempts + cloud_attempts,
        "local_attempts": attempts,
        "cloud_attempts": cloud_attempts,
        "local_fallback_used": cloud_attempts > 0,
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
        "local_fallback_used": local_attempts > 0,
        "cloud_fallback_used": local_attempts > 0,
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
    cloud_capture: ScreenCapture,
    cloud_attempts: int,
    cloud_error: Exception | None,
) -> dict[str, Any]:
    best_found = local_target.found
    best_confidence = local_target.confidence
    sensitive = local_target.sensitive

    if cloud_target is not None and _target_score(cloud_target) > best_confidence:
        best_found = cloud_target.found
        best_confidence = cloud_target.confidence
        sensitive = cloud_target.sensitive

    if cloud_error is not None:
        status = "vision_unavailable"
    elif best_found:
        status = "low_confidence"
    else:
        status = "not_found"

    result: dict[str, Any] = {
        "status": status,
        "target": target_text,
        "found": best_found,
        "confidence": round(best_confidence, 3),
        "description": "Could not find it.",
        "sensitive": sensitive,
        "locator": "gemini+local+gemini",
        "methods": list(local_target.methods),
        "attempts": local_attempts + cloud_attempts,
        "local_attempts": local_attempts,
        "cloud_attempts": cloud_attempts,
        "local_fallback_used": True,
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
        result["cloud_capture_origin"] = [
            cloud_capture.origin_x,
            cloud_capture.origin_y,
        ]
    if cloud_error is not None:
        result["cloud_error"] = "Gemini Vision unavailable."

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


def _screen_signature(capture: ScreenCapture) -> tuple[int, ...]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemActionError(
            "Pillow is required for Harvis screen stability checks."
        ) from exc

    with Image.open(io.BytesIO(capture.image_bytes)) as image:
        reduced = image.convert("L").resize((48, 27))
        return tuple(int(value) for value in reduced.getdata())


def _signature_difference(
    first: tuple[int, ...],
    second: tuple[int, ...],
) -> float:
    if not first or len(first) != len(second):
        return 255.0
    return sum(abs(left - right) for left, right in zip(first, second)) / len(first)


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
    "SCREEN_STABILITY_TIMEOUT_SECONDS",
    "VISUAL_TARGET_TIMEOUT_SECONDS",
    "capture_full_screen",
    "capture_preferred_screen",
    "click_screen_coordinates",
    "local_vision_click",
    "move_pointer",
    "vision_click",
    "wait_for_screen_stable",
    "wait_for_visual_target",
]
