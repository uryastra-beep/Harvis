from __future__ import annotations

import io
import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any

from harvis.actions.system import SystemActionError

VISION_MODEL = os.getenv("HARVIS_VISION_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
VISION_CONFIDENCE_THRESHOLD = 0.72
SCREENSHOT_MAX_DIMENSION = 2304


@dataclass(frozen=True)
class ScreenCapture:
    image_bytes: bytes
    origin_x: int
    origin_y: int
    width: int
    height: int


@dataclass(frozen=True)
class VisionTarget:
    found: bool
    x_1000: int
    y_1000: int
    confidence: float
    description: str
    sensitive: bool


def move_pointer(destination: str) -> dict[str, Any]:
    normalized = str(destination).strip().lower()
    supported = {
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
    if normalized not in supported:
        raise SystemActionError(
            f"Unsupported pointer destination '{destination}'."
        )

    left, top, width, height = _primary_screen_bounds()
    edge = 2
    positions = {
        "top_left": (left + edge, top + edge),
        "top_center": (left + width // 2, top + edge),
        "top_right": (left + width - edge, top + edge),
        "center": (left + width // 2, top + height // 2),
        "bottom_left": (left + edge, top + height - edge),
        "bottom_center": (left + width // 2, top + height - edge),
        "bottom_right": (left + width - edge, top + height - edge),
        "left_center": (left + edge, top + height // 2),
        "right_center": (left + width - edge, top + height // 2),
    }
    x, y = positions[normalized]
    _move_cursor(x, y, duration=0.24)

    # Give auto-hidden UI such as the Windows taskbar time to appear.
    time.sleep(0.55)
    return {"status": "completed", "destination": normalized, "x": x, "y": y}


def vision_click(
    target: str,
    *,
    button: str = "left",
    confirmed: bool = False,
) -> dict[str, Any]:
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
    time.sleep(0.08)
    _click_mouse(normalized_button)
    result["status"] = "clicked"
    return result


def type_text(text: str) -> dict[str, Any]:
    value = str(text)
    if not value:
        return {"status": "completed", "characters": 0}

    system_name = platform.system()
    if system_name == "Windows":
        _windows_paste_text(value)
    elif system_name == "Linux":
        _linux_type_text(value)
    else:
        raise SystemActionError(
            f"Text typing is not supported on {system_name or 'this platform'} yet."
        )

    return {"status": "completed", "characters": len(value)}


def capture_full_screen() -> ScreenCapture:
    try:
        from PIL import ImageGrab
    except ImportError as exc:
        raise SystemActionError(
            "Screen vision requires Pillow. Run: python -m pip install -r requirements.txt"
        ) from exc

    system_name = platform.system()
    try:
        if system_name == "Windows":
            image = ImageGrab.grab(all_screens=True)
            origin_x, origin_y, virtual_width, virtual_height = _windows_virtual_screen_bounds()
        else:
            image = ImageGrab.grab()
            origin_x, origin_y = 0, 0
            virtual_width, virtual_height = image.size
    except Exception as exc:
        raise SystemActionError("Harvis could not capture the screen.") from exc

    original_width, original_height = image.size
    if original_width <= 0 or original_height <= 0:
        raise SystemActionError("Harvis received an empty screen capture.")

    # Prefer the actual captured dimensions if platform metrics disagree.
    width = original_width
    height = original_height
    if system_name == "Windows" and virtual_width > 0 and virtual_height > 0:
        width = original_width
        height = original_height

    rgb_image = image.convert("RGB")
    largest_dimension = max(rgb_image.size)
    if largest_dimension > SCREENSHOT_MAX_DIMENSION:
        ratio = SCREENSHOT_MAX_DIMENSION / float(largest_dimension)
        resized = (
            max(1, int(rgb_image.width * ratio)),
            max(1, int(rgb_image.height * ratio)),
        )
        rgb_image = rgb_image.resize(resized)

    buffer = io.BytesIO()
    rgb_image.save(buffer, format="JPEG", quality=84, optimize=True)
    return ScreenCapture(
        image_bytes=buffer.getvalue(),
        origin_x=origin_x,
        origin_y=origin_y,
        width=width,
        height=height,
    )


def locate_visual_target(capture: ScreenCapture, target: str) -> VisionTarget:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemActionError(
            "GEMINI_API_KEY is not configured, so Harvis cannot analyze the screen."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise SystemActionError(
            "The google-genai package is not installed. Run: python -m pip install -r requirements.txt"
        ) from exc

    prompt = f"""
You are the visual locator for a desktop assistant. Analyze this full-screen screenshot and locate the visible clickable UI element that best matches this request:

TARGET: {target}

Return ONLY one JSON object with exactly these fields:
{{
  "found": true or false,
  "x": integer from 0 to 1000,
  "y": integer from 0 to 1000,
  "confidence": number from 0.0 to 1.0,
  "description": "short description of what you found",
  "sensitive": true or false
}}

Coordinates must be normalized to the screenshot: x=0 is the far left, x=1000 is the far right, y=0 is the top, y=1000 is the bottom. Use the center of the clickable element. Match visible text, icons, logos, position descriptions, and normal GUI conventions. If several elements are plausible and the request does not clearly identify one, set found=false rather than guessing. Set sensitive=true only for actions that could cause a consequential commitment or destructive change, such as purchasing, paying, sending money, deleting an account or data, uninstalling software, formatting storage, accepting a legal agreement, or a similarly high-impact confirmation. Ordinary navigation, opening an app, selecting a tab, sending a normal chat message, and closing a normal window are not sensitive by themselves.
""".strip()

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=VISION_MODEL,
            contents=[
                types.Part.from_bytes(
                    data=capture.image_bytes,
                    mime_type="image/jpeg",
                ),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=220,
            ),
        )
    except Exception as exc:
        raise SystemActionError(
            f"Harvis screen vision failed with {VISION_MODEL}: {exc}"
        ) from exc

    return _parse_vision_response(response.text or "")


def _parse_vision_response(text: str) -> VisionTarget:
    cleaned = str(text).strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise SystemActionError("Harvis screen vision returned an invalid location result.") from exc

    found = bool(payload.get("found", False))
    try:
        x_1000 = max(0, min(1000, int(payload.get("x", 0))))
        y_1000 = max(0, min(1000, int(payload.get("y", 0))))
        confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.0))))
    except (TypeError, ValueError) as exc:
        raise SystemActionError("Harvis screen vision returned invalid coordinates.") from exc

    return VisionTarget(
        found=found,
        x_1000=x_1000,
        y_1000=y_1000,
        confidence=confidence,
        description=str(payload.get("description", "")).strip(),
        sensitive=bool(payload.get("sensitive", False)),
    )


def _normalized_to_screen(
    x_1000: int,
    y_1000: int,
    capture: ScreenCapture,
) -> tuple[int, int]:
    x_ratio = max(0.0, min(1.0, x_1000 / 1000.0))
    y_ratio = max(0.0, min(1.0, y_1000 / 1000.0))
    x = capture.origin_x + int(round(x_ratio * max(0, capture.width - 1)))
    y = capture.origin_y + int(round(y_ratio * max(0, capture.height - 1)))
    return x, y


def _primary_screen_bounds() -> tuple[int, int, int, int]:
    if platform.system() == "Windows":
        import ctypes

        user32 = ctypes.windll.user32
        return 0, 0, int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))

    try:
        from PIL import ImageGrab

        image = ImageGrab.grab()
        return 0, 0, image.width, image.height
    except Exception as exc:
        raise SystemActionError("Harvis could not determine the screen size.") from exc


def _windows_virtual_screen_bounds() -> tuple[int, int, int, int]:
    import ctypes

    user32 = ctypes.windll.user32
    return (
        int(user32.GetSystemMetrics(76)),
        int(user32.GetSystemMetrics(77)),
        int(user32.GetSystemMetrics(78)),
        int(user32.GetSystemMetrics(79)),
    )


def _move_cursor(x: int, y: int, *, duration: float) -> None:
    system_name = platform.system()
    if system_name == "Windows":
        _windows_move_cursor(x, y, duration=duration)
        return

    if system_name == "Linux":
        xdotool = shutil.which("xdotool")
        if xdotool is None:
            raise SystemActionError(
                "Linux pointer control currently requires xdotool and an X11-compatible session."
            )
        result = subprocess.run(
            [xdotool, "mousemove", "--sync", str(x), str(y)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemActionError("Harvis could not move the Linux pointer.")
        return

    raise SystemActionError(
        f"Pointer control is not supported on {system_name or 'this platform'} yet."
    )


def _windows_move_cursor(x: int, y: int, *, duration: float) -> None:
    import ctypes
    from ctypes import wintypes

    class Point(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    user32 = ctypes.windll.user32
    start = Point()
    if not user32.GetCursorPos(ctypes.byref(start)):
        user32.SetCursorPos(int(x), int(y))
        return

    steps = max(1, min(24, int(duration / 0.015)))
    for step in range(1, steps + 1):
        ratio = step / steps
        eased = 1.0 - (1.0 - ratio) ** 3
        current_x = int(round(start.x + (x - start.x) * eased))
        current_y = int(round(start.y + (y - start.y) * eased))
        user32.SetCursorPos(current_x, current_y)
        if step < steps:
            time.sleep(duration / steps)


def _click_mouse(button: str) -> None:
    system_name = platform.system()
    if system_name == "Windows":
        import ctypes

        user32 = ctypes.windll.user32
        if button == "right":
            down, up = 0x0008, 0x0010
        else:
            down, up = 0x0002, 0x0004

        user32.mouse_event(down, 0, 0, 0, 0)
        user32.mouse_event(up, 0, 0, 0, 0)
        if button == "double_left":
            time.sleep(0.09)
            user32.mouse_event(down, 0, 0, 0, 0)
            user32.mouse_event(up, 0, 0, 0, 0)
        return

    if system_name == "Linux":
        xdotool = shutil.which("xdotool")
        if xdotool is None:
            raise SystemActionError("Linux mouse clicks require xdotool.")
        mouse_button = "3" if button == "right" else "1"
        repeat = "2" if button == "double_left" else "1"
        result = subprocess.run(
            [xdotool, "click", "--repeat", repeat, "--delay", "90", mouse_button],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemActionError("Harvis could not click the Linux pointer.")
        return

    raise SystemActionError(
        f"Mouse clicks are not supported on {system_name or 'this platform'} yet."
    )


def _windows_paste_text(text: str) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    cf_unicode_text = 13
    gmem_moveable = 0x0002

    previous_text: str | None = None
    if user32.OpenClipboard(None):
        try:
            handle = user32.GetClipboardData(cf_unicode_text)
            if handle:
                pointer = kernel32.GlobalLock(handle)
                if pointer:
                    try:
                        previous_text = ctypes.wstring_at(pointer)
                    finally:
                        kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()

    encoded_size = (len(text) + 1) * ctypes.sizeof(ctypes.c_wchar)
    if not user32.OpenClipboard(None):
        raise SystemActionError("Harvis could not access the Windows clipboard.")

    memory_handle = None
    try:
        user32.EmptyClipboard()
        memory_handle = kernel32.GlobalAlloc(gmem_moveable, encoded_size)
        if not memory_handle:
            raise SystemActionError("Harvis could not allocate clipboard memory.")
        pointer = kernel32.GlobalLock(memory_handle)
        if not pointer:
            raise SystemActionError("Harvis could not lock clipboard memory.")
        try:
            source = ctypes.create_unicode_buffer(text)
            ctypes.memmove(pointer, source, encoded_size)
        finally:
            kernel32.GlobalUnlock(memory_handle)
        if not user32.SetClipboardData(cf_unicode_text, memory_handle):
            raise SystemActionError("Harvis could not write to the Windows clipboard.")
        memory_handle = None
    finally:
        user32.CloseClipboard()
        if memory_handle:
            kernel32.GlobalFree(memory_handle)

    keyup = 0x0002
    vk_control = 0x11
    vk_v = 0x56
    user32.keybd_event(vk_control, 0, 0, 0)
    user32.keybd_event(vk_v, 0, 0, 0)
    user32.keybd_event(vk_v, 0, keyup, 0)
    user32.keybd_event(vk_control, 0, keyup, 0)

    if previous_text is not None:
        time.sleep(0.16)
        _windows_set_clipboard_text(previous_text)


def _windows_set_clipboard_text(text: str) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    cf_unicode_text = 13
    gmem_moveable = 0x0002
    encoded_size = (len(text) + 1) * ctypes.sizeof(ctypes.c_wchar)

    if not user32.OpenClipboard(None):
        return

    memory_handle = None
    try:
        user32.EmptyClipboard()
        memory_handle = kernel32.GlobalAlloc(gmem_moveable, encoded_size)
        if not memory_handle:
            return
        pointer = kernel32.GlobalLock(memory_handle)
        if not pointer:
            return
        try:
            source = ctypes.create_unicode_buffer(text)
            ctypes.memmove(pointer, source, encoded_size)
        finally:
            kernel32.GlobalUnlock(memory_handle)
        if user32.SetClipboardData(cf_unicode_text, memory_handle):
            memory_handle = None
    finally:
        user32.CloseClipboard()
        if memory_handle:
            kernel32.GlobalFree(memory_handle)


def _linux_type_text(text: str) -> None:
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        raise SystemActionError(
            "Linux text typing currently requires xdotool and an X11-compatible session."
        )

    result = subprocess.run(
        [xdotool, "type", "--clearmodifiers", "--delay", "1", "--", text],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemActionError("Harvis could not type into the active Linux window.")
