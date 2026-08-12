from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from harvis.actions.system import SystemActionError

MAX_SEARCHED_ENTRIES = 80_000
MAX_MATCHES = 12
_SKIPPED_DIRECTORIES = {
    ".cache",
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
}


def default_search_roots() -> list[Path]:
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "Downloads",
        home / "Documents",
        home / "Pictures",
        home / "Videos",
        home / "Music",
    ]
    roots = [path for path in candidates if path.exists()]
    return roots or [home]


def find_exact_paths(
    name: str,
    *,
    roots: Iterable[Path] | None = None,
) -> list[Path]:
    requested = str(name).strip().strip('"')
    if not requested:
        raise ValueError("An exact file or folder name is required.")

    direct = Path(os.path.expandvars(os.path.expanduser(requested)))
    if direct.is_absolute() and direct.exists():
        return [direct.resolve()]

    requested_folded = requested.casefold()
    requested_has_suffix = bool(Path(requested).suffix)
    matches: list[Path] = []
    searched = 0

    for root in roots or default_search_roots():
        root_path = Path(root).expanduser()
        if not root_path.exists():
            continue
        for current_root, directories, files in os.walk(root_path, topdown=True):
            directories[:] = [
                directory
                for directory in directories
                if directory.casefold() not in _SKIPPED_DIRECTORIES
            ]
            for entry_name in [*directories, *files]:
                searched += 1
                if searched > MAX_SEARCHED_ENTRIES:
                    return matches
                entry = Path(current_root) / entry_name
                matches_exact = entry.name.casefold() == requested_folded
                matches_stem = (
                    not requested_has_suffix
                    and entry.is_file()
                    and entry.stem.casefold() == requested_folded
                )
                if matches_exact or matches_stem:
                    matches.append(entry.resolve())
                    if len(matches) >= MAX_MATCHES:
                        return matches
    return matches


def open_exact_path(name: str, *, roots: Iterable[Path] | None = None) -> dict[str, Any]:
    matches = find_exact_paths(name, roots=roots)
    if not matches:
        return {"status": "not_found", "name": str(name).strip()}
    if len(matches) > 1:
        return {
            "status": "ambiguous",
            "name": str(name).strip(),
            "matches": [str(path) for path in matches],
        }

    path = matches[0]
    _open_with_default_application(path)
    return {
        "status": "completed",
        "name": path.name,
        "path": str(path),
        "kind": "folder" if path.is_dir() else "file",
    }


def _open_with_default_application(path: Path) -> None:
    system_name = platform.system()
    try:
        if system_name == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return
        if system_name == "Linux":
            launcher = shutil.which("xdg-open")
            if launcher:
                subprocess.Popen(
                    [launcher, str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                return
        if system_name == "Darwin":
            subprocess.Popen(
                ["open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
    except OSError as exc:
        raise SystemActionError(f"Harvis could not open {path.name}.") from exc
    raise SystemActionError(
        f"Opening files is not supported on {system_name or 'this platform'} yet."
    )
