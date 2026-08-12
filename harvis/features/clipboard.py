from __future__ import annotations

import ctypes
import platform
import shutil
import subprocess
from ctypes import wintypes

from harvis.actions.system import SystemActionError

MAX_CLIPBOARD_CHARACTERS = 50_000


def read_clipboard_text(*, max_characters: int = MAX_CLIPBOARD_CHARACTERS) -> str:
    limit = max(1, min(MAX_CLIPBOARD_CHARACTERS, int(max_characters)))
    system_name = platform.system()
    if system_name == "Windows":
        return _read_windows_clipboard()[:limit]
    if system_name == "Linux":
        return _read_linux_clipboard()[:limit]
    if system_name == "Darwin":
        return _run_clipboard_command(["pbpaste"])[:limit]
    raise SystemActionError(
        f"Clipboard reading is not supported on {system_name or 'this platform'} yet."
    )


def _read_windows_clipboard() -> str:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    cf_unicode_text = 13
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    if not user32.OpenClipboard(None):
        raise SystemActionError("Harvis could not access the Windows clipboard.")
    try:
        handle = user32.GetClipboardData(cf_unicode_text)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _read_linux_clipboard() -> str:
    if shutil.which("wl-paste"):
        return _run_clipboard_command(["wl-paste", "--no-newline"])
    if shutil.which("xclip"):
        return _run_clipboard_command(["xclip", "-selection", "clipboard", "-o"])
    if shutil.which("xsel"):
        return _run_clipboard_command(["xsel", "--clipboard", "--output"])
    raise SystemActionError("Linux clipboard reading requires wl-paste, xclip, or xsel.")


def _run_clipboard_command(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemActionError("Harvis could not read the clipboard.") from exc
    return completed.stdout
