from __future__ import annotations

import ctypes
import platform
import shutil
import subprocess
import time
from typing import Any

from harvis.actions.system import SystemActionError


def type_text(text: str) -> dict[str, Any]:
    value = str(text)
    if not value:
        return {"status": "completed", "characters": 0}

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


def _windows_type_unicode(text: str) -> None:
    """Send Unicode keyboard input using the real Windows INPUT structure layout."""

    from ctypes import wintypes

    input_keyboard = 1
    keyeventf_keyup = 0x0002
    keyeventf_unicode = 0x0004
    vk_return = 0x0D
    vk_tab = 0x09

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

    def send_pair(keyboard_down: KeyboardInput, keyboard_up: KeyboardInput) -> None:
        inputs = (Input * 2)(
            Input(type=input_keyboard, ki=keyboard_down),
            Input(type=input_keyboard, ki=keyboard_up),
        )
        sent = send_input(2, inputs, ctypes.sizeof(Input))
        if sent != 2:
            error_code = ctypes.get_last_error()
            raise SystemActionError(
                f"Harvis could not send Windows keyboard input (error {error_code})."
            )

    def send_virtual_key(vk_code: int) -> None:
        send_pair(
            KeyboardInput(
                wVk=vk_code,
                wScan=0,
                dwFlags=0,
                time=0,
                dwExtraInfo=0,
            ),
            KeyboardInput(
                wVk=vk_code,
                wScan=0,
                dwFlags=keyeventf_keyup,
                time=0,
                dwExtraInfo=0,
            ),
        )

    def send_unicode_code_unit(code_unit: int) -> None:
        send_pair(
            KeyboardInput(
                wVk=0,
                wScan=code_unit,
                dwFlags=keyeventf_unicode,
                time=0,
                dwExtraInfo=0,
            ),
            KeyboardInput(
                wVk=0,
                wScan=code_unit,
                dwFlags=keyeventf_unicode | keyeventf_keyup,
                time=0,
                dwExtraInfo=0,
            ),
        )

    for character in text:
        if character == "\n":
            send_virtual_key(vk_return)
            continue
        if character == "\t":
            send_virtual_key(vk_tab)
            continue

        encoded = character.encode("utf-16-le")
        for index in range(0, len(encoded), 2):
            code_unit = int.from_bytes(encoded[index : index + 2], "little")
            send_unicode_code_unit(code_unit)

        if len(text) < 120:
            time.sleep(0.0015)


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
