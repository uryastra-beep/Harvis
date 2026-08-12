from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from harvis.features.file_access import find_exact_paths

_CATEGORY_SUFFIXES = {
    "Images": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"},
    "Videos": {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"},
    "Audio": {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"},
    "Documents": {".csv", ".doc", ".docx", ".md", ".odt", ".pdf", ".ppt", ".pptx", ".txt", ".xls", ".xlsx"},
    "Archives": {".7z", ".gz", ".rar", ".tar", ".zip"},
}


def resolve_one_exact(name: str) -> tuple[Path | None, dict[str, Any] | None]:
    matches = find_exact_paths(name)
    if not matches:
        return None, {"status": "not_found", "name": str(name).strip()}
    if len(matches) > 1:
        return None, {
            "status": "ambiguous",
            "name": str(name).strip(),
            "matches": [str(path) for path in matches],
        }
    return matches[0], None


def copy_item(source_name: str, destination_folder_name: str) -> dict[str, Any]:
    source, error = resolve_one_exact(source_name)
    if error is not None:
        return error
    destination, error = resolve_one_exact(destination_folder_name)
    if error is not None:
        return error
    if source is None or destination is None:
        raise RuntimeError("Harvis could not resolve the requested copy paths.")
    if not destination.is_dir():
        raise ValueError("The destination must be an existing folder.")
    target = destination / source.name
    if target.exists():
        return {"status": "conflict", "path": str(target)}
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
    return {
        "status": "completed",
        "source": str(source),
        "path": str(target),
    }


def move_item(source_name: str, destination_folder_name: str) -> dict[str, Any]:
    source, error = resolve_one_exact(source_name)
    if error is not None:
        return error
    destination, error = resolve_one_exact(destination_folder_name)
    if error is not None:
        return error
    if source is None or destination is None:
        raise RuntimeError("Harvis could not resolve the requested move paths.")
    if not destination.is_dir():
        raise ValueError("The destination must be an existing folder.")
    target = destination / source.name
    if target.exists():
        return {"status": "conflict", "path": str(target)}
    original_parent = source.parent
    shutil.move(str(source), str(target))
    return {
        "status": "completed",
        "source": str(source),
        "path": str(target),
        "undo": {
            "action": "move_path_absolute",
            "arguments": {
                "source_path": str(target),
                "destination_folder_path": str(original_parent),
            },
        },
    }


def rename_item(source_name: str, new_name: str) -> dict[str, Any]:
    source, error = resolve_one_exact(source_name)
    if error is not None:
        return error
    if source is None:
        raise RuntimeError("Harvis could not resolve the requested rename path.")
    clean_name = str(new_name).strip().strip('"')
    if not clean_name or clean_name in {".", ".."} or any(separator in clean_name for separator in ("/", "\\")):
        raise ValueError("The new name must be one valid file or folder name.")
    target = source.with_name(clean_name)
    if target.exists():
        return {"status": "conflict", "path": str(target)}
    source.rename(target)
    return {
        "status": "completed",
        "source": str(source),
        "path": str(target),
        "undo": {
            "action": "rename_path_absolute",
            "arguments": {
                "source_path": str(target),
                "new_name": source.name,
            },
        },
    }


def move_path_absolute(source_path: str, destination_folder_path: str) -> dict[str, Any]:
    source = Path(source_path)
    destination = Path(destination_folder_path)
    if not source.exists() or not destination.is_dir():
        return {"status": "not_found"}
    target = destination / source.name
    if target.exists():
        return {"status": "conflict", "path": str(target)}
    shutil.move(str(source), str(target))
    return {"status": "completed", "path": str(target)}


def rename_path_absolute(source_path: str, new_name: str) -> dict[str, Any]:
    source = Path(source_path)
    if not source.exists():
        return {"status": "not_found", "path": str(source)}
    clean_name = str(new_name).strip()
    if not clean_name or any(separator in clean_name for separator in ("/", "\\")):
        raise ValueError("The new name is invalid.")
    target = source.with_name(clean_name)
    if target.exists():
        return {"status": "conflict", "path": str(target)}
    source.rename(target)
    return {"status": "completed", "path": str(target)}


def send_item_to_trash(path: Path) -> dict[str, Any]:
    try:
        from send2trash import send2trash
    except ImportError as exc:
        raise RuntimeError("Safe deletion requires send2trash. Reinstall requirements.txt.") from exc
    if not path.exists():
        return {"status": "not_found", "path": str(path)}
    send2trash(str(path))
    return {
        "status": "completed",
        "path": str(path),
        "recoverable": True,
        "location": "operating system trash",
    }


def organize_folder_by_type(folder: Path) -> dict[str, Any]:
    if not folder.is_dir():
        raise ValueError("The selected item must be a folder.")
    moved: list[dict[str, str]] = []
    skipped: list[str] = []
    for item in list(folder.iterdir()):
        if not item.is_file():
            continue
        category = _category_for_suffix(item.suffix.casefold())
        destination = folder / category
        target = destination / item.name
        if target.exists():
            skipped.append(str(item))
            continue
        destination.mkdir(exist_ok=True)
        shutil.move(str(item), str(target))
        moved.append({"source": str(item), "path": str(target)})
    return {
        "status": "completed",
        "folder": str(folder),
        "moved": moved,
        "skipped": skipped,
    }


def _category_for_suffix(suffix: str) -> str:
    for category, suffixes in _CATEGORY_SUFFIXES.items():
        if suffix in suffixes:
            return category
    return "Other"


__all__ = [
    "copy_item",
    "move_item",
    "move_path_absolute",
    "organize_folder_by_type",
    "rename_item",
    "rename_path_absolute",
    "resolve_one_exact",
    "send_item_to_trash",
]
