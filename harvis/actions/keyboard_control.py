from __future__ import annotations

import ctypes
import platform
import re
import shutil
import subprocess
from typing import Any

from harvis.actions.system import SystemActionError

SUSPICIOUS_PUNCTUATION_RE = re.compile(
    r"(?:([!?¿¡.,;:])\1{3,}|[!?¿¡.,;:]{6,})"
)
SUPPORTED_KEYS = {"enter"}
MAX_LINE_SEQUENCE = 50


def type_text(text: str) -> dict[str, Any]:
    value = _normalize_text_payload(str(text))
    if not value:
        return {"status": "completed", "characters": 0}

    _validate_text_payload(value)

    system_name = platform.system()
    if system_name == "Windows":
        _windows_type_unicode(value)
    elif system_name == "Linux":
        _linux_type_text(value)
    else:
        raise SystemActionError(
            f"Text typing is not supported on {system_name or 'this platform'} yet."
        )

    return {"status": "completed", "characters": len(value)}


def press_key(key: str, count: int = 1) -> dict[str, Any]:
    """Press a supported physical keyboard key without encoding it as text."""

    normalized_key = str(key).strip().lower()
    if normalized_key not in SUPPORTED_KEYS:
        raise ValueError(f"Unsupported keyboard key '{key}'.")

    normalized_count = max(1, min(5, int(count)))
    system_name = platform.system()

    if system_name == "Windows":
        _windows_press_key(normalized_key, normalized_count)
    elif system_name == "Linux":
        _linux_press_key(normalized_key, normalized_count)
    else:
        raise SystemActionError(
            f"Keyboard key presses are not supported on {system_name or 'this platform'} yet."
        )

    return {
        "status": "completed",
        "key": normalized_key,
        "count": normalized_count,
    }


def type_lines(lines: list[str]) -> dict[str, Any]:
    """Type multiple literal lines with exactly one physical Enter between them."""

    if not isinstance(lines, list):
        raise ValueError("type_lines requires a list of text lines.")
    if not lines:
        return {
            "status": "completed",
            "lines": 0,
            "characters": 0,
            "enters": 0,
        }
    if len(lines) > MAX_LINE_SEQUENCE:
        raise ValueError(
            f"type_lines supports at most {MAX_LINE_SEQUENCE} lines per call."
        )

    normalized_lines: list[str] = []
    for line in lines:
        value = _normalize_text_payload(str(line))
        if "\n" in value:
            raise ValueError(
                "Each type_lines item must contain exactly one line without newline characters."
            )
        _validate_text_payload(value)
        normalized_lines.append(value)

    for index, value in enumerate(normalized_lines):
        if value:
            type_text(value)
        if index < len(normalized_lines) - 1:
            press_key("enter")

    return {
        "status": "completed",
        "lines": len(normalized_lines),
        "characters": sum(len(value) for value in normalized_lines),
        "enters": len(normalized_lines) - 1,
    }


def _normalize_text_payload(text: str) -> str:
    """Normalize real line endings while preserving literal escape sequences."""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def _validate_text_payload(text: str) -> None:
    """Reject obviously corrupted tool payloads before they reach the keyboard."""

    if "\x00" in text or "\ufffd" in text:
        raise SystemActionError(
            "The text payload contains invalid characters. Reconstruct the intended text and retry type_text once."
        )

    if SUSPICIOUS_PUNCTUATION_RE.search(text):
        raise SystemActionError(
            "The text payload contains an abnormal punctuation run and appears corrupted. "
            "Reconstruct the intended clean text from the user's request and retry type_text once. "
            "Do not use repeated punctuation as a placeholder."
        )


def _windows_type_unicode(text: str) -> None:
    """Send exact Unicode keyboard input in deterministic batches on Windows."""

    from ctypes import wintypes

    input_keyboard = 1
    keyeventf_keyup = 0x0002
    keyeventf_unicode = 0x0004
    vk_return = 0x0D
    vk_tab = 0x09
    max_batch_inputs = 128

    ulong_ptr = wintypes.WPARAM

    class MouseInput(ctypes.Structure):
        _fields_ = [
            ("dx", wintypes.LONG),
            ("dy", wintypes.LONG),
            ("mouseData", wintypes.DWORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ulong_ptr),
        ]

    class KeyboardInput(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ulong_ptr),
        ]

    class HardwareInput(ctypes.Structure):
        _fields_ = [
            ("uMsg", wintypes.DWORD),
            ("wParamL", wintypes.WORD),
            ("wParamH", wintypes.WORD),
        ]

    class InputUnion(ctypes.Union):
        _fields_ = [
            ("mi", MouseInput),
            ("ki", KeyboardInput),
            ("hi", HardwareInput),
        ]

    class Input(ctypes.Structure):
        _anonymous_ = ("union",)
        _fields_ = [
            ("type", wintypes.DWORD),
            ("union", InputUnion),
        ]

    send_input = ctypes.windll.user32.SendInput
    send_input.argtypes = (wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int)
    send_input.restype = wintypes.UINT

    events: list[Input] = []

    def append_virtual_key(vk_code: int) -> None:
        events.extend(
            (
                Input(
                    type=input_keyboard,
                    ki=KeyboardInput(
                        wVk=vk_code,
                        wScan=0,
                        dwFlags=0,
                        time=0,
                        dwExtraInfo=0,
                    ),
                ),
                Input(
                    type=input_keyboard,
                    ki=KeyboardInput(
                        wVk=vk_code,
                        wScan=0,
                        dwFlags=keyeventf_keyup,
                        time=0,
                        dwExtraInfo=0,
                    ),
                ),
            )
        )

    def append_unicode_code_unit(code_unit: int) -> None:
        events.extend(
            (
                Input(
                    type=input_keyboard,
                    ki=KeyboardInput(
                        wVk=0,
                        wScan=code_unit,
                        dwFlags=keyeventf_unicode,
                        time=0,
                        dwExtraInfo=0,
                    ),
                ),
                Input(
                    type=input_keyboard,
                    ki=KeyboardInput(
                        wVk=0,
                        wScan=code_unit,
                        dwFlags=keyeventf_unicode | keyeventf_keyup,
                        time=0,
                        dwExtraInfo=0,
                    ),
                ),
            )
        )

    for character in text:
        if character == "\n":
            append_virtual_key(vk_return)
            continue
        if character == "\t":
            append_virtual_key(vk_tab)
            continue

        encoded = character.encode("utf-16-le")
        for index in range(0, len(encoded), 2):
            append_unicode_code_unit(
                int.from_bytes(encoded[index : index + 2], "little")
            )

    for start in range(0, len(events), max_batch_inputs):
        chunk = events[start : start + max_batch_inputs]
        if not chunk:
            continue

        input_array = (Input * len(chunk))(*chunk)
        sent = send_input(
            len(chunk),
            input_array,
            ctypes.sizeof(Input),
        )
        if sent != len(chunk):
            error_code = ctypes.get_last_error()
            raise SystemActionError(
                "Harvis could not send all Windows keyboard input "
                f"({sent}/{len(chunk)} events, error {error_code})."
            )


def _windows_press_key(key: str, count: int) -> None:
    virtual_keys = {"enter": 0x0D}
    vk_code = virtual_keys[key]
    keyeventf_keyup = 0x0002
    user32 = ctypes.windll.user32

    for _ in range(count):
        user32.keybd_event(vk_code, 0, 0, 0)
        user32.keybd_event(vk_code, 0, keyeventf_keyup, 0)


def _linux_type_text(text: str) -> None:
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        raise SystemActionError(
            "Linux text typing currently requires xdotool and an X11-compatible session."
        )

    chunks = text.split("\n")
    for index, chunk in enumerate(chunks):
        if chunk:
            result = subprocess.run(
                [xdotool, "type", "--clearmodifiers", "--delay", "1", "--", chunk],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise SystemActionError(
                    "Harvis could not type into the active Linux window."
                )

        if index < len(chunks) - 1:
            result = subprocess.run(
                [xdotool, "key", "--clearmodifiers", "Return"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise SystemActionError(
                    "Harvis could not press Enter in the active Linux window."
                )


def _linux_press_key(key: str, count: int) -> None:
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        raise SystemActionError(
            "Linux keyboard key presses currently require xdotool and an X11-compatible session."
        )

    key_names = {"enter": "Return"}
    for _ in range(count):
        result = subprocess.run(
            [xdotool, "key", "--clearmodifiers", key_names[key]],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemActionError("Harvis could not press the requested Linux key.")


__all__ = ["press_key", "type_lines", "type_text"]
