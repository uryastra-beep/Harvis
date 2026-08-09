from __future__ import annotations

import csv
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path

from harvis.actions.system import SystemActionError


APPLICATION_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "edge": "edge",
    "microsoft edge": "edge",
    "firefox": "firefox",
    "spotify": "spotify",
    "discord": "discord",
    "vscode": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "notepad": "notepad",
    "calculator": "calculator",
    "terminal": "terminal",
    "windows terminal": "terminal",
    "settings": "settings",
    "windows settings": "settings",
    "file explorer": "explorer",
    "explorer": "explorer",
}

WINDOWS_PROCESS_NAMES = {
    "chrome": ("chrome.exe",),
    "edge": ("msedge.exe",),
    "firefox": ("firefox.exe",),
    "spotify": ("spotify.exe",),
    "discord": ("discord.exe",),
    "vscode": ("code.exe",),
    "notepad": ("notepad.exe",),
    "calculator": ("calculatorapp.exe", "calculator.exe"),
    "terminal": ("windowsterminal.exe",),
    "settings": ("systemsettings.exe",),
}

LINUX_COMMANDS = {
    "chrome": ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"),
    "edge": ("microsoft-edge", "microsoft-edge-stable"),
    "firefox": ("firefox",),
    "spotify": ("spotify",),
    "discord": ("discord",),
    "vscode": ("code",),
    "notepad": ("gnome-text-editor", "gedit", "kate", "mousepad"),
    "calculator": ("gnome-calculator", "kcalc", "galculator"),
    "terminal": ("kitty", "konsole", "gnome-terminal", "alacritty", "wezterm"),
    "settings": ("gnome-control-center", "systemsettings", "systemsettings6"),
    "explorer": ("nautilus", "dolphin", "thunar", "nemo"),
}

BROWSER_PROCESS_NAMES = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "vivaldi.exe",
    "chrome",
    "chromium",
    "firefox",
    "brave",
    "brave-browser",
    "microsoft-edge",
}

BROWSER_ACTIONS = {
    "close_tab",
    "new_tab",
    "reopen_tab",
    "refresh",
    "back",
    "forward",
    "focus_address",
}

MEDIA_ACTIONS = {
    "play_pause",
    "next_track",
    "previous_track",
}


def normalize_application_name(name: str) -> str:
    normalized = " ".join(str(name).strip().lower().replace("_", " ").replace("-", " ").split())
    app_key = APPLICATION_ALIASES.get(normalized)
    if app_key is None:
        supported = ", ".join(sorted(set(APPLICATION_ALIASES.values())))
        raise SystemActionError(
            f"Unsupported application '{name}'. Supported application names: {supported}."
        )
    return app_key


def open_application(name: str) -> None:
    app_key = normalize_application_name(name)
    system_name = platform.system()

    if system_name == "Windows":
        _open_windows_application(app_key)
        return

    if system_name == "Linux":
        _open_linux_application(app_key)
        return

    raise SystemActionError(
        f"Application launching is not supported on {system_name or 'this platform'} yet."
    )


def close_application(name: str) -> None:
    app_key = normalize_application_name(name)
    system_name = platform.system()

    if system_name == "Windows":
        _close_windows_application(app_key)
        return

    if system_name == "Linux":
        _close_linux_application(app_key)
        return

    raise SystemActionError(
        f"Application closing is not supported on {system_name or 'this platform'} yet."
    )


def control_browser(action: str) -> None:
    normalized_action = str(action).strip().lower()
    if normalized_action not in BROWSER_ACTIONS:
        raise SystemActionError(f"Unsupported browser action: {action}.")

    system_name = platform.system()
    if system_name == "Windows":
        _control_windows_browser(normalized_action)
        return

    if system_name == "Linux":
        _control_linux_browser(normalized_action)
        return

    raise SystemActionError(
        f"Browser controls are not supported on {system_name or 'this platform'} yet."
    )


def control_media(action: str) -> None:
    normalized_action = str(action).strip().lower()
    if normalized_action not in MEDIA_ACTIONS:
        raise SystemActionError(f"Unsupported media action: {action}.")

    system_name = platform.system()
    if system_name == "Windows":
        _control_windows_media(normalized_action)
        return

    if system_name == "Linux":
        _control_linux_media(normalized_action)
        return

    raise SystemActionError(
        f"Media controls are not supported on {system_name or 'this platform'} yet."
    )


def _open_windows_application(app_key: str) -> None:
    if app_key == "settings":
        os.startfile("ms-settings:")
        return

    if app_key == "spotify":
        try:
            os.startfile("spotify:")
            return
        except OSError:
            pass

    candidate = _find_windows_application(app_key)
    if candidate is None:
        raise SystemActionError(f"Harvis could not find the {app_key} application.")

    try:
        os.startfile(str(candidate))
    except OSError as exc:
        raise SystemActionError(f"Harvis could not open {app_key}.") from exc


def _find_windows_application(app_key: str) -> Path | None:
    executable_names = {
        "chrome": ("chrome.exe",),
        "edge": ("msedge.exe",),
        "firefox": ("firefox.exe",),
        "spotify": ("Spotify.exe",),
        "discord": ("Discord.exe",),
        "vscode": ("Code.exe", "code.exe"),
        "notepad": ("notepad.exe",),
        "calculator": ("calc.exe",),
        "terminal": ("wt.exe",),
        "explorer": ("explorer.exe",),
    }.get(app_key, ())

    for executable_name in executable_names:
        resolved = shutil.which(executable_name)
        if resolved:
            return Path(resolved)

    program_files = Path(os.getenv("PROGRAMFILES", "C:/Program Files"))
    program_files_x86 = Path(os.getenv("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
    local_app_data = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    app_data = Path(os.getenv("APPDATA", str(Path.home() / "AppData/Roaming")))

    known_paths = {
        "chrome": (
            program_files / "Google/Chrome/Application/chrome.exe",
            program_files_x86 / "Google/Chrome/Application/chrome.exe",
            local_app_data / "Google/Chrome/Application/chrome.exe",
        ),
        "edge": (
            program_files / "Microsoft/Edge/Application/msedge.exe",
            program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
        ),
        "firefox": (
            program_files / "Mozilla Firefox/firefox.exe",
            program_files_x86 / "Mozilla Firefox/firefox.exe",
        ),
        "spotify": (
            app_data / "Spotify/Spotify.exe",
            local_app_data / "Microsoft/WindowsApps/Spotify.exe",
        ),
        "vscode": (
            local_app_data / "Programs/Microsoft VS Code/Code.exe",
            program_files / "Microsoft VS Code/Code.exe",
        ),
        "terminal": (
            local_app_data / "Microsoft/WindowsApps/wt.exe",
        ),
    }

    for path in known_paths.get(app_key, ()):
        if path.exists():
            return path

    if app_key == "discord":
        discord_root = local_app_data / "Discord"
        versions = sorted(discord_root.glob("app-*/Discord.exe"), reverse=True)
        if versions:
            return versions[0]

    return None


def _open_linux_application(app_key: str) -> None:
    for command_name in LINUX_COMMANDS.get(app_key, ()):
        executable = shutil.which(command_name)
        if executable:
            subprocess.Popen(
                [executable],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return

    raise SystemActionError(f"Harvis could not find the {app_key} application.")


def _close_windows_application(app_key: str) -> None:
    if app_key == "explorer":
        raise SystemActionError(
            "Closing File Explorer is disabled because explorer.exe also hosts the Windows shell."
        )

    process_names = WINDOWS_PROCESS_NAMES.get(app_key)
    if not process_names:
        raise SystemActionError(f"Closing {app_key} is not supported yet.")

    process_ids = _windows_process_ids(process_names)
    if not process_ids:
        raise SystemActionError(f"{app_key} does not appear to be running.")

    closed_windows = _post_close_to_windows(process_ids)
    if closed_windows > 0:
        return

    if app_key in {"spotify", "discord"}:
        for process_name in process_names:
            subprocess.run(
                ["taskkill", "/IM", process_name],
                capture_output=True,
                text=True,
                check=False,
            )
        return

    raise SystemActionError(f"Harvis could not find an open {app_key} window to close.")


def _windows_process_ids(process_names: tuple[str, ...]) -> set[int]:
    process_ids: set[int] = set()

    for process_name in process_names:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for row in csv.reader(result.stdout.splitlines()):
            if len(row) < 2 or row[0].lower() != process_name.lower():
                continue
            try:
                process_ids.add(int(row[1]))
            except ValueError:
                continue

    return process_ids


def _post_close_to_windows(process_ids: set[int]) -> int:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    wm_close = 0x0010
    closed_count = 0

    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd, lparam):
        nonlocal closed_count
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if process_id.value in process_ids and user32.IsWindowVisible(hwnd):
            if user32.PostMessageW(hwnd, wm_close, 0, 0):
                closed_count += 1
        return True

    user32.EnumWindows(callback, 0)
    return closed_count


def _close_linux_application(app_key: str) -> None:
    if app_key == "explorer":
        raise SystemActionError(
            "Closing the file manager by process is disabled because desktop environments may reuse it."
        )

    command_names = LINUX_COMMANDS.get(app_key, ())
    found_process = False

    for command_name in command_names:
        pkill = shutil.which("pkill")
        if pkill is None:
            break

        result = subprocess.run(
            [pkill, "-TERM", "-x", command_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            found_process = True

    if not found_process:
        raise SystemActionError(f"{app_key} does not appear to be running.")


def _control_windows_browser(action: str) -> None:
    process_name = _windows_foreground_process_name()
    if process_name.lower() not in BROWSER_PROCESS_NAMES:
        raise SystemActionError(
            "The active window is not a supported web browser. Focus the browser first."
        )

    shortcuts = {
        "close_tab": ((0x11,), 0x57),
        "new_tab": ((0x11,), 0x54),
        "reopen_tab": ((0x11, 0x10), 0x54),
        "refresh": ((0x11,), 0x52),
        "back": ((0x12,), 0x25),
        "forward": ((0x12,), 0x27),
        "focus_address": ((0x11,), 0x4C),
    }
    modifiers, key = shortcuts[action]
    _windows_send_shortcut(modifiers, key)


def _windows_foreground_process_name() -> str:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise SystemActionError("Harvis could not determine the active window.")

    process_id = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))

    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {process_id.value}", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    rows = list(csv.reader(result.stdout.splitlines()))
    if not rows or not rows[0]:
        raise SystemActionError("Harvis could not identify the active application.")

    return rows[0][0]


def _windows_send_shortcut(modifiers: tuple[int, ...], key: int) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    keyup = 0x0002

    for modifier in modifiers:
        user32.keybd_event(modifier, 0, 0, 0)

    user32.keybd_event(key, 0, 0, 0)
    time.sleep(0.025)
    user32.keybd_event(key, 0, keyup, 0)

    for modifier in reversed(modifiers):
        user32.keybd_event(modifier, 0, keyup, 0)


def _control_linux_browser(action: str) -> None:
    xdotool = shutil.which("xdotool")
    if xdotool is None:
        raise SystemActionError(
            "Linux browser controls currently require xdotool and an X11-compatible session."
        )

    try:
        window_id = subprocess.check_output(
            [xdotool, "getactivewindow"],
            text=True,
        ).strip()
        process_id = subprocess.check_output(
            [xdotool, "getwindowpid", window_id],
            text=True,
        ).strip()
        process_name = Path(f"/proc/{process_id}/comm").read_text(encoding="utf-8").strip().lower()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemActionError("Harvis could not identify the active Linux browser window.") from exc

    if process_name not in BROWSER_PROCESS_NAMES:
        raise SystemActionError(
            "The active window is not a supported web browser. Focus the browser first."
        )

    shortcuts = {
        "close_tab": "ctrl+w",
        "new_tab": "ctrl+t",
        "reopen_tab": "ctrl+shift+t",
        "refresh": "ctrl+r",
        "back": "alt+Left",
        "forward": "alt+Right",
        "focus_address": "ctrl+l",
    }

    result = subprocess.run(
        [xdotool, "key", "--clearmodifiers", shortcuts[action]],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemActionError("The Linux browser shortcut could not be sent.")


def _control_windows_media(action: str) -> None:
    media_keys = {
        "play_pause": 0xB3,
        "next_track": 0xB0,
        "previous_track": 0xB1,
    }
    _windows_send_shortcut((), media_keys[action])


def _control_linux_media(action: str) -> None:
    playerctl = shutil.which("playerctl")
    if playerctl is None:
        raise SystemActionError("Linux media controls require playerctl.")

    commands = {
        "play_pause": "play-pause",
        "next_track": "next",
        "previous_track": "previous",
    }
    result = subprocess.run(
        [playerctl, commands[action]],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemActionError("The media command could not be completed.")
