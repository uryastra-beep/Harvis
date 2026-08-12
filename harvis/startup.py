from __future__ import annotations

import os
import platform
import shlex
import sys
from pathlib import Path

from harvis.features.storage import atomic_write_text

WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_VALUE_NAME = "Harvis"


def apply_startup_setting(enabled: bool) -> None:
    system_name = platform.system()
    if system_name == "Windows":
        _apply_windows_startup(bool(enabled))
    elif system_name == "Linux":
        _apply_linux_startup(bool(enabled))


def _launch_command() -> list[str]:
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve())]
    return [str(Path(sys.executable).resolve()), "-m", "harvis"]


def _apply_windows_startup(enabled: bool) -> None:
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
        if enabled:
            command = subprocess_list2cmdline(_launch_command())
            winreg.SetValueEx(key, WINDOWS_VALUE_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, WINDOWS_VALUE_NAME)
            except FileNotFoundError:
                pass


def _apply_linux_startup(enabled: bool) -> None:
    path = Path.home() / ".config" / "autostart" / "harvis.desktop"
    if not enabled:
        path.unlink(missing_ok=True)
        return
    executable = " ".join(shlex.quote(part) for part in _launch_command())
    atomic_write_text(
        path,
        "\n".join(
            (
                "[Desktop Entry]",
                "Type=Application",
                "Name=Harvis",
                f"Exec={executable}",
                "Terminal=false",
                "X-GNOME-Autostart-enabled=true",
                "",
            )
        ),
    )
    os.chmod(path, 0o600)


def subprocess_list2cmdline(arguments: list[str]) -> str:
    import subprocess

    return subprocess.list2cmdline(arguments)


__all__ = ["apply_startup_setting"]
