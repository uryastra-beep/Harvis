from __future__ import annotations

import csv
import json
import os
import platform
import re
import shutil
import signal
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from harvis.actions.system import SystemActionError

SKIP_DIRECTORY_NAMES = {
    "$recycle.bin",
    ".git",
    "cache",
    "caches",
    "code cache",
    "gpu cache",
    "node_modules",
    "temp",
    "tmp",
}


def open_discovered_application(name: str) -> dict[str, Any]:
    query = _normalize_name(name)
    if not query:
        raise ValueError("An application name is required.")

    system_name = platform.system()
    if system_name == "Windows":
        return _open_windows_discovered_application(query)
    if system_name == "Linux":
        return _open_linux_discovered_application(query)

    raise SystemActionError(
        f"Dynamic application discovery is not supported on {system_name or 'this platform'} yet."
    )


def close_discovered_application(name: str) -> dict[str, Any]:
    query = _normalize_name(name)
    if not query:
        raise ValueError("An application name is required.")

    system_name = platform.system()
    if system_name == "Windows":
        return _close_windows_discovered_application(query)
    if system_name == "Linux":
        return _close_linux_discovered_application(query)

    raise SystemActionError(
        f"Dynamic application closing is not supported on {system_name or 'this platform'} yet."
    )


def _normalize_name(value: str) -> str:
    text = str(value).strip().casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _score_name(candidate: str, query: str) -> int:
    candidate_normalized = _normalize_name(Path(candidate).stem)
    if not candidate_normalized:
        return 0
    if candidate_normalized == query:
        return 1000
    if candidate_normalized.startswith(query):
        return 850 - min(200, len(candidate_normalized) - len(query))
    if query in candidate_normalized:
        return 720 - min(200, len(candidate_normalized) - len(query))

    candidate_tokens = set(candidate_normalized.split())
    query_tokens = set(query.split())
    overlap = len(candidate_tokens & query_tokens)
    if overlap == len(query_tokens) and query_tokens:
        return 620 + overlap * 20
    if overlap:
        return 300 + overlap * 40
    return 0


def _open_windows_discovered_application(query: str) -> dict[str, Any]:
    direct = _windows_find_executable(query)
    if direct is not None:
        try:
            os.startfile(str(direct))
        except OSError as exc:
            raise SystemActionError(
                f"Harvis found {direct.name} but could not open it."
            ) from exc
        return {
            "status": "completed",
            "method": "executable",
            "application": query,
            "resolved": direct.name,
        }

    start_app = _windows_find_start_app(query)
    if start_app is not None:
        app_name, app_id = start_app
        try:
            subprocess.Popen(
                ["explorer.exe", f"shell:AppsFolder\\{app_id}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise SystemActionError(
                f"Harvis found {app_name} in the Start menu but could not open it."
            ) from exc
        return {
            "status": "completed",
            "method": "start_app",
            "application": query,
            "resolved": app_name,
        }

    raise SystemActionError(
        f"Harvis could not find an installed application matching '{query}'."
    )


@lru_cache(maxsize=64)
def _windows_find_executable(query: str) -> Path | None:
    direct_names = [query, query.replace(" ", ""), query.replace(" ", "-")]
    for direct_name in direct_names:
        for candidate_name in (direct_name, f"{direct_name}.exe"):
            resolved = shutil.which(candidate_name)
            if resolved:
                return Path(resolved)

    roots = _windows_search_roots()
    candidates: list[tuple[int, int, Path]] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        root_depth = len(root.parts)
        try:
            for current_root, directory_names, file_names in os.walk(root):
                current_path = Path(current_root)
                depth = len(current_path.parts) - root_depth
                if depth >= 5:
                    directory_names[:] = []
                else:
                    directory_names[:] = [
                        directory_name
                        for directory_name in directory_names
                        if directory_name.casefold() not in SKIP_DIRECTORY_NAMES
                    ]

                for file_name in file_names:
                    if not file_name.casefold().endswith(".exe"):
                        continue
                    score = _score_name(file_name, query)
                    if score < 300:
                        continue
                    candidate = current_path / file_name
                    path_bonus = _path_query_bonus(candidate, query)
                    candidates.append((score + path_bonus, -len(str(candidate)), candidate))
                    if score >= 1000 and path_bonus >= 50:
                        return candidate
        except OSError:
            continue

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][2]


def _windows_search_roots() -> tuple[Path, ...]:
    home = Path.home()
    program_files = Path(os.getenv("PROGRAMFILES", "C:/Program Files"))
    program_files_x86 = Path(os.getenv("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
    local_app_data = Path(os.getenv("LOCALAPPDATA", str(home / "AppData/Local")))
    app_data = Path(os.getenv("APPDATA", str(home / "AppData/Roaming")))
    return (
        program_files,
        program_files_x86,
        local_app_data / "Programs",
        local_app_data / "Microsoft/WindowsApps",
        app_data,
    )


def _path_query_bonus(path: Path, query: str) -> int:
    parent_text = _normalize_name(" ".join(path.parts[-4:-1]))
    query_tokens = set(query.split())
    parent_tokens = set(parent_text.split())
    overlap = len(query_tokens & parent_tokens)
    return overlap * 40


@lru_cache(maxsize=64)
def _windows_find_start_app(query: str) -> tuple[str, str] | None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        return None

    command = "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    if isinstance(payload, dict):
        items = [payload]
    elif isinstance(payload, list):
        items = payload
    else:
        return None

    best: tuple[int, str, str] | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        app_name = str(item.get("Name", "")).strip()
        app_id = str(item.get("AppID", "")).strip()
        if not app_name or not app_id:
            continue
        score = _score_name(app_name, query)
        if score < 300:
            continue
        candidate = (score, app_name, app_id)
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is None:
        return None
    return best[1], best[2]


def _close_windows_discovered_application(query: str) -> dict[str, Any]:
    tasklist = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    best_score = 0
    best_process_name = ""
    process_ids: set[int] = set()
    rows = list(csv.reader(tasklist.stdout.splitlines()))
    for row in rows:
        if len(row) < 2:
            continue
        process_name = row[0]
        score = _score_name(process_name, query)
        if score < 300:
            continue
        try:
            process_id = int(row[1])
        except ValueError:
            continue
        if score > best_score:
            best_score = score
            best_process_name = process_name
            process_ids = {process_id}
        elif score == best_score and process_name.casefold() == best_process_name.casefold():
            process_ids.add(process_id)

    if not process_ids:
        raise SystemActionError(
            f"Harvis could not find a running application matching '{query}'."
        )

    closed = _windows_post_close(process_ids)
    if closed <= 0:
        raise SystemActionError(
            f"Harvis found {best_process_name} but could not find a visible window to close."
        )

    return {
        "status": "completed",
        "application": query,
        "resolved": best_process_name,
        "windows_closed": closed,
    }


def _windows_post_close(process_ids: set[int]) -> int:
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


def _open_linux_discovered_application(query: str) -> dict[str, Any]:
    command_candidates = (
        query,
        query.replace(" ", "-"),
        query.replace(" ", ""),
    )
    for command in command_candidates:
        executable = shutil.which(command)
        if executable:
            subprocess.Popen(
                [executable],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return {
                "status": "completed",
                "method": "executable",
                "application": query,
                "resolved": Path(executable).name,
            }

    desktop_entry = _linux_find_desktop_entry(query)
    if desktop_entry is not None:
        gtk_launch = shutil.which("gtk-launch")
        if gtk_launch:
            subprocess.Popen(
                [gtk_launch, desktop_entry.stem],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return {
                "status": "completed",
                "method": "desktop_entry",
                "application": query,
                "resolved": desktop_entry.stem,
            }

    raise SystemActionError(
        f"Harvis could not find an installed Linux application matching '{query}'."
    )


@lru_cache(maxsize=64)
def _linux_find_desktop_entry(query: str) -> Path | None:
    roots = (
        Path.home() / ".local/share/applications",
        Path("/usr/share/applications"),
    )
    best: tuple[int, Path] | None = None
    for root in roots:
        if not root.exists():
            continue
        for path in root.glob("*.desktop"):
            score = _score_name(path.stem, query)
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for line in text.splitlines():
                if line.startswith("Name="):
                    score = max(score, _score_name(line[5:], query))
                    break
            if score < 300:
                continue
            if best is None or score > best[0]:
                best = (score, path)
    return None if best is None else best[1]


def _close_linux_discovered_application(query: str) -> dict[str, Any]:
    ps_result = subprocess.run(
        ["ps", "-eo", "pid=,comm="],
        capture_output=True,
        text=True,
        check=False,
    )
    best: tuple[int, int, str] | None = None
    for line in ps_result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            process_id = int(parts[0])
        except ValueError:
            continue
        process_name = parts[1]
        score = _score_name(process_name, query)
        if score < 300:
            continue
        candidate = (score, process_id, process_name)
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is None:
        raise SystemActionError(
            f"Harvis could not find a running Linux application matching '{query}'."
        )

    _, process_id, process_name = best
    try:
        os.kill(process_id, signal.SIGTERM)
    except OSError as exc:
        raise SystemActionError(
            f"Harvis found {process_name} but could not close it."
        ) from exc

    return {
        "status": "completed",
        "application": query,
        "resolved": process_name,
    }
