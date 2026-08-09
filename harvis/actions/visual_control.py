from __future__ import annotations

import io
from typing import Any

from harvis.actions.screen_control import (
    SCREENSHOT_MAX_DIMENSION,
    VISION_CONFIDENCE_THRESHOLD,
    ScreenCapture,
    _click_mouse,
    _move_cursor,
    _normalized_to_screen,
    capture_full_screen as capture_full_screen_fallback,
    locate_visual_target,
    move_pointer,
)
from harvis.actions.system import SystemActionError


def capture_full_screen() -> ScreenCapture:
    """Capture the full virtual desktop with MSS, falling back to Pillow ImageGrab."""

    try:
        import mss
        from PIL import Image
    except ImportError:
        return capture_full_screen_fallback()

    try:
        with mss.mss() as capture:
            if not capture.monitors:
                raise SystemActionError("Harvis could not find a display to capture.")

            monitor = capture.monitors[0]
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
    if largest_dimension > SCREENSHOT_MAX_DIMENSION:
        ratio = SCREENSHOT_MAX_DIMENSION / float(largest_dimension)
        image = image.resize(
            (
                max(1, int(image.width * ratio)),
                max(1, int(image.height * ratio)),
            )
        )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=86, optimize=True)
    return ScreenCapture(
        image_bytes=buffer.getvalue(),
        origin_x=origin_x,
        origin_y=origin_y,
        width=width,
        height=height,
    )


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

    capture = capture_full_screen()
    located = locate_visual_target(capture, target_text)

    result: dict[str, Any] = {
        "status": "not_found",
        "target": target_text,
        "found": located.found,
        "confidence": round(located.confidence, 3),
        "description": located.description,
        "sensitive": located.sensitive,
    }

    if not located.found or located.confidence < VISION_CONFIDENCE_THRESHOLD:
        if located.found:
            result["status"] = "low_confidence"
        return result

    screen_x, screen_y = _normalized_to_screen(
        located.x_1000,
        located.y_1000,
        capture,
    )
    result["x"] = screen_x
    result["y"] = screen_y

    if located.sensitive and not confirmed:
        result["status"] = "confirmation_required"
        result["requires_confirmation"] = True
        return result

    _move_cursor(screen_x, screen_y, duration=0.20)
    _click_mouse(normalized_button)
    result["status"] = "clicked"
    return result


__all__ = ["capture_full_screen", "move_pointer", "vision_click"]
